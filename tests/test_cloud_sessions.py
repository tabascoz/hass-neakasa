"""Tests for the cloud-side budget: sessions minted, requests per scan."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.neakasa.api import _describe_write
from custom_components.neakasa.api_manager import (
    _session_mints,
    _shared_clients,
    _shared_locks,
    clear_shared_api,
    get_shared_api,
)
from custom_components.neakasa.button.refresh_data import NeakasaRefreshDataButton
from custom_components.neakasa.coordinator import (
    SESSION_OWNER_ELSEWHERE,
    SESSION_OWNER_OURS,
    NeakasaCoordinator,
)
from custom_components.neakasa.exceptions import (
    NeakasaApiClientSessionExpiredError,
)
from custom_components.neakasa.sensor.cloud_session import (
    NeakasaCloudSessionStatusSensor,
)

USER = "cloud@example.com"
PASSWORD = "hunter2"

DEVICE_LIST = [
    {
        "iotId": "iot-001",
        "deviceName": "T1 Plus",
        "categoryKey": "CatLitter",
        "productKey": "a1nNMMJkLqG",
        "nickName": "T1 Plus",
    }
]


def _scanning_client() -> AsyncMock:
    """A client whose every cloud call succeeds, without touching the network."""
    client = AsyncMock()
    client.get_devices = AsyncMock(return_value=DEVICE_LIST)
    client.get_device_properties = AsyncMock(return_value={})
    client.get_records = AsyncMock(return_value={})
    client.refresh_session = AsyncMock()
    return client


def _coordinator(
    hass: HomeAssistant, entry: MagicMock, client: AsyncMock
) -> NeakasaCoordinator:
    """Return a real coordinator whose shared client is *client*."""
    coordinator = NeakasaCoordinator(hass, entry)
    coordinator._get_client = AsyncMock(return_value=client)
    return coordinator


async def test_scan_uses_one_client_and_a_cached_device_list(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
) -> None:
    """Two scans take one client each and list the account devices once."""
    client = _scanning_client()
    coordinator = _coordinator(hass, mock_config_entry, client)

    first = await coordinator.async_update_data()
    second = await coordinator.async_update_data()

    assert "iot-001" in first
    assert "iot-001" in second
    assert coordinator._get_client.await_count == 2
    assert client.get_devices.call_count == 1
    assert client.get_device_properties.call_count == 2
    assert client.get_records.call_count == 1


async def test_device_name_needs_no_extra_lookup(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
) -> None:
    """Names come from the device list the scan already fetched."""
    client = _scanning_client()
    coordinator = _coordinator(hass, mock_config_entry, client)

    await coordinator._discover_devices()
    assert await coordinator._get_device_name("iot-001") == "T1 Plus"
    assert client.get_devices.call_count == 1


async def test_forced_refresh_refetches_the_device_list(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
) -> None:
    """Recovery paths drop the cached list so new devices are found."""
    client = _scanning_client()
    coordinator = _coordinator(hass, mock_config_entry, client)

    await coordinator._discover_devices()
    coordinator.force_refresh_devices()
    await coordinator._discover_devices()
    assert client.get_devices.call_count == 2


async def test_session_failure_renews_the_token_without_signing_in(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
) -> None:
    """A rejected session is renewed by token exchange, not by logging in."""
    client = _scanning_client()
    client.get_devices = AsyncMock(
        side_effect=[NeakasaApiClientSessionExpiredError("expired"), DEVICE_LIST]
    )
    coordinator = _coordinator(hass, mock_config_entry, client)

    with patch(
        "custom_components.neakasa.coordinator.force_reconnect_api",
        new=MagicMock(),
    ) as reconnect:
        payload = await coordinator.async_update_data()

    assert "iot-001" in payload
    assert client.refresh_session.call_count == 1
    assert client.get_devices.call_count == 2
    reconnect.assert_not_called()


async def test_repeated_session_failures_do_not_stack_sessions(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
) -> None:
    """A second failure inside the cooldown does not sign in again."""
    client = _scanning_client()
    client.get_devices = AsyncMock(
        side_effect=[
            NeakasaApiClientSessionExpiredError("first"),
            NeakasaApiClientSessionExpiredError("second"),
        ]
    )
    client.refresh_session = AsyncMock(
        side_effect=NeakasaApiClientSessionExpiredError("rejected")
    )
    coordinator = _coordinator(hass, mock_config_entry, client)

    with (
        patch(
            "custom_components.neakasa.coordinator.force_reconnect_api",
            new=AsyncMock(),
        ) as reconnect,
        pytest.raises(UpdateFailed),
    ):
        await coordinator.async_update_data()

    reconnect.assert_awaited_once()
    assert client.refresh_session.call_count == 2


SESSION_REFUSED = NeakasaApiClientSessionExpiredError("request auth error")


def _api_manager_patches() -> tuple[MagicMock, MagicMock, MagicMock]:
    """Patched collaborators so the shared manager does no HTTP."""
    session = MagicMock()
    api_cls = MagicMock()
    api_cls.return_value.connect = AsyncMock()
    client_cls = MagicMock()
    client_cls.return_value.connected = True
    return session, api_cls, client_cls


async def test_concurrent_callers_authenticate_once() -> None:
    """Two first-setup paths sharing an account sign in once."""
    clear_shared_api(USER, PASSWORD)
    session, api_cls, client_cls = _api_manager_patches()
    with (
        patch(
            "custom_components.neakasa.api_manager.async_get_clientsession",
            return_value=session,
        ),
        patch("custom_components.neakasa.api_manager.NeakasaAPI", api_cls),
        patch(
            "custom_components.neakasa.api_manager.NeakasaApiClient",
            client_cls,
        ),
    ):
        clients = await asyncio.gather(
            get_shared_api(MagicMock(), USER, PASSWORD),
            get_shared_api(MagicMock(), USER, PASSWORD),
        )

    assert clients[0] is clients[1]
    api_cls.return_value.connect.assert_awaited_once()


async def test_clearing_the_client_keeps_the_lock() -> None:
    """A cleared client must not hand out a fresh lock to waiting callers."""
    session, api_cls, client_cls = _api_manager_patches()
    with (
        patch(
            "custom_components.neakasa.api_manager.async_get_clientsession",
            return_value=session,
        ),
        patch("custom_components.neakasa.api_manager.NeakasaAPI", api_cls),
        patch(
            "custom_components.neakasa.api_manager.NeakasaApiClient",
            client_cls,
        ),
    ):
        await get_shared_api(MagicMock(), USER, PASSWORD)
        clear_shared_api(USER, PASSWORD)

    credentials_key = f"{USER}:{PASSWORD}"
    assert credentials_key not in _shared_clients
    assert credentials_key in _shared_locks


TOKEN_REJECTED = (
    "Error in /catbox/record: Error getting data: TokenInvalid\ufffatoken is abnormal"
)


async def test_rejected_account_token_recovers_by_signing_in(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
) -> None:
    """The records token is only replaced by a sign-in, not a token exchange."""
    client = _scanning_client()
    client.get_records = AsyncMock(
        side_effect=[
            NeakasaApiClientSessionExpiredError(TOKEN_REJECTED),
            {"cat_list": [], "record_list": []},
        ]
    )
    coordinator = _coordinator(hass, mock_config_entry, client)

    with patch(
        "custom_components.neakasa.coordinator.force_reconnect_api",
        new=AsyncMock(),
    ) as reconnect:
        payload = await coordinator.async_update_data()

    assert "iot-001" in payload
    assert client.get_records.call_count == 2
    assert client.refresh_session.call_count == 0
    reconnect.assert_awaited_once()


async def test_a_persistently_rejected_token_gives_up_early(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
) -> None:
    """Repeated recovery attempts stop at the bound without minting sessions."""
    client = _scanning_client()
    client.get_records = AsyncMock(
        side_effect=NeakasaApiClientSessionExpiredError(TOKEN_REJECTED)
    )
    coordinator = _coordinator(hass, mock_config_entry, client)

    with (
        patch(
            "custom_components.neakasa.coordinator.force_reconnect_api",
            new=AsyncMock(),
        ) as reconnect,
        pytest.raises(UpdateFailed),
    ):
        await coordinator.async_update_data()

    reconnect.assert_awaited_once()
    assert client.refresh_session.call_count == 0


# ---------------------------------------------------------------------------
# What the cloud was asked for, as the journal says it
# ---------------------------------------------------------------------------


def test_write_lines_name_the_call_and_the_device() -> None:
    """The line for an accepted write names the call, the device, the payload."""
    service = {
        "args": {"bStartClean": 1},
        "identifier": "cleanNow",
        "iotId": "iot-1",
    }
    assert _describe_write("/thing/service/invoke", service) == (
        "/thing/service/invoke iotId=iot-1 identifier=cleanNow args={'bStartClean': 1}"
    )

    properties = {"items": {"autoClean": 1}, "iotId": "iot-1"}
    assert _describe_write("/thing/properties/set", properties) == (
        "/thing/properties/set iotId=iot-1 items={'autoClean': 1}"
    )


async def test_sign_ins_are_numbered_and_a_reuse_is_not() -> None:
    """Two sign-ins for one account are numbered; a reused client adds none."""
    session, api_cls, client_cls = _api_manager_patches()
    # Other tests in this file already signed in for USER, so only the
    # lines this test adds are asserted.
    before = _session_mints.get(USER, 0)
    clear_shared_api(USER, PASSWORD)
    with (
        patch(
            "custom_components.neakasa.api_manager.async_get_clientsession",
            return_value=session,
        ),
        patch("custom_components.neakasa.api_manager.NeakasaAPI", api_cls),
        patch(
            "custom_components.neakasa.api_manager.NeakasaApiClient",
            client_cls,
        ),
    ):
        await get_shared_api(MagicMock(), USER, PASSWORD, "first scan")
        assert _session_mints[USER] == before + 1
        await get_shared_api(MagicMock(), USER, PASSWORD)
        assert _session_mints[USER] == before + 1
        clear_shared_api(USER, PASSWORD)
        await get_shared_api(MagicMock(), USER, PASSWORD, "session expired")
        assert _session_mints[USER] == before + 2
        assert api_cls.return_value.connect.await_count == 2


async def test_a_refused_account_call_opens_a_back_off_and_says_so(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
) -> None:
    """The list we were given is served, and the update says the values are cached."""
    client = _scanning_client()
    client.get_devices = AsyncMock(side_effect=[DEVICE_LIST, SESSION_REFUSED])
    coordinator = _coordinator(hass, mock_config_entry, client)

    first = await coordinator.async_update_data()
    assert "iot-001" in first
    assert coordinator.cloud_session_owner == SESSION_OWNER_OURS

    coordinator.force_refresh_devices()
    second = await coordinator.async_update_data()
    assert "iot-001" in second
    assert client.get_devices.call_count == 2
    assert coordinator.records_refused is True
    assert coordinator.cloud_session_owner == SESSION_OWNER_ELSEWHERE

    third = await coordinator.async_update_data()
    assert "iot-001" in third
    assert client.get_devices.call_count == 2
    assert coordinator.records_refused is True


async def test_a_request_takes_the_session_back_and_re_reads(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
) -> None:
    """Regaining the session signs in once, closes the window and reads again."""
    client = _scanning_client()
    client.get_devices = AsyncMock(
        side_effect=[DEVICE_LIST, SESSION_REFUSED, DEVICE_LIST]
    )
    coordinator = _coordinator(hass, mock_config_entry, client)

    first = await coordinator.async_update_data()
    assert "iot-001" in first

    coordinator.force_refresh_devices()
    await coordinator.async_update_data()
    assert coordinator.cloud_session_owner == SESSION_OWNER_ELSEWHERE

    with patch(
        "custom_components.neakasa.coordinator.force_reconnect_api",
        new=AsyncMock(),
    ) as reconnect:
        await coordinator.regain_cloud_session()
    reconnect.assert_awaited_once()
    assert client.get_devices.call_count == 3
    assert coordinator.cloud_session_owner == SESSION_OWNER_OURS


async def test_the_account_sensor_names_the_client_that_holds_the_session(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
) -> None:
    """The account sensor follows what the scans observed."""
    client = _scanning_client()
    client.get_devices = AsyncMock(side_effect=[DEVICE_LIST, SESSION_REFUSED])
    coordinator = _coordinator(hass, mock_config_entry, client)

    sensor = NeakasaCloudSessionStatusSensor(coordinator, MagicMock())
    first = await coordinator.async_update_data()
    assert "iot-001" in first
    assert sensor.native_value == SESSION_OWNER_OURS

    coordinator.force_refresh_devices()
    await coordinator.async_update_data()
    assert sensor.native_value == SESSION_OWNER_ELSEWHERE


async def test_the_account_button_takes_the_session_back_in_one_sign_in(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
) -> None:
    """Pressing it signs in once, closes the window and re-reads the account."""
    client = _scanning_client()
    client.get_devices = AsyncMock(
        side_effect=[DEVICE_LIST, SESSION_REFUSED, DEVICE_LIST]
    )
    coordinator = _coordinator(hass, mock_config_entry, client)

    first = await coordinator.async_update_data()
    assert "iot-001" in first

    coordinator.force_refresh_devices()
    assert (await coordinator.async_update_data()) != {}
    assert coordinator.records_refused is True

    button = NeakasaRefreshDataButton(coordinator, MagicMock())
    with patch(
        "custom_components.neakasa.coordinator.force_reconnect_api",
        new=AsyncMock(),
    ) as reconnect:
        await button.async_press()

    reconnect.assert_awaited_once()
    assert client.get_devices.call_count == 3
    assert coordinator.cloud_session_owner == SESSION_OWNER_OURS

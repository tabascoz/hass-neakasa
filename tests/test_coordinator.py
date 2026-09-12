"""Tests for NeakasaCoordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.neakasa.coordinator import (
    NeakasaCoordinator,
    _build_device_snapshot,
    _get_last_use_date,
    _property_value,
    _to_int,
    _to_list,
)
from custom_components.neakasa.exceptions import (
    NeakasaApiClientAuthenticationError,
    NeakasaApiClientSessionExpiredError,
)

# ---------------------------------------------------------------------------
# Wire-value helpers (unit tests, no HA needed)
# ---------------------------------------------------------------------------

FAKE_DEVDATA: dict = {
    "binFullWaitReset": {"value": 1},
    "cleanCfg": {
        "value": {"active": True, "cleanInterval": 23, "workTime": 10, "delayTime": 5}
    },
    "youngCatMode": {"value": 0},
    "childLockOnOff": {"value": 0},
    "autoBury": {"value": 1},
    "autoLevel": {"value": 1},
    "silentMode": {"value": 0},
    "autoForceInit": {"value": 0},
    "bIntrptRangeDet": {"value": 1},
    "bucketStatus": {"value": 0},
    "room_of_bin": {"value": 0},
    "Sand": {"value": {"percent": 65, "level": 2}},
    "NetWorkStatus": {"value": {"WiFi_RSSI": -55}},
    "catLeft": {"value": {"stayTime": 120}, "time": 1730000000},
}

FAKE_DEVICES_LIST = [
    {"iotId": "iot-001", "deviceName": "T1 Plus", "categoryKey": "CatLitter"}
]


def test_property_value_present() -> None:
    assert _property_value(FAKE_DEVDATA, "bucketStatus") == 0


def test_property_value_missing_key() -> None:
    assert _property_value(FAKE_DEVDATA, "nonexistent", default=42) == 42


def test_property_value_not_dict() -> None:
    assert _property_value(None, "bucketStatus", default=99) == 99


def test_to_int_bool() -> None:
    assert _to_int(True) == 1
    assert _to_int(False) == 0


def test_to_int_string() -> None:
    assert _to_int("42") == 42


def test_to_int_invalid() -> None:
    assert _to_int("abc", default=99) == 99
    assert _to_int(None, default=99) == 99


def test_to_list_valid() -> None:
    assert _to_list([1, 2]) == [1, 2]


def test_to_list_none() -> None:
    assert _to_list(None) == []


def test_get_last_use_date_present() -> None:
    assert _get_last_use_date(FAKE_DEVDATA) == 1730000000


def test_get_last_use_date_missing() -> None:
    assert _get_last_use_date({}) == 0


def test_build_snapshot() -> None:
    snap = _build_device_snapshot(
        "iot-001",
        "T1 Plus",
        FAKE_DEVDATA,
        {},
        1730000000,
        category_key="CatLitter",
        product_key="a1nNMMJkLqG",
    )
    assert snap.iot_id == "iot-001"
    assert snap.device_name == "T1 Plus"
    assert snap.category_key == "CatLitter"
    assert snap.product_key == "a1nNMMJkLqG"
    assert snap.bin_full is True
    assert snap.sand_level_percent == 65
    assert snap.sand_level_state == 2
    assert snap.wifi_rssi == -55
    assert snap.stay_time == 120
    assert snap.last_use == 1730000000
    assert snap.young_cat_mode is False
    assert snap.child_lock is False
    assert snap.auto_bury is True
    assert snap.auto_level is True
    assert snap.silent_mode is False


def test_build_snapshot_empty_dict() -> None:
    snap = _build_device_snapshot("iot-001", "T1", {}, {}, 0)
    assert snap.iot_id == "iot-001"
    assert snap.bin_full is False
    assert snap.sand_level_percent == 0


# ---------------------------------------------------------------------------
# Coordinator tests — mock _get_client directly
# ---------------------------------------------------------------------------


def _make_coordinator(hass: HomeAssistant, entry: MagicMock) -> NeakasaCoordinator:
    """Create a coordinator and inject a mock client."""
    c = NeakasaCoordinator(hass, entry)
    c._get_client = AsyncMock()
    return c


async def test_coordinator_first_refresh(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_get_shared_api: MagicMock,
) -> None:
    """Test that the coordinator fetches device data."""
    coordinator = _make_coordinator(hass, mock_config_entry)
    # Override the client mock setup by _make_coordinator with a proper one
    client = AsyncMock()
    client.get_devices = AsyncMock(return_value=FAKE_DEVICES_LIST)
    coordinator._get_client = AsyncMock(return_value=client)

    with (
        patch.object(
            coordinator,
            "_discover_devices",
            return_value=FAKE_DEVICES_LIST,
        ),
        patch.object(
            coordinator,
            "_fetch_single_device",
            return_value=_build_device_snapshot(
                "iot-001", "T1 Plus", FAKE_DEVDATA, {}, 1730000000
            ),
        ),
    ):
        data = await coordinator.async_update_data()
        assert "iot-001" in data
        assert data["iot-001"].device_name == "T1 Plus"


async def test_coordinator_session_expired(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_get_shared_api: MagicMock,
) -> None:
    """Test that session expiry triggers reconnection."""
    coordinator = _make_coordinator(hass, mock_config_entry)

    with (
        patch.object(
            coordinator,
            "_discover_devices",
            side_effect=NeakasaApiClientSessionExpiredError("expired"),
        ),
        patch.object(
            coordinator,
            "_reconnect_and_retry",
            return_value={"iot-001": MagicMock()},
        ) as retry,
    ):
        data = await coordinator.async_update_data()
        retry.assert_awaited_once()
        assert "iot-001" in data


async def test_coordinator_auth_error_reauth(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_get_shared_api: MagicMock,
) -> None:
    """Test that persistent auth errors trigger reauth."""
    coordinator = _make_coordinator(hass, mock_config_entry)
    # mock_config_entry must have entry_id accessible as a real string
    mock_config_entry.entry_id = "mock-entry-id"
    mock_config_entry.async_start_reauth = AsyncMock()

    with (
        patch.object(
            coordinator,
            "_discover_devices",
            side_effect=NeakasaApiClientAuthenticationError("bad password"),
        ),
        patch.object(
            coordinator,
            "_reconnect_and_retry",
            side_effect=UpdateFailed("reconnect failed"),
        ),
        pytest.raises(UpdateFailed),
    ):
        await coordinator.async_update_data()


async def test_set_property(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_get_shared_api: MagicMock,
) -> None:
    """Test setting a device property."""
    coordinator = _make_coordinator(hass, mock_config_entry)
    client = AsyncMock()
    client.set_device_properties = AsyncMock()
    coordinator._get_client = AsyncMock(return_value=client)

    # Set coordinator data so property write path works
    snap = _build_device_snapshot("iot-001", "T1 Plus", FAKE_DEVDATA, {}, 1730000000)
    coordinator.data = {"iot-001": snap}

    await coordinator.set_property("iot-001", "child_lock", 1)
    client.set_device_properties.assert_awaited_once()


async def test_invoke_service(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_get_shared_api: MagicMock,
) -> None:
    """Test invoking a clean/level service."""
    coordinator = _make_coordinator(hass, mock_config_entry)
    client = AsyncMock()
    client.clean_now = AsyncMock()
    client.sand_leveling = AsyncMock()
    coordinator._get_client = AsyncMock(return_value=client)

    await coordinator.invoke_service("iot-001", "clean")
    client.clean_now.assert_awaited_once_with("iot-001")

    await coordinator.invoke_service("iot-001", "level")
    client.sand_leveling.assert_awaited_once_with("iot-001")

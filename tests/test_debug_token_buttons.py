"""Tests for the temporary token debug buttons (remove with them)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant

from custom_components.neakasa.api import NeakasaAPI
from custom_components.neakasa.api_client import NeakasaApiClient
from custom_components.neakasa.coordinator import (
    DEBUG_TOKEN_CHURN_CYCLES,
    NeakasaCoordinator,
)
from custom_components.neakasa.exceptions import (
    NeakasaApiClientSessionExpiredError,
)


def _api_with_tokens() -> MagicMock:
    """A legacy API object holding both tokens."""
    api = NeakasaAPI(MagicMock())
    api._iot_token = "good-iot"
    api._encryption._token = "good-account"
    return api


async def test_debug_invalidate_breaks_both_tokens() -> None:
    """The debug tool makes the account and the IoT tokens unusable."""
    api = _api_with_tokens()
    client = NeakasaApiClient(api)
    await client.debug_invalidate_tokens()
    assert api._iot_token == "invalid"
    assert api._encryption._token == "invalid"


async def test_debug_churn_signs_in_the_configured_number_of_times(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
) -> None:
    """One press costs the same as the same number of natural expiries."""
    coordinator = NeakasaCoordinator(hass, mock_config_entry)
    coordinator._get_client = AsyncMock()
    with patch(
        "custom_components.neakasa.coordinator.force_reconnect_api",
        new=AsyncMock(),
    ) as reconnect:
        await coordinator.debug_token_churn()
    assert reconnect.await_count == DEBUG_TOKEN_CHURN_CYCLES


async def test_debug_invalidate_is_repaired_by_the_next_scan(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
) -> None:
    """A scan broken for its token goes to the session-recovery path."""
    coordinator = NeakasaCoordinator(hass, mock_config_entry)
    client = AsyncMock()
    client.debug_invalidate_tokens = AsyncMock()
    client.get_records = AsyncMock(
        side_effect=[
            NeakasaApiClientSessionExpiredError("TokenInvalid\ufffatoken is abnormal"),
            {"cat_list": [], "record_list": []},
        ]
    )
    client.get_devices = AsyncMock(
        return_value=[
            {
                "iotId": "iot-001",
                "deviceName": "T1 Plus",
                "categoryKey": "CatLitter",
                "productKey": "a1nNMMJkLqG",
            }
        ]
    )
    client.get_device_properties = AsyncMock(return_value={})
    coordinator._get_client = AsyncMock(return_value=client)
    await coordinator.debug_invalidate_tokens()

    with patch(
        "custom_components.neakasa.coordinator.force_reconnect_api",
        new=AsyncMock(),
    ) as reconnect:
        payload = await coordinator.async_update_data()

    assert "iot-001" in payload
    reconnect.assert_awaited_once()
    assert client.refresh_session.call_count == 0

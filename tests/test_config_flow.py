"""Tests for config_flow.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.neakasa.const import DOMAIN

FAKE_USERNAME = "test@example.com"
FAKE_PASSWORD = "hunter2"

FAKE_DEVICES = [
    {
        "iotId": "iot-001",
        "deviceName": "T1 Plus",
        "categoryKey": "CatLitter",
    }
]


async def test_flow_show_form(hass: HomeAssistant) -> None:
    """Test that the user step shows the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_flow_success(
    hass: HomeAssistant,
    mock_get_shared_api: MagicMock,
) -> None:
    """Test successful config flow creates entry."""
    with (
        patch(
            "custom_components.neakasa.config_flow.NeakasaAPI",
            autospec=True,
        ) as mock_api_cls,
        patch(
            "custom_components.neakasa.config_flow.NeakasaApiClient",
        ) as mock_client_cls,
    ):
        mock_api = mock_api_cls.return_value
        mock_api.connect = AsyncMock()

        client = mock_client_cls.return_value
        client.get_devices = AsyncMock(return_value=FAKE_DEVICES)

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        assert result["type"] is FlowResultType.FORM

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: FAKE_USERNAME, CONF_PASSWORD: FAKE_PASSWORD},
        )
        assert result2["type"] is FlowResultType.CREATE_ENTRY
        assert result2["title"] == f"Neakasa ({FAKE_USERNAME})"


async def test_flow_abort_duplicate(
    hass: HomeAssistant,
    mock_get_shared_api: MagicMock,
) -> None:
    """Test that a duplicate config entry is aborted."""
    # Create a first entry so the second one gets aborted
    with (
        patch(
            "custom_components.neakasa.config_flow.NeakasaAPI",
            autospec=True,
        ) as mock_api_cls,
        patch(
            "custom_components.neakasa.config_flow.NeakasaApiClient",
        ) as mock_client_cls,
    ):
        mock_api = mock_api_cls.return_value
        mock_api.connect = AsyncMock()

        client = mock_client_cls.return_value
        client.get_devices = AsyncMock(return_value=FAKE_DEVICES)

        # First flow: create entry
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: FAKE_USERNAME, CONF_PASSWORD: FAKE_PASSWORD},
        )
        assert result2["type"] is FlowResultType.CREATE_ENTRY

        # Second flow: should abort as duplicate
        result3 = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"],
            {CONF_USERNAME: FAKE_USERNAME, CONF_PASSWORD: FAKE_PASSWORD},
        )
        assert result4["type"] is FlowResultType.ABORT


async def test_reauth_flow() -> None:
    """Test that the config flow handler has reauth support."""
    from custom_components.neakasa.config_flow import NeakasaConfigFlow

    # Verify the flow handler defines the reauth step
    assert hasattr(NeakasaConfigFlow, "async_step_reauth")
    assert hasattr(NeakasaConfigFlow, "async_step_reauth_confirm")

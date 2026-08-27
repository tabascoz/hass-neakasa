"""Tests for __init__.py — integration setup/teardown."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from homeassistant.core import HomeAssistant

from custom_components.neakasa import PLATFORMS, async_setup_entry, async_unload_entry


async def test_platforms_present() -> None:
    """Verify we register all expected platforms."""
    for platform_name in ("sensor", "binary_sensor", "switch", "button"):
        assert any(p.value == platform_name for p in PLATFORMS), (
            f"Missing platform: {platform_name}"
        )


async def test_async_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_get_shared_api: MagicMock,
) -> None:
    """Test that setup_entry creates coordinator and forwards platforms."""
    with (
        patch(
            "custom_components.neakasa.NeakasaCoordinator",
            autospec=True,
        ) as mock_coord_cls,
        patch.object(hass.config_entries, "async_forward_entry_setups") as fwd,
    ):
        mock_coordinator = mock_coord_cls.return_value
        mock_coordinator.async_config_entry_first_refresh.return_value = None

        result = await async_setup_entry(hass, mock_config_entry)
        assert result is True
        mock_coordinator.async_config_entry_first_refresh.assert_awaited_once()
        fwd.assert_awaited_once()


async def test_async_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
) -> None:
    """Test that unload_entry unloads platforms and clears shared API."""
    with (
        patch.object(
            hass.config_entries, "async_unload_platforms", return_value=True
        ) as unload,
        patch("custom_components.neakasa.clear_shared_api") as clear_api,
    ):
        result = await async_unload_entry(hass, mock_config_entry)
        assert result is True
        unload.assert_awaited_once()
        clear_api.assert_called_once()

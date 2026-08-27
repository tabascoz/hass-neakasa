"""Neakasa integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    Platform,
)

from .api_manager import clear_shared_api
from .const import _LOGGER
from .coordinator import NeakasaCoordinator
from .data import NeakasaConfigEntry, NeakasaData

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.BUTTON,
]


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """
    Migrate config entry from VERSION 1 → 2.

    V1 entries stored ``device_id``, ``friendly_name``, ``username``, ``password``
    in data and used the device IOT ID as the unique_id.  V2 keeps only
    ``username`` + ``password`` and uses ``account:{username}`` as the unique_id.
    """
    if config_entry.version == 1:
        _LOGGER.debug("Migrating config entry %s from V1 to V2", config_entry.entry_id)

        username = config_entry.data[CONF_USERNAME]
        password = config_entry.data[CONF_PASSWORD]

        new_data = {
            CONF_USERNAME: username,
            CONF_PASSWORD: password,
        }
        new_unique_id = f"account:{username.lower()}"

        hass.config_entries.async_update_entry(
            config_entry,
            data=new_data,
            unique_id=new_unique_id,
            version=2,
        )
        _LOGGER.debug("Migrated config entry %s to V2", config_entry.entry_id)
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Neakasa Integration from a config entry."""
    entry = cast("NeakasaConfigEntry", config_entry)

    coordinator = NeakasaCoordinator(hass, config_entry)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = NeakasaData(coordinator=coordinator)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def _async_update_listener(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Handle config options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    entry = cast("NeakasaConfigEntry", config_entry)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        coordinator = entry.runtime_data.coordinator
        clear_shared_api(coordinator.username, coordinator.password)

    return unload_ok

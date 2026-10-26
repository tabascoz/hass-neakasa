"""Neakasa integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import callback
from homeassistant.helpers.device_registry import (
    async_entries_for_config_entry,
)
from homeassistant.helpers.device_registry import (
    async_get as get_device_registry,
)

from .api_manager import clear_shared_api
from .const import _LOGGER, DOMAIN
from .coordinator import NeakasaCoordinator
from .data import NeakasaConfigEntry, NeakasaData
from .log_redact import entry_label

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.device_registry import DeviceEntry

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.TEXT,
]


def _current_identifiers(
    config_entry: ConfigEntry, coordinator: NeakasaCoordinator
) -> set[tuple[str, str]]:
    """
    Return the device identifiers this entry describes now.

    The account device is named by the config entry, not by the credentials,
    so reconfiguring the entry to another Neakasa account describes the same
    device. The machines are named by their iotId, which the account sharing
    keeps the same, so their entities and ids survive a reconfiguration.
    """
    identifiers = {(DOMAIN, f"account:{config_entry.entry_id}")}
    identifiers |= {(DOMAIN, iot_id) for iot_id in coordinator.data}
    return identifiers


@callback
def _prune_devices_this_entry_no_longer_describes(
    hass: HomeAssistant, config_entry: ConfigEntry, coordinator: NeakasaCoordinator
) -> None:
    """
    Forget the devices this entry created and no longer describes.

    Home Assistant keeps devices in the registry once they exist. When the
    entry is set up again with other credentials, the account device from
    before would otherwise stay, shown with an entity that can only be
    unavailable; a device taken off the account would stay too. Only
    devices belonging to this entry are considered.

    The enumeration has to be the one keyed by the config entry: `async_get_devices`
    with no filters walks only the identifier and connection indexes
    (`helpers/device_registry.py:1176 get_entries`), so it returned nothing
    and nothing was ever forgotten - the unit carried two account devices from
    earlier credentials for the whole of 2026-10-26. `async_entries_for_config_entry`
    walks the index that is always present.
    """
    current = _current_identifiers(config_entry, coordinator)
    registry = get_device_registry(hass)
    for device in async_entries_for_config_entry(registry, config_entry.entry_id):
        if device.identifiers & current:
            continue
        _LOGGER.info(
            "Forgetting device %s: this entry no longer describes it",
            device.name or device.id,
        )
        registry.async_remove_device(device.id)


async def async_remove_config_entry_device(
    hass: HomeAssistant,  # noqa: ARG001 - required by Home Assistant's hook
    config_entry: ConfigEntry,
    device_entry: DeviceEntry,
) -> bool:
    """Allow HA to drop a device this entry no longer describes."""
    entry = cast("NeakasaConfigEntry", config_entry)
    if entry.runtime_data is None:
        return True
    return not bool(
        device_entry.identifiers
        & _current_identifiers(config_entry, entry.runtime_data.coordinator)
    )


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """
    Migrate config entry from VERSION 1 → 2.

    V1 entries stored ``device_id``, ``friendly_name``, ``username``, ``password``
    in data and used the device IOT ID as the unique_id.  V2 keeps only
    ``username`` + ``password`` and uses ``account:{username}`` as the unique_id.
    """
    if config_entry.version == 1:
        _LOGGER.debug(
            "Migrating config entry %s from V1 to V2",
            entry_label(config_entry.entry_id),
        )

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
        _LOGGER.debug(
            "Migrated config entry %s to V2", entry_label(config_entry.entry_id)
        )
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Neakasa Integration from a config entry."""
    entry = cast("NeakasaConfigEntry", config_entry)

    coordinator = NeakasaCoordinator(hass, config_entry)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = NeakasaData(coordinator=coordinator)
    _prune_devices_this_entry_no_longer_describes(hass, config_entry, coordinator)

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

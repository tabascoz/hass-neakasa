"""Binary sensor platform for Neakasa."""

from __future__ import annotations

from typing import cast

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON, STATE_OFF
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .data import NeakasaConfigEntry
from .const import DOMAIN, _LOGGER
from .coordinator import NeakasaCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors for all discovered devices."""
    entry = cast(NeakasaConfigEntry, config_entry)
    coordinator: NeakasaCoordinator = entry.runtime_data.coordinator

    @callback
    def _discover() -> None:
        entities: list = []
        for iot_id, snap in coordinator.data.items():
            device_info = DeviceInfo(
                name=snap.device_name,
                manufacturer="Neakasa",
                identifiers={(DOMAIN, iot_id)},
            )
            entities.append(
                NeakasaBinarySensor(coordinator, device_info, iot_id, translation="bin_full", key="bin_full", icon="mdi:delete-empty"),
            )
        async_add_entities(entities)

    _discover()
    config_entry.async_on_unload(coordinator.async_add_listener(_discover))


class NeakasaBinarySensor(CoordinatorEntity[NeakasaCoordinator], BinarySensorEntity):

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, coordinator: NeakasaCoordinator, deviceinfo: DeviceInfo, iot_id: str, translation: str, key: str, icon: str = None, visible: bool = True) -> None:
        super().__init__(coordinator)
        self._iot_id = iot_id
        self._data_key = key
        self.device_info = deviceinfo
        self.translation_key = translation
        self.entity_registry_enabled_default = visible
        self._attr_unique_id = f"{iot_id}-{translation}"
        if icon is not None:
            self._attr_icon = icon

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        snap = self.coordinator.device_snapshot(self._iot_id)
        if snap is None:
            return False
        return bool(getattr(snap, self._data_key))

    @property
    def state(self):
        return STATE_ON if self.is_on else STATE_OFF

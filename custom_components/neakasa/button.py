"""Button platform for Neakasa."""

from __future__ import annotations

from typing import cast

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
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
    """Set up buttons for all discovered devices."""
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
            entities.extend([
                NeakasaButton(coordinator, device_info, iot_id, translation="clean", service="clean"),
                NeakasaButton(coordinator, device_info, iot_id, translation="level", service="level"),
            ])
        async_add_entities(entities)

    _discover()
    config_entry.async_on_unload(coordinator.async_add_listener(_discover))


class NeakasaButton(CoordinatorEntity[NeakasaCoordinator], ButtonEntity):

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, coordinator: NeakasaCoordinator, deviceinfo: DeviceInfo, iot_id: str, translation: str, service: str, icon: str = None, visible: bool = True) -> None:
        super().__init__(coordinator)
        self._iot_id = iot_id
        self._service_key = service
        self.device_info = deviceinfo
        self.translation_key = translation
        self.entity_registry_enabled_default = visible
        self._attr_unique_id = f"{iot_id}-{translation}"
        if icon is not None:
            self._attr_icon = icon

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()

    async def async_press(self) -> None:
        await self.coordinator.invoke_service(self._iot_id, self._service_key)

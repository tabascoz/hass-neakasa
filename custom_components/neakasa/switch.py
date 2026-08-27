"""Switch platform for Neakasa."""

from __future__ import annotations

from typing import cast

from homeassistant.components.switch import SwitchEntity
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
    """Set up switches for all discovered devices."""
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
                NeakasaSwitch(coordinator, device_info, iot_id, translation="auto_clean", key="clean_cfg", subkey="active", icon="mdi:vacuum"),
                NeakasaSwitch(coordinator, device_info, iot_id, translation="young_cat_mode", key="young_cat_mode", visible=False, icon="mdi:cat"),
                NeakasaSwitch(coordinator, device_info, iot_id, translation="child_lock", key="child_lock", icon="mdi:lock-alert"),
                NeakasaSwitch(coordinator, device_info, iot_id, translation="auto_bury", key="auto_bury", icon="mdi:window-closed"),
                NeakasaSwitch(coordinator, device_info, iot_id, translation="auto_level", key="auto_level", icon="mdi:spirit-level"),
                NeakasaSwitch(coordinator, device_info, iot_id, translation="silent_mode", key="silent_mode", icon="mdi:volume-off"),
                NeakasaSwitch(coordinator, device_info, iot_id, translation="auto_recovery", key="auto_force_init", visible=False, icon="mdi:alert-outline"),
                NeakasaSwitch(coordinator, device_info, iot_id, translation="unstoppable_cycle", key="b_intrpt_range_det", icon="mdi:cached"),
            ])
        async_add_entities(entities)

    _discover()
    config_entry.async_on_unload(coordinator.async_add_listener(_discover))


class NeakasaSwitch(CoordinatorEntity[NeakasaCoordinator], SwitchEntity):

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, coordinator: NeakasaCoordinator, deviceinfo: DeviceInfo, iot_id: str, translation: str, key: str, subkey: str = None, icon: str = None, visible: bool = True) -> None:
        super().__init__(coordinator)
        self._iot_id = iot_id
        self._data_key = key
        self._data_subkey = subkey
        self.device_info = deviceinfo
        self.translation_key = translation
        self.entity_registry_enabled_default = visible
        self._attr_unique_id = f"{iot_id}-{translation}"
        if icon is not None:
            self._attr_icon = icon

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs):
        await self._set_state(1)

    async def async_turn_off(self, **kwargs):
        await self._set_state(0)

    async def _set_state(self, state: int):
        if self._data_subkey is None:
            await self.coordinator.set_property(self._iot_id, self._data_key, state)
            return
        snap = self.coordinator.device_snapshot(self._iot_id)
        value = dict(getattr(snap, self._data_key, {}) or {})
        value[self._data_subkey] = state
        await self.coordinator.set_property(self._iot_id, self._data_key, value)

    @property
    def is_on(self) -> bool:
        snap = self.coordinator.device_snapshot(self._iot_id)
        if snap is None:
            return False
        value = getattr(snap, self._data_key, None)
        if self._data_subkey is None:
            return bool(value)
        if not isinstance(value, dict):
            return False
        return bool(value.get(self._data_subkey, False))

    @property
    def state(self):
        return STATE_ON if self.is_on else STATE_OFF

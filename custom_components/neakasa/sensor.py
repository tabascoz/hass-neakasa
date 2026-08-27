"""Sensor platform for Neakasa."""

from __future__ import annotations

from datetime import datetime
from typing import cast

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS,
    UnitOfTime,
    EntityCategory,
    UnitOfMass,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .data import NeakasaConfigEntry
from .const import DOMAIN, _LOGGER
from .coordinator import NeakasaCoordinator, NeakasaDeviceSnapshot


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors for all discovered devices."""
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
                NeakasaSensor(coordinator, device_info, iot_id, translation="sand_percent", key="sand_level_percent", unit=PERCENTAGE),
                NeakasaSensor(coordinator, device_info, iot_id, translation="wifi_rssi", key="wifi_rssi", unit=SIGNAL_STRENGTH_DECIBELS, visible=False, category=EntityCategory.DIAGNOSTIC, icon="mdi:wifi"),
                NeakasaSensor(coordinator, device_info, iot_id, translation="stay_time", key="stay_time", unit=UnitOfTime.SECONDS, visible=False),
                NeakasaTimestampSensor(coordinator, device_info, iot_id, translation="last_usage", key="last_use"),
                NeakasaMapSensor(coordinator, device_info, iot_id, translation="current_status", key="bucket_status", options=["idle", "cleaning", "cleaning", "leveling", "flipover", "cat_present", "paused", "side_bin_locking_panels_missing", None, "cleaning_interrupted"], icon="mdi:state-machine"),
                NeakasaMapSensor(coordinator, device_info, iot_id, translation="sand_state", key="sand_level_state", options=["insufficient", "moderate", "sufficient", "overfilled"]),
                NeakasaMapSensor(coordinator, device_info, iot_id, translation="bin_state", key="room_of_bin", options=["normal", "full", "missing"], icon="mdi:delete"),
            ])
            for cat in snap.cat_list:
                entities.append(
                    NeakasaCatSensor(coordinator, device_info, iot_id, catName=cat["name"], catId=cat["id"], icon="mdi:cat"),
                )
        async_add_entities(entities)

    _discover()
    config_entry.async_on_unload(coordinator.async_add_listener(_discover))


class NeakasaCatSensor(CoordinatorEntity[NeakasaCoordinator]):

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, coordinator: NeakasaCoordinator, deviceinfo: DeviceInfo, iot_id: str, catName: str, catId: str, icon: str = None, visible: bool = True, category: str = None) -> None:
        super().__init__(coordinator)
        self._iot_id = iot_id
        self._catId = catId
        self.device_info = deviceinfo
        self.entity_registry_enabled_default = visible
        self._attr_translation_key = "cat_sensor"
        self._attr_translation_placeholders = {"name": catName}
        self._attr_unique_id = f"{iot_id}-cat-{catId}"
        self._attr_unit_of_measurement = UnitOfMass.KILOGRAMS
        if icon is not None:
            self._attr_icon = icon
        if category is not None:
            self._attr_entity_category = category

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()

    @property
    def _snap(self) -> NeakasaDeviceSnapshot | None:
        return self.coordinator.device_snapshot(self._iot_id)

    @property
    def _records(self):
        snap = self._snap
        if snap is None:
            return []
        return [r for r in snap.record_list if r.get("cat_id") == self._catId]

    @property
    def native_value(self):
        records = self._records
        if not records:
            return 0
        return records[0]["weight"]

    @property
    def extra_state_attributes(self):
        records = self._records
        if not records:
            return {}
        last = records[0]
        return {
            "state_class": SensorStateClass.MEASUREMENT,
            "start_time": datetime.fromtimestamp(last["start_time"]),
            "end_time": datetime.fromtimestamp(last["end_time"]),
        }


class NeakasaSensor(CoordinatorEntity[NeakasaCoordinator]):

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, coordinator: NeakasaCoordinator, deviceinfo: DeviceInfo, iot_id: str, translation: str, key: str, unit: str, icon: str = None, visible: bool = True, category: str = None) -> None:
        super().__init__(coordinator)
        self._iot_id = iot_id
        self._data_key = key
        self.device_info = deviceinfo
        self.translation_key = translation
        self.entity_registry_enabled_default = visible
        self._attr_unique_id = f"{iot_id}-{translation}"
        self._attr_unit_of_measurement = unit
        if icon is not None:
            self._attr_icon = icon
        if category is not None:
            self._attr_entity_category = category

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()

    @property
    def native_value(self):
        snap = self.coordinator.device_snapshot(self._iot_id)
        if snap is None:
            return None
        return getattr(snap, self._data_key)

    @property
    def extra_state_attributes(self):
        return {"state_class": SensorStateClass.MEASUREMENT}


class NeakasaMapSensor(CoordinatorEntity[NeakasaCoordinator]):

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, coordinator: NeakasaCoordinator, deviceinfo: DeviceInfo, iot_id: str, translation: str, key: str, options: list, icon: str = None, visible: bool = True) -> None:
        super().__init__(coordinator)
        self._iot_id = iot_id
        self._data_key = key
        self._options = options
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
    def native_value(self):
        snap = self.coordinator.device_snapshot(self._iot_id)
        if snap is None:
            return None
        raw = getattr(snap, self._data_key)
        if raw >= len(self._options):
            return raw
        value = self._options[raw]
        return raw if value is None else value


class NeakasaTimestampSensor(CoordinatorEntity[NeakasaCoordinator]):

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TIMESTAMP

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
    def native_value(self):
        snap = self.coordinator.device_snapshot(self._iot_id)
        if snap is None:
            return None
        raw = getattr(snap, self._data_key)
        if not raw:
            return None
        try:
            return datetime.fromtimestamp(raw / 1000)
        except (TypeError, ValueError):
            return None

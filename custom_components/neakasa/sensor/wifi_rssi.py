"""Sensor for WiFi RSSI."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.const import SIGNAL_STRENGTH_DECIBELS, EntityCategory
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..coordinator import NeakasaCoordinator, NeakasaDeviceSnapshot

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceInfo


class NeakasaWifiRssiSensor(CoordinatorEntity[NeakasaCoordinator], SensorEntity):
    """WiFi signal strength in dBm."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "wifi_rssi"
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_icon = "mdi:wifi"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: NeakasaCoordinator,
        device_info: DeviceInfo,
        iot_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._iot_id = iot_id
        self.device_info = device_info
        self._attr_unique_id = f"{iot_id}-wifi_rssi"

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Update entity state from coordinator data."""
        if self.entity_id is None:
            return
        self._handle_coordinator_update()

    async def async_added_to_hass(self) -> None:
        """Write initial state once entity_id is assigned."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    @property
    def _snap(self) -> NeakasaDeviceSnapshot | None:
        return self.coordinator.device_snapshot(self._iot_id)

    @property
    def native_value(self) -> int | None:
        """Return the WiFi RSSI value."""
        snap = self._snap
        if snap is None:
            return None
        return snap.wifi_rssi

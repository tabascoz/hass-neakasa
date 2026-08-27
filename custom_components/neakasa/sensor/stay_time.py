"""Sensor for last cat stay duration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.const import UnitOfTime
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..coordinator import NeakasaCoordinator, NeakasaDeviceSnapshot

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceInfo


class NeakasaStayTimeSensor(CoordinatorEntity[NeakasaCoordinator], SensorEntity):
    """Duration of the last cat visit in seconds."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "stay_time"
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_entity_registry_enabled_default = False
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
        self._attr_unique_id = f"{iot_id}-stay_time"

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
        """Return the stay time in seconds."""
        snap = self._snap
        if snap is None:
            return None
        return snap.stay_time

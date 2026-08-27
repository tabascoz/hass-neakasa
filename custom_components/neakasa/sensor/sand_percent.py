"""Sensor for cat litter fill percentage."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import PERCENTAGE
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..coordinator import NeakasaCoordinator, NeakasaDeviceSnapshot

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceInfo


class NeakasaSandPercentSensor(CoordinatorEntity[NeakasaCoordinator]):
    """Cat litter fill level as a percentage."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "sand_percent"
    _attr_native_unit_of_measurement = PERCENTAGE

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
        self._attr_unique_id = f"{iot_id}-sand_percent"

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()

    @property
    def _snap(self) -> NeakasaDeviceSnapshot | None:
        return self.coordinator.device_snapshot(self._iot_id)

    @property
    def native_value(self) -> int | None:
        """Return the sand level percentage."""
        snap = self._snap
        if snap is None:
            return None
        return snap.sand_level_percent

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return additional state attributes."""
        return {"state_class": SensorStateClass.MEASUREMENT}

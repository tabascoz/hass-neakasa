"""Sensor for individual cat weight measurements."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import UnitOfMass
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..coordinator import NeakasaCoordinator, NeakasaDeviceSnapshot

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceInfo


class NeakasaCatWeightSensor(CoordinatorEntity[NeakasaCoordinator]):
    """Weight measurement for a specific cat."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "cat_sensor"
    _attr_native_unit_of_measurement = UnitOfMass.KILOGRAMS

    def __init__(
        self,
        coordinator: NeakasaCoordinator,
        device_info: DeviceInfo,
        iot_id: str,
        cat_name: str,
        cat_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._iot_id = iot_id
        self._cat_id = cat_id
        self.device_info = device_info
        self._attr_translation_placeholders = {"name": cat_name}
        self._attr_unique_id = f"{iot_id}-cat-{cat_id}"

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()

    @property
    def _snap(self) -> NeakasaDeviceSnapshot | None:
        return self.coordinator.device_snapshot(self._iot_id)

    @property
    def _records(self) -> list[dict]:
        snap = self._snap
        if snap is None:
            return []
        return [r for r in snap.record_list if r.get("cat_id") == self._cat_id]

    @property
    def native_value(self) -> float:
        """Return the most recent weight measurement."""
        records = self._records
        if not records:
            return 0
        return records[0]["weight"]

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional state attributes for the cat."""
        records = self._records
        if not records:
            return {}
        last = records[0]
        return {
            "state_class": SensorStateClass.MEASUREMENT,
            "start_time": datetime.fromtimestamp(last["start_time"], tz=UTC),
            "end_time": datetime.fromtimestamp(last["end_time"], tz=UTC),
        }

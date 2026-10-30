"""Sensor for the solid grams of food the machine served today."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..base_entity import write_state_if_changed
from ..coordinator import NeakasaCoordinator, NeakasaDeviceSnapshot

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceInfo


class NeakasaFoodIntakeTodaySolidsSensor(
    CoordinatorEntity[NeakasaCoordinator], SensorEntity
):
    """
    The solid half of what this machine served today.

    The machine's meal rows name the ground food and the watered food apart, so
    this is one side of the total the day figure shows. A day with no recorded
    meal states no number rather than a guessed zero.
    """

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "food_intake_today_solids"
    _attr_icon = "mdi:food"
    _attr_native_unit_of_measurement = "g"
    _attr_suggested_unit_of_measurement = "g"
    _attr_entity_registry_enabled_default = False

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
        self._attr_unique_id = f"{iot_id}-food_intake_today_solids"

    @callback
    def _handle_coordinator_update(self) -> None:
        write_state_if_changed(self, self._iot_id)

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
        """Return the solid grams served today, or None when none were stated."""
        snap = self._snap
        if snap is None:
            return None
        return snap.feed_today_solids_g

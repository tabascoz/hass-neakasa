"""Sensor for when the food bin was last marked clean."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..base_entity import write_state_if_changed
from ..coordinator import NeakasaCoordinator, NeakasaDeviceSnapshot

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceInfo


class NeakasaFoodBinCleanSensor(CoordinatorEntity[NeakasaCoordinator], SensorEntity):
    """
    The last time the food bin was marked clean.

    The machine's definition offers the record, this unit has never answered
    with one, so the value stays unknown until a mark is written.
    """

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "food_bin_clean"
    _attr_icon = "mdi:container-outline"

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
        self._attr_unique_id = f"{iot_id}-food_bin_clean"

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
    def native_value(self) -> str | None:
        """Return what the machine recorded as the last cleaning, or None."""
        snap = self._snap
        if snap is None:
            return None
        return snap.last_food_bin_clean

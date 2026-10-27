"""Sensor for the bowl's actual weight as the machine's scale reads it."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..base_entity import write_state_if_changed
from ..coordinator import NeakasaCoordinator, NeakasaDeviceSnapshot

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceInfo


class NeakasaBowlWeightSensor(CoordinatorEntity[NeakasaCoordinator], SensorEntity):
    """
    Grams on the feeder's own scale, including the bowl it is weighing.

    The number is what the cloud holds for the machine's scale, and that copy is
    only as fresh as the machine's last push of that key - asking the cloud does
    not refresh it - so the reading's own age travels with it in
    `extra_state_attributes`: `scale_state_as_of` names the moment the machine
    stated it and `scale_state_age_minutes` says how long ago that was, beside
    the raw reading, the bowl's weight the machine states and whether the bowl is
    in place. A reading two days old is shown as such rather than as the present.
    """

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "bowl_weight"
    _attr_icon = "mdi:scale"
    _attr_native_unit_of_measurement = "g"
    _attr_suggested_unit_of_measurement = "g"

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
        self._attr_unique_id = f"{iot_id}-bowl_weight"

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
    def extra_state_attributes(self) -> dict[str, Any]:
        """The reading's age and the parts it is made of, so it can be checked."""
        return self.coordinator.scale_state_evidence(self._iot_id)

    @property
    def native_value(self) -> int | None:
        """Return the grams the scale reads, or None when it does not report."""
        snap = self._snap
        if snap is None:
            return None
        return snap.bowl_weight_g

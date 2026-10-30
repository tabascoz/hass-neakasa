"""Sensor for the grams of food the machine served today."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..base_entity import write_state_if_changed
from ..coordinator import NeakasaCoordinator, NeakasaDeviceSnapshot

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceInfo


class NeakasaFoodIntakeTodaySensor(CoordinatorEntity[NeakasaCoordinator], SensorEntity):
    """
    Grams of food this machine served today, solid and liquid together.

    A pet feeder keeps its own meal rows and no key on the device states a day
    total, so the rows are added up here for the day Home Assistant itself runs.
    A day with no recorded meal states no number rather than a guessed zero.
    The meals the figure groups - each naming its own moment - and the moment the
    rows were asked for stay in `extra_state_attributes`, so a figure can be
    traced to the meals that made it rather than read as the present.
    """

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "food_intake_today"
    _attr_icon = "mdi:food"
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
        self._attr_unique_id = f"{iot_id}-food_intake_today"

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
        """The meals grouped into the figure, and when their rows were asked."""
        return self.coordinator.served_today_evidence(self._iot_id)

    @property
    def native_value(self) -> int | None:
        """
        Return the grams served today, or None when none were recorded.

        The two halves are what the machine's rows state - `feed_weight` ground
        out and `water_weight` watered - and the total is their sum, the figure
        the product's own day panel prints beside that pair.
        """
        snap = self._snap
        if snap is None:
            return None
        solids = snap.feed_today_solids_g
        liquid = snap.feed_today_liquid_g
        if solids is None or liquid is None:
            return None
        return solids + liquid

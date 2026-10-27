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
    Grams of contents in the bowl, from the machine's own scale and tare.

    The scale answers in two ways, and both are kept apart. The cloud's copy of
    `bowlStatus` only repeats what the machine last reported, so it carries its
    own moment and age; the definition's 称重 read (`iotRead` with the weighing
    type) is asked once a scan and answers with a reading that moves, beside the
    tare the same answer states. The published figure is the difference clamped
    at zero, preferring the answer that was taken more recently, which is what
    the Neakasa app shows for the same bowl. Both answers and both moments stay
    in `extra_state_attributes`, so a figure can be traced to the call that made
    it rather than read as the present.
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
        """Both answers the scale can give, each with the moment it was stated."""
        return {
            **self.coordinator.scale_state_evidence(self._iot_id),
            **self.coordinator.live_scale_evidence(self._iot_id),
        }

    @property
    def native_value(self) -> int | None:
        """
        Return what the bowl holds, or None when the scale gives no answer.

        The scale's number includes the bowl, and the machine states the bowl's
        own tare beside it - either in the same report or in the same reply -
        so the contents are the difference clamped at zero: this unit's 89.08 g
        reading above its 68 g tare is 21 g, the figure the app shows for the
        bowl. The live answer is asked for each scan and is the more recent
        claim, so it wins; with no live answer the stored copy is used, and the
        attributes say which of the two and when it was stated. With no tare in
        either answer there is nothing to take away, so the raw reading is what
        is shown.
        """
        snap = self._snap
        if snap is None:
            return None
        if snap.scale_live_g is not None:
            tare = (
                snap.scale_live_tare_g
                if snap.scale_live_tare_g is not None
                else snap.bowl_tare_g
            )
            if tare is None:
                return round(snap.scale_live_g)
            return max(0, round(snap.scale_live_g - tare))
        if snap.bowl_weight_g is None:
            return None
        if snap.bowl_tare_g is None:
            return snap.bowl_weight_g
        return max(0, snap.bowl_weight_g - snap.bowl_tare_g)

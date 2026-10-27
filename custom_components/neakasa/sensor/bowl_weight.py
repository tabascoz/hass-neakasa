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

    The scale states one weight that includes the bowl, and the machine states
    the bowl's tare beside it, so the value published is the difference clamped
    at zero - what the app shows for the same bowl. The raw reading and the
    tare are not hidden: they travel in `extra_state_attributes` with
    `scale_state_as_of` and `scale_state_age_minutes`, because the cloud only
    holds the state the machine last pushed for that key and asking it changes
    nothing - this unit's copy kept the same value and stamp for two days.
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
        """
        Return what the bowl holds, or None when the scale does not report.

        The scale's number includes the bowl (`curWeight`, 67 g observed here)
        and the machine states the bowl's own tare beside it (`bowlGram`, 68 g
        observed here), so the contents are the difference clamped at zero -
        the scale sits a gram light, and an empty bowl is empty rather than
        negative. That is the figure the Neakasa app shows for the same bowl.
        With no tare stated there is nothing to subtract, so the raw reading is
        what is shown; both parts and the moment they were stated are in
        `extra_state_attributes` either way.
        """
        snap = self._snap
        if snap is None or snap.bowl_weight_g is None:
            return None
        if snap.bowl_tare_g is None:
            return snap.bowl_weight_g
        return max(0, snap.bowl_weight_g - snap.bowl_tare_g)

"""Sensor for how the machine says its battery is fitted."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..base_entity import write_state_if_changed
from ..coordinator import NeakasaCoordinator, NeakasaDeviceSnapshot

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceInfo

# The battery states the definition spells inside `pwrStatus.batStatus`: 不在位
# (not fitted), 充电中 (being charged), 使用中 (in use). This unit answered 2,
# so "in use" is the only one observed here; the other two are the definition's.
_FIT_OPTIONS = ["not_fitted", "charging", "in_use"]


class NeakasaBatteryStateSensor(CoordinatorEntity[NeakasaCoordinator], SensorEntity):
    """
    How the feeder says its battery is fitted, as its own key states.

    The percent the battery sensor shows and this state come from the same
    `pwrStatus` object, so the state travels with the moment the machine last
    stated that object. A machine that never answered the state shows nothing
    rather than an assumed one.
    """

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "battery_state"
    _attr_icon = "mdi:battery"

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
        self._attr_unique_id = f"{iot_id}-battery_state"

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
    def extra_state_attributes(self) -> dict[str, int | str | None]:
        """The state as the machine stated it, and when it stated it."""
        return self.coordinator.battery_state_evidence(self._iot_id)

    @property
    def native_value(self) -> str | int | None:
        """Return the battery state the machine reported, or None stated none."""
        snap = self._snap
        if snap is None:
            return None
        raw = snap.battery_state
        if raw is None:
            return None
        if raw >= len(_FIT_OPTIONS):
            return raw
        return _FIT_OPTIONS[raw]

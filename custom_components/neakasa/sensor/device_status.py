"""Sensor for the state the machine reports for itself."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..base_entity import write_state_if_changed
from ..coordinator import NeakasaCoordinator, NeakasaDeviceSnapshot

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceInfo

_STATE_OPTIONS = [
    "idle",
    "preparing_food",
    "serving_food",
    "paused",
    "fault",
    "sleeping",
    "freshness_protection",
    "deep_cleaning",
]


class NeakasaDeviceStatusSensor(CoordinatorEntity[NeakasaCoordinator], SensorEntity):
    """
    The operating state the feeder's own `deviceState` key states.

    The state codes and their names are the definition's (`deviceState.state`
    is an enum whose eight values the definition spells out), and the machine
    re-pushes that key as it works, so the model carries the value with the
    moment the machine stated it - `state_as_of` and `state_age_minutes`
    travel beside the number rather than presenting it as the present. This
    unit has only ever answered 0; the other names are what the definition
    says they mean, not what has been seen here. A code outside the eight is
    published as that number, because nothing here invents a name for it.
    """

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "device_status"
    _attr_icon = "mdi:state-machine"

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
        self._attr_unique_id = f"{iot_id}-device_status"

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
        return self.coordinator.device_state_evidence(self._iot_id)

    @property
    def native_value(self) -> str | int | None:
        """Return the state the machine reported, or None when it states none."""
        snap = self._snap
        if snap is None:
            return None
        raw = snap.device_state
        if raw >= len(_STATE_OPTIONS):
            return raw
        return _STATE_OPTIONS[raw]

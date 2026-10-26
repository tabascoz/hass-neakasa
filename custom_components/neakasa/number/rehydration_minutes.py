"""Number for the rehydration time the machine applies to a wet meal."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.number import NumberEntity
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..base_entity import write_state_if_changed
from ..const import MIX_MIN_MAX, MIX_MIN_MIN
from ..coordinator import NeakasaCoordinator

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceInfo


class NeakasaRehydrationMinutesNumber(
    CoordinatorEntity[NeakasaCoordinator], NumberEntity
):
    """Minutes the machine spends rehydrating the meal before it delivers it."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "rehydration_minutes"
    _attr_icon = "mdi:timer"
    _attr_native_unit_of_measurement = "min"
    _attr_native_step = 1
    _attr_native_min_value = float(MIX_MIN_MIN)
    _attr_native_max_value = float(MIX_MIN_MAX)

    def __init__(
        self,
        coordinator: NeakasaCoordinator,
        device_info: DeviceInfo,
        iot_id: str,
    ) -> None:
        """Initialize the number."""
        super().__init__(coordinator)
        self._iot_id = iot_id
        self.device_info = device_info
        self._attr_unique_id = f"{iot_id}-rehydration_minutes"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Show the rehydration time the machine stores."""
        snap = self.coordinator.device_snapshot(self._iot_id)
        minutes = snap.mix_min_minutes if snap is not None else None
        self._attr_native_value = float(minutes) if minutes is not None else None
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

    async def async_set_native_value(self, value: float) -> None:
        """Store a new rehydration time, leaving the meal amounts alone."""
        await self.coordinator.set_rehydration_minutes(self._iot_id, int(value))

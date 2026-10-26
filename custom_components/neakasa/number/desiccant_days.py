"""Number for the desiccant pack's day budget."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.number import NumberEntity
from homeassistant.components.sensor import EntityCategory
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..base_entity import write_state_if_changed
from ..const import DESICCANT_DAYS_MAX, DESICCANT_DAYS_MIN
from ..coordinator import NeakasaCoordinator

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceInfo


class NeakasaDesiccantDaysNumber(CoordinatorEntity[NeakasaCoordinator], NumberEntity):
    """Days of drying the machine should count for a fresh desiccant pack."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "desiccant_days"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:scale-balance"
    _attr_native_unit_of_measurement = "d"
    _attr_native_step = 1
    _attr_native_min_value = float(DESICCANT_DAYS_MIN)
    _attr_native_max_value = float(DESICCANT_DAYS_MAX)

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
        self._attr_unique_id = f"{iot_id}-desiccant_days"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Show the budget the machine states for its pack."""
        snap = self.coordinator.device_snapshot(self._iot_id)
        days = snap.desiccant_days_effective if snap is not None else None
        self._attr_native_value = float(days) if days is not None else None
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
        """Store a new day budget for the pack."""
        days = int(value)
        if not DESICCANT_DAYS_MIN <= days <= DESICCANT_DAYS_MAX:
            msg = f"Days out of range: {days}"
            raise ValueError(msg)
        await self.coordinator.set_property(
            self._iot_id, "desiccant_days_effective", days
        )

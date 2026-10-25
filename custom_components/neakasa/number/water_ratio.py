"""Number to set the water-to-food ratio used by the next Riko feed."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.number import NumberEntity
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..const import FEED_WATER_RATIO_MAX, FEED_WATER_RATIO_MIN
from ..coordinator import NeakasaCoordinator

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceInfo


class NeakasaWaterRatioNumber(CoordinatorEntity[NeakasaCoordinator], NumberEntity):
    """Water-to-food ratio (1:1 to 1:5) the next Feed now will use."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "water_ratio"
    _attr_icon = "mdi:water"
    _attr_native_step = 1
    _attr_native_min_value = float(FEED_WATER_RATIO_MIN)
    _attr_native_max_value = float(FEED_WATER_RATIO_MAX)

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
        self._attr_unique_id = f"{iot_id}-water_ratio"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Show the ratio the next Feed now would use."""
        _food_g, water_ratio = self.coordinator.feed_values(self._iot_id)
        self._attr_native_value = float(water_ratio)
        self.async_write_ha_state()

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
        """Use a new water ratio for the next feed; the machine is not written."""
        self.coordinator.set_pending_feed(self._iot_id, water_ratio=int(value))

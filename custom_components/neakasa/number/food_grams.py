"""Number to set the Riko food portion used by the next feed (grams)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.number import NumberEntity
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..base_entity import write_state_if_changed
from ..const import FEED_FOOD_MAX_G, FEED_FOOD_MIN_G
from ..coordinator import NeakasaCoordinator

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceInfo


class NeakasaFoodGramsNumber(CoordinatorEntity[NeakasaCoordinator], NumberEntity):
    """Wet-food portion in grams the next Feed now will use (3-15)."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "food_grams"
    _attr_icon = "mdi:scale"
    _attr_native_unit_of_measurement = "g"
    _attr_native_step = 1
    _attr_native_min_value = float(FEED_FOOD_MIN_G)
    _attr_native_max_value = float(FEED_FOOD_MAX_G)

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
        self._attr_unique_id = f"{iot_id}-food_grams"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Show the portion the next Feed now would use."""
        food_g, _ratio = self.coordinator.feed_values(self._iot_id)
        self._attr_native_value = float(food_g)
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
        """Use a new food portion for the next feed; the machine is not written."""
        self.coordinator.set_pending_feed(self._iot_id, food_g=int(value))

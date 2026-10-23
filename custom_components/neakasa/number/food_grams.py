"""Number to set the Riko default feed portion (grams of wet food)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.number import NumberEntity
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..const import FEED_FOOD_MAX_G, FEED_FOOD_MIN_G
from ..coordinator import NeakasaCoordinator, NeakasaDeviceSnapshot

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceInfo


class NeakasaFoodGramsNumber(CoordinatorEntity[NeakasaCoordinator], NumberEntity):
    """Default wet-food portion per feeding, in grams (3-15)."""

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
        snap = self.coordinator.device_snapshot(self._iot_id)
        if snap is not None:
            self._attr_native_value = float(snap.default_food_g or FEED_FOOD_MIN_G)
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

    @property
    def _snap(self) -> NeakasaDeviceSnapshot | None:
        return self.coordinator.device_snapshot(self._iot_id)

    async def async_set_native_value(self, value: float) -> None:
        """Write a new food portion, preserving the current water ratio."""
        snap = self._snap
        if snap is None:
            return
        await self.coordinator.set_feed_config(
            self._iot_id,
            food_g=int(value),
            water_ratio=snap.default_water_ratio or 1,
        )

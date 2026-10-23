"""Number to set the Riko water-to-food ratio for feeding (1-5)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.number import NumberEntity
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..const import FEED_WATER_RATIO_MAX, FEED_WATER_RATIO_MIN
from ..coordinator import NeakasaCoordinator, NeakasaDeviceSnapshot

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceInfo


class NeakasaWaterRatioNumber(CoordinatorEntity[NeakasaCoordinator], NumberEntity):
    """Water-to-food ratio per feeding (1 = 1:1, 5 = 1:5)."""

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
        snap = self.coordinator.device_snapshot(self._iot_id)
        if snap is not None:
            self._attr_native_value = float(
                snap.default_water_ratio or FEED_WATER_RATIO_MIN
            )
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
        """Write a new water ratio, preserving the current food portion."""
        snap = self._snap
        if snap is None:
            return
        await self.coordinator.set_feed_config(
            self._iot_id,
            food_g=snap.default_food_g or 5,
            water_ratio=int(value),
        )

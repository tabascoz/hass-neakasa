"""Button asking the machine to recalibrate how it reads food weight."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..base_entity import write_state_if_changed
from ..coordinator import NeakasaCoordinator

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceInfo


class NeakasaCalibrateFoodScaleButton(
    CoordinatorEntity[NeakasaCoordinator], ButtonEntity
):
    """
    Ask for the food-scale recalibration the machine can do by itself.

    The command asked for is `fdCalbration`. Its definition names coefficients
    the machine sets itself, and this unit has never answered with any of them,
    so nothing is invented here: the press asks and the machine answers.
    """

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "calibrate_food_scale"
    _attr_icon = "mdi:scale-bold"

    def __init__(
        self,
        coordinator: NeakasaCoordinator,
        device_info: DeviceInfo,
        iot_id: str,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._iot_id = iot_id
        self.device_info = device_info
        self._attr_unique_id = f"{iot_id}-calibrate_food_scale"

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

    async def async_press(self) -> None:
        """Ask the machine to recalibrate its food-weight reading."""
        await self.coordinator.request_food_scale_calibration(self._iot_id)

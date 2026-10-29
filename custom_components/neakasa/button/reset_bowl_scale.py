"""Button re-zeroing the scale against the bowl it weighs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..base_entity import write_state_if_changed
from ..coordinator import NeakasaCoordinator

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceInfo


class NeakasaResetBowlScaleButton(CoordinatorEntity[NeakasaCoordinator], ButtonEntity):
    """
    Re-zero the machine's scale with the bowl weight it states.

    The command asked for is `resetScaleZero`; the grams used are the bowl
    weight the machine states, and the press fails with a message when the
    machine has never stated one.
    """

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "reset_bowl_scale"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:scale"

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
        self._attr_unique_id = f"{iot_id}-reset_bowl_scale"

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
        """Re-zero the scale with the bowl weight the machine states."""
        await self.coordinator.request_bowl_scale_reset(self._iot_id)

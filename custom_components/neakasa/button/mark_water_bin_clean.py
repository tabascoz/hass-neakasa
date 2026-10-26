"""Button marking the water tank as cleaned now."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..base_entity import write_state_if_changed
from ..coordinator import NeakasaCoordinator

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceInfo


class NeakasaMarkWaterBinCleanButton(
    CoordinatorEntity[NeakasaCoordinator], ButtonEntity
):
    """
    Record on the machine that its water tank was cleaned now.

    The mark is the property the machine's definition names for the last
    cleaning; this unit has never answered with one, so the press is what
    shows whether this firmware stores it.
    """

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "mark_water_bin_clean"
    _attr_icon = "mdi:water-drop"

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
        self._attr_unique_id = f"{iot_id}-mark_water_bin_clean"

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
        """Mark the water tank clean on the machine."""
        await self.coordinator.mark_bin_clean(self._iot_id, "water")

"""Number for how loud the machine plays the sound of a delivered meal."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.number import NumberEntity
from homeassistant.const import EntityCategory
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..base_entity import write_state_if_changed
from ..const import FEED_SOUND_VOLUME_MAX, FEED_SOUND_VOLUME_MIN
from ..coordinator import NeakasaCoordinator

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceInfo


class NeakasaFeedSoundVolumeNumber(CoordinatorEntity[NeakasaCoordinator], NumberEntity):
    """
    The volume of the meal sound, where 0 means no sound at all.

    The machine's own definition allows a volume up to 200 and this unit states
    100; the integration offers 0-100 so that a setting here stays inside what
    the machine has been seen to use.
    """

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "feed_sound_volume"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:volume-high"
    _attr_native_step = 1
    _attr_native_min_value = float(FEED_SOUND_VOLUME_MIN)
    _attr_native_max_value = float(FEED_SOUND_VOLUME_MAX)

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
        self._attr_unique_id = f"{iot_id}-feed_sound_volume"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Show the volume the machine states."""
        snap = self.coordinator.device_snapshot(self._iot_id)
        volume = snap.sound_volume if snap is not None else None
        self._attr_native_value = float(volume) if volume is not None else None
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
        """Set the volume of the meal sound, keeping the clip it uses."""
        await self.coordinator.set_feed_sound_volume(self._iot_id, int(value))

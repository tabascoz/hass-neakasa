"""Text the front display shows while the machine is idle."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import EntityCategory
from homeassistant.components.text import TextEntity
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..base_entity import write_state_if_changed
from ..const import DISPLAY_PARAM_MAX_CHARS
from ..coordinator import NeakasaCoordinator, NeakasaDeviceSnapshot

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceInfo


class NeakasaDisplayCustomMessageText(
    CoordinatorEntity[NeakasaCoordinator], TextEntity
):
    """
    The message the front display shows when the machine is idle.

    The machine's definition caps this at 50 characters; Home Assistant's
    maximum is enforced before writing, so an over-long value is refused rather
    than truncated silently.
    """

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "display_custom_message"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:text"
    _attr_native_max = DISPLAY_PARAM_MAX_CHARS

    def __init__(
        self,
        coordinator: NeakasaCoordinator,
        device_info: DeviceInfo,
        iot_id: str,
    ) -> None:
        """Initialize the text entity."""
        super().__init__(coordinator)
        self._iot_id = iot_id
        self.device_info = device_info
        self._attr_unique_id = f"{iot_id}-display_custom_message"

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

    @property
    def _snap(self) -> NeakasaDeviceSnapshot | None:
        return self.coordinator.device_snapshot(self._iot_id)

    @property
    def native_value(self) -> str | None:
        """
        Return the message the display shows, or `""` when it shows none.

        `native_value` is the name the text platform reads, so this is what puts
        a state on the entity. A device that is not in the model at all stays
        `None`, because an empty message would be a claim about a machine that
        was never read. A device that states its display config with nothing in
        the message field is shown empty, which is what lets a message be typed
        into it: Home Assistant offers no typing for an entity that has no state,
        so a machine that holds no standby message would otherwise be unreachable.
        """
        snap = self._snap
        if snap is None:
            return None
        return snap.display_param or ""

    async def async_set_value(self, value: str) -> None:
        """Write a message the front display should show."""
        if len(value) > DISPLAY_PARAM_MAX_CHARS:
            msg = f"Message too long: {len(value)} characters"
            raise ValueError(msg)
        snap = self._snap
        if snap is None:
            return
        cfg = dict(snap.display_cfg or {})
        cfg["displayParam"] = value
        await self.coordinator.set_property(self._iot_id, "display_cfg", cfg)

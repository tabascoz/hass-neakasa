"""Selector for the kind of standby display the front shows."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..base_entity import write_state_if_changed
from ..coordinator import NeakasaCoordinator, NeakasaDeviceSnapshot

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceInfo

# The definition spells the kind out: `displayCfg.displayType` is an enum whose
# value list is `{"0": 时间, "1": 图形, "2": 自定义}`, so the numbers below are the
# definition's, not inferred from the product's order. Choosing a kind carries
# whatever message the machine states in the sibling `displayParam`; the panel draws
# no lower-case glyphs, so a message worth seeing is upper-case, and
# `text/display_custom_message.py` sends it that way.
DISPLAY_TYPE_CODES: dict[str, int] = {"time": 0, "graphics": 1, "custom": 2}
DISPLAY_TYPE_NAMES: dict[int, str] = {
    value: name for name, value in DISPLAY_TYPE_CODES.items()
}


class NeakasaDisplayStandbyKindSelect(
    CoordinatorEntity[NeakasaCoordinator], SelectEntity
):
    """Choose what the front display shows while the machine is idle."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "display_standby_kind"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:display"
    _attr_options = tuple(DISPLAY_TYPE_CODES)

    def __init__(
        self,
        coordinator: NeakasaCoordinator,
        device_info: DeviceInfo,
        iot_id: str,
    ) -> None:
        """Initialize the selector."""
        super().__init__(coordinator)
        self._iot_id = iot_id
        self.device_info = device_info
        self._attr_unique_id = f"{iot_id}-display_standby_kind"

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
    def current_option(self) -> str | None:
        """Return the display kind the machine states, or None."""
        snap = self._snap
        if snap is None or snap.display_type is None:
            return None
        return DISPLAY_TYPE_NAMES.get(snap.display_type)

    async def async_select_option(self, option: str) -> None:
        """Ask for one of the standby display kinds."""
        code = DISPLAY_TYPE_CODES.get(option)
        if code is None:
            msg = f"Unknown display kind: {option}"
            raise ValueError(msg)
        snap = self._snap
        if snap is None:
            return
        cfg = dict(snap.display_cfg or {})
        cfg["displayType"] = code
        await self.coordinator.set_property(self._iot_id, "display_cfg", cfg)

"""Switch for the machine's do-not-disturb window."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..base_entity import write_state_if_changed
from ..coordinator import NeakasaCoordinator, NeakasaDeviceSnapshot

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceInfo


class NeakasaDoNotDisturbSwitch(CoordinatorEntity[NeakasaCoordinator], SwitchEntity):
    """
    Silence the machine while its do-not-disturb window is on.

    The window itself (its start, end, which days repeat, and whether the
    silence covers the sound and the display) stays as the machine stated it;
    this switch only moves `active`.
    """

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "do_not_disturb"
    _attr_icon = "mdi:moon"

    def __init__(
        self,
        coordinator: NeakasaCoordinator,
        device_info: DeviceInfo,
        iot_id: str,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._iot_id = iot_id
        self.device_info = device_info
        self._attr_unique_id = f"{iot_id}-do_not_disturb"

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
    def is_on(self) -> bool:
        """Return whether the machine says the window is active."""
        snap = self._snap
        if snap is None:
            return False
        return bool(snap.dnd_active)

    @property
    def state(self) -> str:
        """Return the current switch state."""
        return STATE_ON if self.is_on else STATE_OFF

    async def async_turn_on(self, **kwargs: object) -> None:  # noqa: ARG002
        """Ask the machine to hold its do-not-disturb window."""
        await self._set_active(1)

    async def async_turn_off(self, **kwargs: object) -> None:  # noqa: ARG002
        """Let the machine run again in that window."""
        await self._set_active(0)

    async def _set_active(self, value: int) -> None:
        snap = self._snap
        if snap is None:
            return
        cfg = dict(snap.dnd_cfg or {})
        cfg["active"] = value
        await self.coordinator.set_property(self._iot_id, "dnd_cfg", cfg)

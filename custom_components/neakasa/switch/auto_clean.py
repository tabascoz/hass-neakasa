"""Switch to toggle auto-clean scheduling."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..coordinator import NeakasaCoordinator, NeakasaDeviceSnapshot

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceInfo


class NeakasaAutoCleanSwitch(CoordinatorEntity[NeakasaCoordinator], SwitchEntity):
    """Toggle for the auto-clean schedule."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "auto_clean"
    _attr_icon = "mdi:vacuum"

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
        self._attr_unique_id = f"{iot_id}-auto_clean"

    @callback
    def _handle_coordinator_update(self) -> None:
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

    @property
    def is_on(self) -> bool:
        """Return whether auto-clean is enabled."""
        snap = self._snap
        if snap is None:
            return False
        cfg = snap.clean_cfg
        if not isinstance(cfg, dict):
            return False
        return bool(cfg.get("active", False))

    @property
    def state(self) -> str:
        """Return the current switch state."""
        return STATE_ON if self.is_on else STATE_OFF

    async def async_turn_on(self, **kwargs: object) -> None:  # noqa: ARG002
        """Turn the switch on."""
        await self._set_active(1)

    async def async_turn_off(self, **kwargs: object) -> None:  # noqa: ARG002
        """Turn the switch off."""
        await self._set_active(0)

    async def _set_active(self, value: int) -> None:
        snap = self._snap
        cfg = dict(snap.clean_cfg if isinstance(snap.clean_cfg, dict) else {})
        cfg["active"] = value
        await self.coordinator.set_property(self._iot_id, "clean_cfg", cfg)

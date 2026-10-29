"""Switch for the freshness manager that watches the bowl."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import STATE_OFF, STATE_ON, EntityCategory
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..base_entity import write_state_if_changed
from ..coordinator import NeakasaCoordinator, NeakasaDeviceSnapshot

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceInfo


class NeakasaFreshMealManagerSwitch(
    CoordinatorEntity[NeakasaCoordinator], SwitchEntity
):
    """
    Start or stop the machine's freshness manager.

    Only `bOnOff` is written: the leftover threshold and the hours it watches
    stay as the machine reported them.
    """

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "fresh_meal_manager"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:snowflake"

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
        self._attr_unique_id = f"{iot_id}-fresh_meal_manager"

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
        """Return whether the machine says the manager is running."""
        snap = self._snap
        if snap is None:
            return False
        return bool(snap.fresh_mgr_on)

    @property
    def state(self) -> str:
        """Return the current switch state."""
        return STATE_ON if self.is_on else STATE_OFF

    async def async_turn_on(self, **kwargs: object) -> None:  # noqa: ARG002
        """Start the freshness manager."""
        await self._set_enabled(1)

    async def async_turn_off(self, **kwargs: object) -> None:  # noqa: ARG002
        """Stop the freshness manager."""
        await self._set_enabled(0)

    async def _set_enabled(self, value: int) -> None:
        snap = self._snap
        if snap is None:
            return
        cfg = dict(snap.fresh_mgr_cfg or {})
        cfg["bOnOff"] = value
        await self.coordinator.set_property(self._iot_id, "fresh_mgr_cfg", cfg)

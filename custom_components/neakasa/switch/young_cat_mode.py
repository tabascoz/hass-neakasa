"""Switch for kitten/young-cat mode."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..coordinator import NeakasaCoordinator, NeakasaDeviceSnapshot

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceInfo


class NeakasaYoungCatModeSwitch(CoordinatorEntity[NeakasaCoordinator], SwitchEntity):
    """Toggle for kitten (young cat) mode."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "young_cat_mode"
    _attr_entity_registry_enabled_default = False
    _attr_icon = "mdi:cat"

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
        self._attr_unique_id = f"{iot_id}-young_cat_mode"

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()

    @property
    def _snap(self) -> NeakasaDeviceSnapshot | None:
        return self.coordinator.device_snapshot(self._iot_id)

    @property
    def is_on(self) -> bool:
        """Return whether young cat mode is enabled."""
        snap = self._snap
        if snap is None:
            return False
        return snap.young_cat_mode

    @property
    def state(self) -> str:
        """Return the current switch state."""
        return STATE_ON if self.is_on else STATE_OFF

    async def async_turn_on(self, **kwargs: object) -> None:  # noqa: ARG002
        """Turn the switch on."""
        await self.coordinator.set_property(self._iot_id, "young_cat_mode", 1)

    async def async_turn_off(self, **kwargs: object) -> None:  # noqa: ARG002
        """Turn the switch off."""
        await self.coordinator.set_property(self._iot_id, "young_cat_mode", 0)

"""Switch choosing whether a Riko feed stores the amounts it used."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..base_entity import write_state_if_changed
from ..coordinator import NeakasaCoordinator

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceInfo


class NeakasaFeedKeepDefaultsSwitch(
    CoordinatorEntity[NeakasaCoordinator], SwitchEntity
):
    """Choose whether a feed stores its amounts as the machine's defaults."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "feed_keep_as_new_defaults"
    _attr_icon = "mdi:content-save"

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
        self._attr_unique_id = f"{iot_id}-feed_keep_as_new_defaults"

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
    def is_on(self) -> bool:
        """Return whether the next feed stores the amounts it uses."""
        return self.coordinator.feed_keep_as_new_defaults(self._iot_id)

    @property
    def state(self) -> str:
        """Return the current switch state."""
        return STATE_ON if self.is_on else STATE_OFF

    async def async_turn_on(self, **kwargs: object) -> None:  # noqa: ARG002
        """Store the amounts the next feed uses as the machine's defaults."""
        self.coordinator.set_feed_keep_as_new_defaults(self._iot_id, value=True)

    async def async_turn_off(self, **kwargs: object) -> None:  # noqa: ARG002
        """Leave the machine's defaults alone when feeding."""
        self.coordinator.set_feed_keep_as_new_defaults(self._iot_id, value=False)

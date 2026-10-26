"""Temporary debug buttons for the account tokens (remove after testing)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..base_entity import write_state_if_changed
from ..coordinator import NeakasaCoordinator

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceInfo


class NeakasaDebugTokenChurnButton(CoordinatorEntity[NeakasaCoordinator], ButtonEntity):
    """Press to sign in a few times in a row, so the account gains sessions."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "debug_token_churn"
    _attr_icon = "mdi:refresh"

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
        self._attr_unique_id = f"{iot_id}-debug_token_churn"

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
        """Churn the account's sessions and watch the Neakasa app."""
        await self.coordinator.debug_token_churn()


class NeakasaDebugTokenInvalidateButton(
    CoordinatorEntity[NeakasaCoordinator], ButtonEntity
):
    """Press to break the tokens we hold, so the next scan must recover them."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "debug_token_invalidate"
    _attr_icon = "mdi:token"

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
        self._attr_unique_id = f"{iot_id}-debug_token_invalidate"

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
        """Invalidate our tokens and watch the next scan repair them."""
        await self.coordinator.debug_invalidate_tokens()

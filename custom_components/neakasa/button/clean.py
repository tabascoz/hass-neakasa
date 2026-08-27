"""Button to trigger an immediate clean cycle."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..coordinator import NeakasaCoordinator

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceInfo


class NeakasaCleanButton(CoordinatorEntity[NeakasaCoordinator], ButtonEntity):
    """Button to start an immediate cleaning cycle."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "clean"

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
        self._attr_unique_id = f"{iot_id}-clean"

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()

    async def async_press(self) -> None:
        """Trigger a clean cycle."""
        await self.coordinator.invoke_service(self._iot_id, "clean")

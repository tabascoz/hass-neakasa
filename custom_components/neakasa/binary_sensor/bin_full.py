"""Binary sensor for waste bin full state."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..coordinator import NeakasaCoordinator, NeakasaDeviceSnapshot

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceInfo


class NeakasaBinFullBinarySensor(
    CoordinatorEntity[NeakasaCoordinator], BinarySensorEntity
):
    """Binary sensor indicating whether the waste bin is full."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "bin_full"
    _attr_icon = "mdi:delete-empty"

    def __init__(
        self,
        coordinator: NeakasaCoordinator,
        device_info: DeviceInfo,
        iot_id: str,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._iot_id = iot_id
        self.device_info = device_info
        self._attr_unique_id = f"{iot_id}-bin_full"

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
        """Return whether the bin is full."""
        snap = self._snap
        if snap is None:
            return False
        return snap.bin_full

    @property
    def state(self) -> str:
        """Return the current binary sensor state."""
        return STATE_ON if self.is_on else STATE_OFF

"""Sensor for the waste bin state."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..coordinator import NeakasaCoordinator, NeakasaDeviceSnapshot

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceInfo

_BIN_OPTIONS = ["normal", "full", "missing"]


class NeakasaBinStateSensor(CoordinatorEntity[NeakasaCoordinator]):
    """Waste bin state (normal, full, missing)."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "bin_state"
    _attr_icon = "mdi:delete"

    def __init__(
        self,
        coordinator: NeakasaCoordinator,
        device_info: DeviceInfo,
        iot_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._iot_id = iot_id
        self.device_info = device_info
        self._attr_unique_id = f"{iot_id}-bin_state"

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()

    @property
    def _snap(self) -> NeakasaDeviceSnapshot | None:
        return self.coordinator.device_snapshot(self._iot_id)

    @property
    def native_value(self) -> str | int | None:
        """Return the mapped bin state."""
        snap = self._snap
        if snap is None:
            return None
        raw = snap.room_of_bin
        if raw >= len(_BIN_OPTIONS):
            return raw
        value = _BIN_OPTIONS[raw]
        return raw if value is None else value

"""Sensor for the timestamp of the last cat usage."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..coordinator import NeakasaCoordinator, NeakasaDeviceSnapshot

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceInfo


class NeakasaLastUsageSensor(CoordinatorEntity[NeakasaCoordinator]):
    """Timestamp of the last time a cat used the litter box."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "last_usage"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

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
        self._attr_unique_id = f"{iot_id}-last_usage"

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()

    @property
    def _snap(self) -> NeakasaDeviceSnapshot | None:
        return self.coordinator.device_snapshot(self._iot_id)

    @property
    def native_value(self) -> datetime | None:
        """Return the last-use timestamp."""
        snap = self._snap
        if snap is None:
            return None
        raw = snap.last_use
        if not raw:
            return None
        try:
            return datetime.fromtimestamp(raw / 1000, tz=UTC)
        except (TypeError, ValueError):
            return None

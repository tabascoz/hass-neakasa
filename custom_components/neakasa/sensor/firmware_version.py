"""Sensor for the firmware and hardware versions the machine reports."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import EntityCategory, SensorEntity
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..base_entity import write_state_if_changed
from ..coordinator import NeakasaCoordinator, NeakasaDeviceSnapshot

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceInfo


class NeakasaFirmwareVersionSensor(CoordinatorEntity[NeakasaCoordinator], SensorEntity):
    """The version the machine states about itself, firmware and hardware."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "firmware_version"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:memory"

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
        self._attr_unique_id = f"{iot_id}-firmware_version"

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
    def native_value(self) -> str | None:
        """Return the firmware version the machine states."""
        snap = self._snap
        if snap is None:
            return None
        return snap.firmware_version

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Include the hardware version, which the same record carries."""
        snap = self._snap
        if snap is None:
            return {}
        return {"hw_version": snap.hardware_version}

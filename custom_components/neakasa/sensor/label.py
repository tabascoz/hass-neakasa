"""Sensor exposing the user-assigned device label for any Neakasa device."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..base_entity import write_state_if_changed
from ..coordinator import NeakasaCoordinator, NeakasaDeviceSnapshot

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceInfo


class NeakasaLabelSensor(CoordinatorEntity[NeakasaCoordinator], SensorEntity):
    """
    The friendly name the owner gave the device in the Neakasa app.

    The integration names devices by their wire serial (stable, and what the
    cloud record endpoints key on); this sensor surfaces the human label so
    users can tell their devices apart. It applies to every product type.
    """

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "device_label"

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
        self._attr_unique_id = f"{iot_id}-device_label"

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
        """Return the user label, or None when the owner has not set one."""
        snap = self._snap
        if snap is None:
            return None
        return snap.label or None

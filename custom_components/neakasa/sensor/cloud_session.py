"""Account-level sensor: which client holds the cloud session."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..coordinator import (
    CLOUD_SESSION_OWNERS,
    SESSION_OWNER_UNKNOWN,
    NeakasaCoordinator,
)

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceInfo


class NeakasaCloudSessionStatusSensor(
    CoordinatorEntity[NeakasaCoordinator], SensorEntity
):
    """Which client the account's session currently belongs to."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "cloud_session_status"
    _attr_icon = "mdi:key"

    def __init__(
        self,
        coordinator: NeakasaCoordinator,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the sensor for the account, not for a device."""
        super().__init__(coordinator)
        self.device_info = device_info
        self._attr_unique_id = f"{coordinator.username}-cloud_session"
        self._attr_options = list(CLOUD_SESSION_OWNERS)
        self._last_owner = SESSION_OWNER_UNKNOWN

    @property
    def native_value(self) -> str:
        """Return which client the session belongs to, as last observed."""
        return self.coordinator.cloud_session_owner

    @callback
    def _handle_coordinator_update(self) -> None:
        self._write_if_changed()

    def _write_if_changed(self) -> None:
        """Write the state only when the owner changed, so scans stay quiet."""
        owner = self.coordinator.cloud_session_owner
        if owner == self._last_owner:
            return
        self._last_owner = owner
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Update the sensor from the coordinator."""
        if self.entity_id is None:
            return
        self._write_if_changed()

    async def async_added_to_hass(self) -> None:
        """Write the initial state once entity_id is assigned."""
        await super().async_added_to_hass()
        self._write_if_changed()

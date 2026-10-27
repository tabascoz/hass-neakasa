"""Account-level sensor: which client the cloud session belongs to, and why."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
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
    """
    Which client the account's session belongs to, as far as we can prove.

    The values are the slugs in CLOUD_SESSION_OWNERS - what rules and
    actions compare against - and the words you see come from the state
    maps in translations/. home_assistant says our last account call was
    accepted, not_home_assistant says it was refused (the mobile app holds
    the session, or the cloud let it age out on its own: a refusal cannot
    tell those apart), and unknown says nothing has presented the account
    since this entry started. The attributes carry the timestamps, so any
    claim traces to the call that made it.
    """

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "cloud_session_status"
    _attr_icon = "mdi:key"
    _attr_device_class = SensorDeviceClass.ENUM

    def __init__(
        self,
        coordinator: NeakasaCoordinator,
        device_info: DeviceInfo,
        account_id: str,
    ) -> None:
        """
        Initialize the sensor for the account, not for a device.

        The identity comes from the config entry, so reconfiguring the
        entry to another account keeps this entity rather than leaving
        an orphan of the previous account behind.
        """
        super().__init__(coordinator)
        self.device_info = device_info
        self._attr_unique_id = f"{account_id}-cloud_session"
        self._attr_options = list(CLOUD_SESSION_OWNERS)
        self._last_owner = SESSION_OWNER_UNKNOWN

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """What the reported owner is based on, so the claim can be checked."""
        return self.coordinator.session_evidence

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

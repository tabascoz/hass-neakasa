"""Account-level button: take the session back and read fresh values."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..coordinator import NeakasaCoordinator

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceInfo


class NeakasaRefreshDataButton(CoordinatorEntity[NeakasaCoordinator], ButtonEntity):
    """Press to give the account session back to Home Assistant and re-read."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "refresh_data"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:refresh"

    def __init__(
        self,
        coordinator: NeakasaCoordinator,
        device_info: DeviceInfo,
        account_id: str,
    ) -> None:
        """
        Initialize the button for the account, not for a device.

        The identity comes from the config entry, so reconfiguring the
        entry to another account keeps this button.
        """
        super().__init__(coordinator)
        self.device_info = device_info
        self._attr_unique_id = f"{account_id}-refresh_data"

    async def async_press(self) -> None:
        """
        Take the session back and read what was refused.

        Presenting the account is what moves the session, so the Neakasa app
        has to sign in again after this press. It exists so that choosing the
        client which is current is a decision, rather than the two of them
        taking it back and forth on every scan.
        """
        await self.coordinator.regain_cloud_session()

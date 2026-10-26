"""
Temporary debug buttons for the account tokens (remove after testing).

Both presses exist to make the session path observable in a short time: a
natural token expiry costs exactly what the churn press performs, and waiting
for one is slow. What each press does, and what was seen on the unit, is
written up in docs/app-session-experiments.md.
"""

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
    """
    Sign the account in a few times in a row, so it gains sessions.

    The press writes `Debug token churn 1/3: signing in` per sign-in and
    `Debug token churn complete: 3 sign-ins`, beside the `Account session
    minted #N …` lines the shared client writes for each sign-in. Each sign-in
    is one session, which is what makes the app side sign in again; the count is
    the thing docs/app-session-experiments.md measures.
    """

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
        """Churn the account's sessions and watch the app sign in again."""
        await self.coordinator.debug_token_churn()


class NeakasaDebugTokenInvalidateButton(
    CoordinatorEntity[NeakasaCoordinator], ButtonEntity
):
    """
    Break the tokens we hold, so the next scan has to recover them.

    The press writes `Debug tokens invalidated: the next scan must recover them`.
    The next scan then has a records call refused for the account token, which is
    the branch's recovery path: it must read that refusal as an expired session,
    sign in once, and read the values again. What was observed on the unit after
    such a press is written up in docs/app-session-experiments.md.
    """

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
        """Break our tokens so the next scan's recovery path has to run."""
        await self.coordinator.debug_invalidate_tokens()

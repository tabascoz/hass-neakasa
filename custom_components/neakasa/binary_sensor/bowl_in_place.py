"""Binary sensor for whether the bowl is on the scale."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..base_entity import write_state_if_changed
from ..coordinator import NeakasaCoordinator, NeakasaDeviceSnapshot

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceInfo


class NeakasaBowlInPlaceBinarySensor(
    CoordinatorEntity[NeakasaCoordinator], BinarySensorEntity
):
    """
    Whether the bowl sits on the scale, as the machine's own key states.

    `bowlStatus.bBowlIn` is an enum the definition names 不在位 (not in place)
    and 在位 (in place); this unit has answered 1 with the bowl in place. The
    answer belongs to the same cloud copy the bowl weight is read from, so the
    reading's age travels with it: a bowl reported in place is in place at the
    moment the machine stated it, not necessarily now.
    """

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "bowl_in_place"
    _attr_icon = "mdi:bowl"

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
        self._attr_unique_id = f"{iot_id}-bowl_in_place"

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
    def extra_state_attributes(self) -> dict[str, int | str | None]:
        """The cloud copy this answer belongs to, and when it was stated."""
        return self.coordinator.scale_state_evidence(self._iot_id)

    @property
    def is_on(self) -> bool:
        """Return whether the machine states the bowl is on the scale."""
        snap = self._snap
        if snap is None:
            return False
        return snap.bowl_present

    @property
    def state(self) -> str:
        """Return the current binary sensor state."""
        return STATE_ON if self.is_on else STATE_OFF

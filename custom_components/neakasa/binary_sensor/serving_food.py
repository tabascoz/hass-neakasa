"""Binary sensor for whether the machine is working on a meal."""

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

# The two codes the definition names for a meal (备餐中 preparing, 出餐中
# serving); neither has been reported by this unit, so the pair is the
# definition's and not something observed here.
_MEAL_STATES = frozenset({1, 2})


class NeakasaServingFoodBinarySensor(
    CoordinatorEntity[NeakasaCoordinator], BinarySensorEntity
):
    """
    Whether the feeder states it is preparing or serving a meal.

    The answer comes from the machine's state key, which is re-pushed as the
    machine works, and not from the scale: the scale's copy repeats what the
    machine last stored, so it follows nothing. The evidence is the state's
    own, so a claim can be read at the moment the machine made it.
    """

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "serving_food"
    _attr_icon = "mdi:food-delivery"

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
        self._attr_unique_id = f"{iot_id}-serving_food"

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
        """The state the answer comes from, and when the machine stated it."""
        return self.coordinator.device_state_evidence(self._iot_id)

    @property
    def is_on(self) -> bool:
        """Return whether the machine states it is preparing or serving a meal."""
        snap = self._snap
        if snap is None:
            return False
        return snap.device_state in _MEAL_STATES

    @property
    def state(self) -> str:
        """Return the current binary sensor state."""
        return STATE_ON if self.is_on else STATE_OFF

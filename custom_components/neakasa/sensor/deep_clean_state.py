"""Sensor for the bowl wash the machine states it is in."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..base_entity import write_state_if_changed
from ..coordinator import NeakasaCoordinator, NeakasaDeviceSnapshot

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceInfo

# The wash states the definition spells for `deepCleanCfg.cleanState`: 初始状态
# (initial state), 水路清洁中 (water channel washing), 水路清洁完成 (water
# channel washing done), 水路冲洗中 (water channel rinsing). This unit has only
# ever answered 0, so the other three names are the definition's, not observed.
_WASH_OPTIONS = [
    "not_washing",
    "washing_water_channel",
    "water_channel_washed",
    "rinsing_water_channel",
]


class NeakasaDeepCleanStateSensor(CoordinatorEntity[NeakasaCoordinator], SensorEntity):
    """
    The wash state the feeder's own `deepCleanCfg.cleanState` key states.

    The four names are the definition's; this unit has answered only 0, so
    which wash it is in has not been seen here. The state travels with the
    moment the machine stated it, so an answer can be read at that moment
    rather than as now.
    """

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "deep_clean_state"
    _attr_icon = "mdi:water-drop"

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
        self._attr_unique_id = f"{iot_id}-deep_clean_state"

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
        """The wash state as the machine stated it, and when it stated it."""
        return self.coordinator.deep_clean_evidence(self._iot_id)

    @property
    def native_value(self) -> str | int | None:
        """Return the wash state the machine reported, or None when it states none."""
        snap = self._snap
        if snap is None:
            return None
        raw = snap.deep_clean_state
        if raw is None:
            return None
        if raw >= len(_WASH_OPTIONS):
            return raw
        return _WASH_OPTIONS[raw]

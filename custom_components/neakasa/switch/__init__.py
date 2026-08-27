"""Switch platform for Neakasa."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback  # noqa: TC002

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

    from ..coordinator import NeakasaCoordinator
    from ..data import NeakasaConfigEntry

from ..const import DOMAIN
from .auto_bury import NeakasaAutoBurySwitch
from .auto_clean import NeakasaAutoCleanSwitch
from .auto_level import NeakasaAutoLevelSwitch
from .auto_recovery import NeakasaAutoRecoverySwitch
from .child_lock import NeakasaChildLockSwitch
from .silent_mode import NeakasaSilentModeSwitch
from .unstoppable_cycle import NeakasaUnstoppableCycleSwitch
from .young_cat_mode import NeakasaYoungCatModeSwitch


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch entities for all discovered devices."""
    entry = cast("NeakasaConfigEntry", config_entry)
    coordinator: NeakasaCoordinator = entry.runtime_data.coordinator

    _seen_iot_ids: set[str] = set()

    @callback
    def _discover() -> None:
        entities: list = []
        for iot_id, snap in coordinator.data.items():
            if iot_id in _seen_iot_ids:
                continue
            _seen_iot_ids.add(iot_id)
            device_info = DeviceInfo(
                name=snap.device_name,
                manufacturer="Neakasa",
                identifiers={(DOMAIN, iot_id)},
            )
            entities.extend(
                [
                    NeakasaAutoCleanSwitch(coordinator, device_info, iot_id),
                    NeakasaYoungCatModeSwitch(coordinator, device_info, iot_id),
                    NeakasaChildLockSwitch(coordinator, device_info, iot_id),
                    NeakasaAutoBurySwitch(coordinator, device_info, iot_id),
                    NeakasaAutoLevelSwitch(coordinator, device_info, iot_id),
                    NeakasaSilentModeSwitch(coordinator, device_info, iot_id),
                    NeakasaAutoRecoverySwitch(coordinator, device_info, iot_id),
                    NeakasaUnstoppableCycleSwitch(coordinator, device_info, iot_id),
                ]
            )
        async_add_entities(entities)

    _discover()
    config_entry.async_on_unload(coordinator.async_add_listener(_discover))

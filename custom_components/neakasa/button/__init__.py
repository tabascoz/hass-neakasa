"""Button platform for Neakasa."""

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
from .clean import NeakasaCleanButton
from .level import NeakasaLevelButton


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities for all discovered devices."""
    entry = cast("NeakasaConfigEntry", config_entry)
    coordinator: NeakasaCoordinator = entry.runtime_data.coordinator

    @callback
    def _discover() -> None:
        entities: list = []
        for iot_id, snap in coordinator.data.items():
            device_info = DeviceInfo(
                name=snap.device_name,
                manufacturer="Neakasa",
                identifiers={(DOMAIN, iot_id)},
            )
            entities.extend([
                NeakasaCleanButton(coordinator, device_info, iot_id),
                NeakasaLevelButton(coordinator, device_info, iot_id),
            ])
        async_add_entities(entities)

    _discover()
    config_entry.async_on_unload(coordinator.async_add_listener(_discover))

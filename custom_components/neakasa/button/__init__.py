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
from .debug_token import (
    NeakasaDebugTokenChurnButton,
    NeakasaDebugTokenInvalidateButton,
)
from .feed_now import NeakasaFeedNowButton
from .level import NeakasaLevelButton
from .refresh_data import NeakasaRefreshDataButton


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities for all discovered devices."""
    entry = cast("NeakasaConfigEntry", config_entry)
    coordinator: NeakasaCoordinator = entry.runtime_data.coordinator

    _seen_iot_ids: set[str] = set()
    _account_added = False

    @callback
    def _discover() -> None:
        nonlocal _account_added
        entities: list = []
        if not _account_added:
            _account_added = True
            entities.append(
                NeakasaRefreshDataButton(
                    coordinator,
                    DeviceInfo(
                        name="Neakasa account",
                        manufacturer="Neakasa",
                        identifiers={(DOMAIN, f"account:{coordinator.username}")},
                    ),
                ),
            )
        for iot_id, snap in coordinator.data.items():
            if iot_id in _seen_iot_ids:
                continue
            _seen_iot_ids.add(iot_id)
            device_info = DeviceInfo(
                name=snap.device_name,
                model=snap.product_key or None,
                manufacturer="Neakasa",
                identifiers={(DOMAIN, iot_id)},
            )
            if snap.category_key == "petFeeder":
                entities.extend(
                    [
                        NeakasaFeedNowButton(coordinator, device_info, iot_id),
                        NeakasaDebugTokenChurnButton(coordinator, device_info, iot_id),
                        NeakasaDebugTokenInvalidateButton(
                            coordinator,
                            device_info,
                            iot_id,
                        ),
                    ]
                )
                continue
            entities.extend(
                [
                    NeakasaCleanButton(coordinator, device_info, iot_id),
                    NeakasaLevelButton(coordinator, device_info, iot_id),
                ]
            )
        async_add_entities(entities)

    _discover()
    config_entry.async_on_unload(coordinator.async_add_listener(_discover))

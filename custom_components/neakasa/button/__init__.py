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
from .calibrate_food_scale import NeakasaCalibrateFoodScaleButton
from .clean import NeakasaCleanButton

# Disabled for v1.5.0: the token debug presses were test tools only, and their
# module, coordinator methods and tests are gone from this release. The calls
# they used to make are left here as a comment so the removal is reviewable.
# from .debug_token import (
#     NeakasaDebugTokenChurnButton,
#     NeakasaDebugTokenInvalidateButton,
# )  # noqa: ERA001
from .feed_now import NeakasaFeedNowButton
from .level import NeakasaLevelButton
from .mark_food_bin_clean import NeakasaMarkFoodBinCleanButton
from .mark_water_bin_clean import NeakasaMarkWaterBinCleanButton
from .refresh_data import NeakasaRefreshDataButton
from .reset_bowl_scale import NeakasaResetBowlScaleButton
from .reset_desiccant import NeakasaResetDesiccantButton


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities for all discovered devices."""
    entry = cast("NeakasaConfigEntry", config_entry)
    coordinator: NeakasaCoordinator = entry.runtime_data.coordinator

    # One name for the account device, shared by the platforms that add
    # the account-level entities. It follows the config entry, not the
    # credentials, so reconfiguring to another account keeps this device.
    account_id = f"account:{config_entry.entry_id}"

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
                        identifiers={(DOMAIN, account_id)},
                    ),
                    account_id,
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
                        # Disabled with the debug module removed: these two presses
                        # only existed to watch the token path, and
                        # docs/app-session-experiments.md keeps what they showed.
                        # NeakasaDebugTokenChurnButton(
                        #     coordinator, device_info, iot_id
                        # ),
                        # NeakasaDebugTokenInvalidateButton(
                        #     coordinator,
                        #     device_info,
                        #     iot_id,
                        # ),
                        NeakasaResetDesiccantButton(coordinator, device_info, iot_id),
                        NeakasaResetBowlScaleButton(coordinator, device_info, iot_id),
                        NeakasaCalibrateFoodScaleButton(
                            coordinator, device_info, iot_id
                        ),
                        NeakasaMarkWaterBinCleanButton(
                            coordinator, device_info, iot_id
                        ),
                        NeakasaMarkFoodBinCleanButton(coordinator, device_info, iot_id),
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

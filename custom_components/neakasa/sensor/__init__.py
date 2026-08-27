"""Sensor platform for Neakasa."""

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
from .bin_state import NeakasaBinStateSensor
from .bucket_status import NeakasaBucketStatusSensor
from .cat_weight import NeakasaCatWeightSensor
from .last_usage import NeakasaLastUsageSensor
from .sand_level_state import NeakasaSandLevelStateSensor
from .sand_percent import NeakasaSandPercentSensor
from .stay_time import NeakasaStayTimeSensor
from .wifi_rssi import NeakasaWifiRssiSensor


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities for all discovered devices."""
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
                NeakasaSandPercentSensor(coordinator, device_info, iot_id),
                NeakasaWifiRssiSensor(coordinator, device_info, iot_id),
                NeakasaStayTimeSensor(coordinator, device_info, iot_id),
                NeakasaLastUsageSensor(coordinator, device_info, iot_id),
                NeakasaBucketStatusSensor(coordinator, device_info, iot_id),
                NeakasaSandLevelStateSensor(coordinator, device_info, iot_id),
                NeakasaBinStateSensor(coordinator, device_info, iot_id),
            ])
            entities.extend(
                NeakasaCatWeightSensor(
                    coordinator, device_info, iot_id,
                    cat_name=cat["name"], cat_id=cat["id"],
                )
                for cat in snap.cat_list
            )
        async_add_entities(entities)

    _discover()
    config_entry.async_on_unload(coordinator.async_add_listener(_discover))

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
from .battery import NeakasaBatterySensor
from .bin_state import NeakasaBinStateSensor
from .bowl_weight import NeakasaBowlWeightSensor
from .bucket_status import NeakasaBucketStatusSensor
from .cat_weight import NeakasaCatWeightSensor
from .cloud_session import NeakasaCloudSessionStatusSensor
from .desiccant_days_left import NeakasaDesiccantDaysLeftSensor
from .device_serial import NeakasaDeviceSerialSensor
from .firmware_version import NeakasaFirmwareVersionSensor
from .food_intake_today import NeakasaFoodIntakeTodaySensor
from .food_level import NeakasaFoodLevelSensor
from .label import NeakasaLabelSensor
from .last_bin_clean_food import NeakasaFoodBinCleanSensor
from .last_bin_clean_water import NeakasaWaterBinCleanSensor
from .last_usage import NeakasaLastUsageSensor
from .sand_level_state import NeakasaSandLevelStateSensor
from .sand_percent import NeakasaSandPercentSensor
from .stay_time import NeakasaStayTimeSensor
from .water_level import NeakasaWaterLevelSensor
from .wifi_rssi import NeakasaWifiRssiSensor


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities for all discovered devices."""
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
            # The account-level entities exist once per config entry, not once
            # per device: what they describe is the account, not a machine.
            _account_added = True
            entities.append(
                NeakasaCloudSessionStatusSensor(
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
            entities.append(NeakasaLabelSensor(coordinator, device_info, iot_id))
            if snap.category_key == "petFeeder":
                entities.extend(
                    [
                        NeakasaFoodLevelSensor(coordinator, device_info, iot_id),
                        NeakasaWaterLevelSensor(coordinator, device_info, iot_id),
                        NeakasaBatterySensor(coordinator, device_info, iot_id),
                        NeakasaWifiRssiSensor(coordinator, device_info, iot_id),
                        NeakasaBowlWeightSensor(coordinator, device_info, iot_id),
                        NeakasaDesiccantDaysLeftSensor(
                            coordinator, device_info, iot_id
                        ),
                        NeakasaDeviceSerialSensor(coordinator, device_info, iot_id),
                        NeakasaFirmwareVersionSensor(coordinator, device_info, iot_id),
                        NeakasaFoodIntakeTodaySensor(coordinator, device_info, iot_id),
                        NeakasaWaterBinCleanSensor(coordinator, device_info, iot_id),
                        NeakasaFoodBinCleanSensor(coordinator, device_info, iot_id),
                    ]
                )
                continue
            entities.extend(
                [
                    NeakasaSandPercentSensor(coordinator, device_info, iot_id),
                    NeakasaWifiRssiSensor(coordinator, device_info, iot_id),
                    NeakasaStayTimeSensor(coordinator, device_info, iot_id),
                    NeakasaLastUsageSensor(coordinator, device_info, iot_id),
                    NeakasaBucketStatusSensor(coordinator, device_info, iot_id),
                    NeakasaSandLevelStateSensor(coordinator, device_info, iot_id),
                    NeakasaBinStateSensor(coordinator, device_info, iot_id),
                ]
            )
            entities.extend(
                NeakasaCatWeightSensor(
                    coordinator,
                    device_info,
                    iot_id,
                    cat_name=cat["name"],
                    cat_id=cat["id"],
                )
                for cat in snap.cat_list
            )
        async_add_entities(entities)

    _discover()
    config_entry.async_on_unload(coordinator.async_add_listener(_discover))

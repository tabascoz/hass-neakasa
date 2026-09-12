"""Coordinator that fetches and caches device data for all Neakasa devices."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import timedelta
from typing import TYPE_CHECKING, Any, ClassVar

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api_manager import clear_shared_api, force_reconnect_api, get_shared_api
from .const import _LOGGER, DOMAIN
from .exceptions import (
    NeakasaApiClientAuthenticationError,
    NeakasaApiClientCommunicationError,
    NeakasaApiClientError,
    NeakasaApiClientSessionExpiredError,
)
from .value_cacher import ValueCacher

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .api_client import NeakasaApiClient

_clean_cfg_warnings_logged: set[str] = set()


@dataclass
class NeakasaDeviceSnapshot:
    """Immutable snapshot of a single device's state at a point in time."""

    iot_id: str
    device_name: str
    category_key: str
    product_key: str
    bin_full: bool
    clean_cfg: dict[str, Any]
    sand_level_state: int
    sand_level_percent: int
    bucket_status: int
    room_of_bin: int
    young_cat_mode: bool
    child_lock: bool
    auto_bury: bool
    auto_level: bool
    silent_mode: bool
    wifi_rssi: int
    auto_force_init: bool
    b_intrpt_range_det: bool
    stay_time: int
    last_use: int
    cat_list: list[dict[str, Any]] = field(default_factory=list)
    record_list: list[dict[str, Any]] = field(default_factory=list)


NeakasaPayload = dict[str, NeakasaDeviceSnapshot]


# ---------------------------------------------------------------------------
# Wire-value helpers
# ---------------------------------------------------------------------------


def _property_value(devicedata: Any, key: str, default: Any = None) -> Any:
    """Return the ``value`` field for *key* in the Aliyun IoT property wrapper."""
    if not isinstance(devicedata, dict):
        return default
    entry = devicedata.get(key)
    if not isinstance(entry, dict):
        return default
    return entry.get("value", default)


def _to_int(value: Any, default: int = 0) -> int:
    """Coerce a wire value to int, returning *default* on failure."""
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_list(value: Any) -> list[dict[str, Any]]:
    """Coerce a wire value to a list of dicts, returning [] on failure."""
    if isinstance(value, list):
        return value
    if value is None:
        return []
    if isinstance(value, (dict, tuple)):
        return list(value)
    return []


def _get_last_use_date(devicedata: Any) -> int:
    """Extract the ``catLeft.time`` timestamp from device properties."""
    if not isinstance(devicedata, dict):
        return 0
    cat_left = devicedata.get("catLeft")
    if not isinstance(cat_left, dict):
        return 0
    return cat_left.get("time", 0)


def _build_device_snapshot(
    iot_id: str,
    device_name: str,
    devicedata: Any,
    records: Any,
    new_last_use: int,
    *,
    category_key: str = "CatLitter",
    product_key: str = "",
) -> NeakasaDeviceSnapshot:
    """Build a :class:`NeakasaDeviceSnapshot` without crashing on missing keys."""
    if not isinstance(devicedata, dict):
        devicedata = {}
    if not isinstance(records, dict):
        records = {}

    sand = _property_value(devicedata, "Sand", {})
    if not isinstance(sand, dict):
        sand = {}
    network = _property_value(devicedata, "NetWorkStatus", {})
    if not isinstance(network, dict):
        network = {}
    cat_left_value = _property_value(devicedata, "catLeft", {})
    if not isinstance(cat_left_value, dict):
        cat_left_value = {}
    clean_cfg = _property_value(devicedata, "cleanCfg", {})
    if not isinstance(clean_cfg, dict):
        clean_cfg = {}

    expected_keys = (
        "binFullWaitReset",
        "cleanCfg",
        "youngCatMode",
        "childLockOnOff",
        "autoBury",
        "autoLevel",
        "silentMode",
        "autoForceInit",
        "bIntrptRangeDet",
        "Sand",
        "NetWorkStatus",
        "bucketStatus",
        "room_of_bin",
        "catLeft",
    )
    missing_keys = [key for key in expected_keys if key not in devicedata]
    if missing_keys:
        _LOGGER.debug(
            "Neakasa device %s missing keys %s (available: %s)",
            iot_id,
            missing_keys,
            list(devicedata.keys()),
        )

    if "cleanCfg" in missing_keys and iot_id not in _clean_cfg_warnings_logged:
        _clean_cfg_warnings_logged.add(iot_id)
        _LOGGER.warning(
            "Neakasa device %s did not report the 'cleanCfg' property; "
            "the auto-clean switch will be unavailable. Available properties: %s",
            iot_id,
            list(devicedata.keys()),
        )

    return NeakasaDeviceSnapshot(
        iot_id=iot_id,
        device_name=device_name,
        category_key=category_key,
        product_key=product_key,
        bin_full=_property_value(devicedata, "binFullWaitReset", 0) == 1,
        clean_cfg=clean_cfg,
        young_cat_mode=_property_value(devicedata, "youngCatMode", 0) == 1,
        child_lock=_property_value(devicedata, "childLockOnOff", 0) == 1,
        auto_bury=_property_value(devicedata, "autoBury", 0) == 1,
        auto_level=_property_value(devicedata, "autoLevel", 0) == 1,
        silent_mode=_property_value(devicedata, "silentMode", 0) == 1,
        auto_force_init=_property_value(devicedata, "autoForceInit", 0) == 1,
        b_intrpt_range_det=_property_value(devicedata, "bIntrptRangeDet", 0) == 1,
        sand_level_percent=_to_int(sand.get("percent", 0)),
        wifi_rssi=_to_int(network.get("WiFi_RSSI", 0)),
        bucket_status=_to_int(_property_value(devicedata, "bucketStatus", 0)),
        room_of_bin=_to_int(_property_value(devicedata, "room_of_bin", 0)),
        sand_level_state=_to_int(sand.get("level", 0)),
        stay_time=_to_int(cat_left_value.get("stayTime", 0)),
        last_use=new_last_use,
        cat_list=_to_list(records.get("cat_list")),
        record_list=_to_list(records.get("record_list")),
    )


class NeakasaCoordinator(DataUpdateCoordinator[NeakasaPayload]):
    """Coordinator that fetches all Neakasa devices under one account."""

    _SNAP_TO_WIRE: ClassVar[dict[str, str]] = {
        "young_cat_mode": "youngCatMode",
        "child_lock": "childLockOnOff",
        "auto_bury": "autoBury",
        "auto_level": "autoLevel",
        "silent_mode": "silentMode",
        "auto_force_init": "autoForceInit",
        "b_intrpt_range_det": "bIntrptRangeDet",
        "clean_cfg": "cleanCfg",
        "bin_full": "binFullWaitReset",
    }

    # ------------------------------------------------------------------
    # Product-type routing
    # ------------------------------------------------------------------
    # When adding a new Neakasa product:
    # 1. Add its categoryKey to ``KNOWN_PRODUCT_TYPES``
    # 2. Create entity classes under a new platform sub-package
    # 3. Register the platform in ``__init__.py``
    # 4. Add translations keys to ``translations/en.json``

    KNOWN_PRODUCT_TYPES: ClassVar[set[str]] = {
        "CatLitter",
        # "WashingMachine",   # future
        # "CatFoodFeeder",    # future
        # "CatWaterFountain", # future
    }

    _SERVICE_DISPATCH: ClassVar[dict[str, dict[str, str]]] = {
        "CatLitter": {
            "clean": "clean_now",
            "level": "sand_leveling",
        },
        # "WashingMachine": {"start": "start_wash", "pause": "pause_wash"},
        # "CatFoodFeeder": {"dispense": "dispense_food"},
    }

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the coordinator from a config entry."""
        self.config_entry = config_entry
        self.username = config_entry.data[CONF_USERNAME]
        self.password = config_entry.data[CONF_PASSWORD]

        self._records_caches: dict[str, ValueCacher] = {}
        self._properties_caches: dict[str, ValueCacher] = {}
        self._last_use_dates: dict[str, int] = {}
        self._device_names: dict[str, str] = {}
        self._device_meta: dict[str, dict[str, str]] = {}
        self._device_ids: list[str] = []

        scan_interval = config_entry.options.get("scan_interval", 60)
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} ({config_entry.unique_id})",
            update_method=self.async_update_data,
            update_interval=timedelta(seconds=scan_interval),
            config_entry=config_entry,
        )

    # ------------------------------------------------------------------
    # Public helpers for entities
    # ------------------------------------------------------------------

    def device_snapshot(self, iot_id: str) -> NeakasaDeviceSnapshot | None:
        """Return the latest snapshot for *iot_id*, or None if unavailable."""
        return self.data.get(iot_id) if self.data else None

    @property
    def device_ids(self) -> list[str]:
        """Return the list of known device IOT IDs."""
        return self._device_ids

    def device_category(self, iot_id: str) -> str:
        """Return the ``categoryKey`` for *iot_id*, e.g. ``"CatLitter"``."""
        snap = self.device_snapshot(iot_id)
        return snap.category_key if snap else "unknown"

    async def set_property(self, iot_id: str, key: str, value: Any) -> None:
        """Set a device property via the Aliyun IoT gateway."""
        client = await self._get_client()
        wire_key = self._SNAP_TO_WIRE.get(key, key)
        await client.set_device_properties(iot_id, {wire_key: value})
        if self.data and iot_id in self.data:
            setattr(self.data[iot_id], key, value)
            self.async_set_updated_data(self.data)

    async def invoke_service(self, iot_id: str, service: str) -> None:
        """Invoke a device service (clean or level)."""
        client = await self._get_client()
        match service:
            case "clean":
                await client.clean_now(iot_id)
            case "level":
                await client.sand_leveling(iot_id)
            case _:
                msg = f"Unknown service: {service}"
                raise ValueError(msg)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get_client(self) -> NeakasaApiClient:
        """Return the shared API client for this coordinator's credentials."""
        return await get_shared_api(self.hass, self.username, self.password)

    async def _discover_devices(self) -> list[dict[str, Any]]:
        """Fetch all known Neakasa devices for the account."""
        client = await self._get_client()
        all_devices = await client.get_devices()
        matched: list[dict[str, Any]] = []
        for d in all_devices:
            cat_key: str = d.get("categoryKey", "")
            if cat_key in self.KNOWN_PRODUCT_TYPES:
                iot_id: str = d.get("iotId", "")
                self._device_meta[iot_id] = {
                    "category_key": cat_key,
                    "product_key": d.get("productKey", ""),
                }
                matched.append(d)
        return matched

    def _cache_for(self, iot_id: str) -> tuple[ValueCacher, ValueCacher]:
        """Return (records_cache, properties_cache) for *iot_id*."""
        if iot_id not in self._records_caches:
            self._records_caches[iot_id] = ValueCacher(
                refresh_after=timedelta(minutes=30),
                discard_after=timedelta(hours=4),
            )
        if iot_id not in self._properties_caches:
            self._properties_caches[iot_id] = ValueCacher(
                refresh_after=timedelta(seconds=0),
                discard_after=timedelta(minutes=30),
            )
        return self._records_caches[iot_id], self._properties_caches[iot_id]

    async def _get_device_name(self, iot_id: str) -> str:
        """Resolve a user-facing device name from its IOT ID."""
        if iot_id in self._device_names:
            return self._device_names[iot_id]
        client = await self._get_client()
        devices = await client.get_devices()
        for d in devices:
            if d.get("iotId") == iot_id:
                name = d.get("deviceName") or iot_id
                self._device_names[iot_id] = name
                return name
        self._device_names[iot_id] = iot_id
        return iot_id

    async def _get_records(self, iot_id: str) -> Any:
        """Fetch cached usage records for *iot_id*."""
        records_cache, _ = self._cache_for(iot_id)

        async def fetch() -> Any:
            device_name = await self._get_device_name(iot_id)
            client = await self._get_client()
            return await client.get_records(device_name)

        return await records_cache.get_or_update(fetch)

    async def _get_properties(self, iot_id: str) -> Any:
        """Fetch cached device properties for *iot_id*."""
        _, props_cache = self._cache_for(iot_id)

        async def fetch() -> Any:
            client = await self._get_client()
            return await client.get_device_properties(iot_id)

        return await props_cache.get_or_update(fetch)

    async def _fetch_single_device(self, iot_id: str) -> NeakasaDeviceSnapshot:
        """Fetch properties and records for one device, building a snapshot."""
        devicedata = await self._get_properties(iot_id)
        new_last_use = _get_last_use_date(devicedata)

        records_cache, _ = self._cache_for(iot_id)
        if self._last_use_dates.get(iot_id) != new_last_use:
            records_cache.mark_as_stale()
        self._last_use_dates[iot_id] = new_last_use

        records = await self._get_records(iot_id)
        device_name = await self._get_device_name(iot_id)
        meta = self._device_meta.get(iot_id, {})
        return _build_device_snapshot(
            iot_id,
            device_name,
            devicedata,
            records,
            new_last_use,
            category_key=meta.get("category_key", "CatLitter"),
            product_key=meta.get("product_key", ""),
        )

    # ------------------------------------------------------------------
    # Reconnection helpers
    # ------------------------------------------------------------------

    async def _reconnect_and_retry(self) -> NeakasaPayload:
        """
        Clear the cached API client and retry the update.

        Used by session-expiry, auth, and identityId recovery paths.
        Raises :class:`UpdateFailed` if reconnection itself fails.
        """
        try:
            await force_reconnect_api(self.hass, self.username, self.password)
        except NeakasaApiClientError as reconnect_err:
            msg = "Reconnection failed"
            raise UpdateFailed(msg) from reconnect_err
        else:
            return await self.async_update_data()

    async def _reconnect_clear_and_retry(self) -> NeakasaPayload:
        """
        Fully clear the shared API and retry from scratch.

        Used for identityId-blank errors where a partial reconnect is insufficient.
        """
        clear_shared_api(self.username, self.password)
        return await self._reconnect_and_retry()

    # ------------------------------------------------------------------
    # Main update loop
    # ------------------------------------------------------------------

    async def async_update_data(self) -> NeakasaPayload:
        """Fetch fresh data from all CatLitter devices on the account."""
        try:
            devices = await self._discover_devices()
            self._device_ids = [d["iotId"] for d in devices]

            snapshots = await asyncio.gather(
                *(self._fetch_single_device(iot_id) for iot_id in self._device_ids),
                return_exceptions=True,
            )

            payload: NeakasaPayload = {}
            for iot_id, result in zip(self._device_ids, snapshots, strict=False):
                if isinstance(result, BaseException):
                    _LOGGER.error("Failed to fetch device %s: %s", iot_id, result)
                    continue
                payload[iot_id] = result

            _LOGGER.debug("Coordinator update complete: %d devices", len(payload))
            return payload  # noqa: TRY300

        except NeakasaApiClientSessionExpiredError as err:
            _LOGGER.warning("Session expired, reconnecting silently: %s", err)
            try:
                payload = await self._reconnect_and_retry()
            except Exception as exc:
                _LOGGER.warning("Reconnect+retry FAILED after session expiry: %s", exc)
                raise
            else:
                _LOGGER.info(
                    "Reconnect+retry SUCCEEDED after session expiry — %d devices",
                    len(payload),
                )
                return payload

        except NeakasaApiClientAuthenticationError as err:
            _LOGGER.warning("Authentication error, attempting reconnect: %s", err)
            try:
                return await self._reconnect_and_retry()
            except UpdateFailed:
                _LOGGER.info(
                    "Starting reauth flow for entry %s", self.config_entry.entry_id
                )
                self.hass.async_create_task(
                    self.config_entry.async_start_reauth(self.hass)
                )
                raise

        except NeakasaApiClientCommunicationError as err:
            if "identityId is blank" in str(err):
                _LOGGER.debug("IdentityId error, attempting automatic reconnection")
                return await self._reconnect_clear_and_retry()

            _LOGGER.warning("API communication error (retrying): %s", err)
            for delay in (2, 4, 8, 16, 32):
                _LOGGER.debug("Retrying after %ds ...", delay)
                await asyncio.sleep(delay)
                try:
                    return await self.async_update_data()
                except NeakasaApiClientCommunicationError:
                    continue
            _LOGGER.error("API communication error after all retries: %s", err)
            msg = f"Communication error after 5 retries: {err}"
            raise UpdateFailed(msg) from err

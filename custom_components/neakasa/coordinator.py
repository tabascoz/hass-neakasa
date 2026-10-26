"""Coordinator that fetches and caches device data for all Neakasa devices."""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, ClassVar

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api_manager import clear_shared_api, force_reconnect_api, get_shared_api
from .const import (
    _LOGGER,
    DEFAULT_FEED_FOOD_G,
    DEFAULT_FEED_WATER_RATIO,
    DOMAIN,
    FEED_FOOD_MAX_G,
    FEED_FOOD_MIN_G,
    FEED_WATER_RATIO_MAX,
    FEED_WATER_RATIO_MIN,
    SUPPORTED_CATEGORY_KEYS,
)
from .exceptions import (
    NeakasaApiClientAuthenticationError,
    NeakasaApiClientCommunicationError,
    NeakasaApiClientError,
    NeakasaApiClientSessionExpiredError,
)
from .log_redact import device_label, entry_label
from .value_cacher import ValueCacher

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .api_client import NeakasaApiClient

# Listing the account's devices is an account presentation: it moves the
# session, so how often it happens is what makes the Neakasa app sign in
# again. Six hours keeps us near two presentations an hour, through the
# records path; the Refresh data now button and a config reload find a
# device you just added. The value this replaces was 10 minutes: six
# presentations an hour on the 5-minute scan cadence this entry runs.
DEVICE_LIST_REFRESH_MINUTES = 6 * 60

# A full re-login mints a new session for the account, so it is done at most
# once per cooldown; renewing the IoT token (one call) is tried first.
FULL_REAUTH_COOLDOWN_SECONDS = 600
# Temporary test tool: sign-ins one debug press performs, see debug_token_churn.
DEBUG_TOKEN_CHURN_CYCLES = 3
# The wordings the account web API uses when the login token aged; that token
# is what /catbox/record sends, so only a sign-in replaces it.
_TOKEN_INVALID_PHRASES: tuple[str, ...] = ("tokeninvalid", "token is abnormal")
# Consecutive recoveries inside one update, so a persistently rejected token
# cannot keep asking for sessions.
MAX_SESSION_RECOVERY_ATTEMPTS = 2
# Presenting the account to the cloud is what moves the session away from
# whoever else holds it, whether the request is accepted or refused, and the
# IoT token exchange (/account/createSessionByAuthCode) does the same -
# measured on 2026-10-26: an accepted device-list call at 17:04:48 left the
# mobile app needing a sign-in, a token exchange at 17:15:15 was followed by
# one 15 seconds later, and a scan at 17:10:14 whose device reads went
# through unchanged left the app usable for minutes afterwards. A refusal is
# reported and what we hold is served, but nothing is skipped: reading stays
# on the scan cadence, and the account sensor says who we last saw holding it.

# What the account sensor reports: which client the session belongs to. The
# values are what rules, templates and actions compare against, so they stay
# lowercase slugs; the words you see in the UI come from the state maps in
# translations/. A refusal only ever proves that our token is no longer the
# one holding the session - the cloud may equally have let that session age
# out - so the value says not_home_assistant instead of naming an app.
SESSION_OWNER_HOME_ASSISTANT = "home_assistant"
SESSION_OWNER_NOT_HOME_ASSISTANT = "not_home_assistant"
SESSION_OWNER_UNKNOWN = "unknown"
CLOUD_SESSION_OWNERS: tuple[str, ...] = (
    SESSION_OWNER_UNKNOWN,
    SESSION_OWNER_HOME_ASSISTANT,
    SESSION_OWNER_NOT_HOME_ASSISTANT,
)


def _utc_stamp() -> str:
    """Return the current time as the account sensor will print it."""
    return datetime.now(UTC).isoformat(timespec="seconds")


CATLITTER_EXPECTED_KEYS: tuple[str, ...] = (
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

PETFEEDER_EXPECTED_KEYS: tuple[str, ...] = (
    "foodLvl",
    "waterLvl",
    "pwrStatus",
    "bowlStatus",
    "bCoverAbsent",
    "leftDrierDays",
    "deviceState",
    "freshMgrCfg",
    "deepCleanCfg",
    "NetWorkStatus",
)

_missing_keys_logged: set[str] = set()
_clean_cfg_warnings_logged: set[str] = set()


def _log_missing_property_keys(
    iot_id: str, devicedata: dict[str, Any], expected: tuple[str, ...]
) -> list[str]:
    """
    Log (once per device) any *expected* wire keys absent from *devicedata*.

    Returns the missing keys so callers can use them for diagnostics. A future
    firmware or feature change is self-announcing instead of silently defaulting.
    """
    missing = [key for key in expected if key not in devicedata]
    if missing and iot_id not in _missing_keys_logged:
        _missing_keys_logged.add(iot_id)
        _LOGGER.debug(
            "Neakasa device %s missing keys %s (available: %s)",
            device_label(iot_id),
            missing,
            list(devicedata.keys()),
        )
    return missing


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
    label: str = ""
    cat_list: list[dict[str, Any]] = field(default_factory=list)
    record_list: list[dict[str, Any]] = field(default_factory=list)
    # Riko (petFeeder) fields — unused by CatLitter devices.
    food_level_state: int = 0
    water_level_state: int = 0
    battery_percent: int | None = None
    battery_level: int | None = None
    bowl_present: bool = False
    cover_absent: bool = False
    desiccant_days_left: int | None = None
    fresh_mgr_on: bool = False
    deep_clean_on: bool = False
    default_food_g: int | None = None
    default_water_ratio: int | None = None
    feed_cfg: dict[str, Any] | None = None


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


def _configured_feed_defaults(def_fd: dict[str, Any]) -> tuple[int | None, int | None]:
    """
    Map a wire ``defFdCfg`` (water stored in grams) to a portion and a ratio.

    Returns ``None`` for both when the machine reports no configured defaults.
    """
    food_g = _to_int(def_fd.get("food", 0))
    water_g = _to_int(def_fd.get("water", 0))
    if not FEED_FOOD_MIN_G <= food_g <= FEED_FOOD_MAX_G or water_g <= 0:
        return None, None
    ratio = max(
        FEED_WATER_RATIO_MIN, min(FEED_WATER_RATIO_MAX, round(water_g / food_g))
    )
    return food_g, ratio


def _build_device_snapshot(
    iot_id: str,
    device_name: str,
    devicedata: Any,
    records: Any,
    new_last_use: int,
    *,
    category_key: str = "CatLitter",
    product_key: str = "",
    label: str = "",
) -> NeakasaDeviceSnapshot:
    """Build a :class:`NeakasaDeviceSnapshot` without crashing on missing keys."""
    if not isinstance(devicedata, dict):
        devicedata = {}
    if not isinstance(records, dict):
        records = {}

    network = _property_value(devicedata, "NetWorkStatus", {})
    if not isinstance(network, dict):
        network = {}

    if category_key == "petFeeder":
        return _build_pet_feeder_snapshot(
            iot_id, device_name, devicedata, product_key, label
        )

    sand = _property_value(devicedata, "Sand", {})
    if not isinstance(sand, dict):
        sand = {}
    cat_left_value = _property_value(devicedata, "catLeft", {})
    if not isinstance(cat_left_value, dict):
        cat_left_value = {}
    clean_cfg = _property_value(devicedata, "cleanCfg", {})
    if not isinstance(clean_cfg, dict):
        clean_cfg = {}

    _log_missing_property_keys(iot_id, devicedata, CATLITTER_EXPECTED_KEYS)

    if "cleanCfg" not in devicedata and iot_id not in _clean_cfg_warnings_logged:
        _clean_cfg_warnings_logged.add(iot_id)
        _LOGGER.warning(
            "Neakasa device %s did not report the 'cleanCfg' property; "
            "the auto-clean switch will be unavailable. Available properties: %s",
            device_label(iot_id),
            list(devicedata.keys()),
        )

    return NeakasaDeviceSnapshot(
        iot_id=iot_id,
        device_name=device_name,
        category_key=category_key,
        product_key=product_key,
        label=label,
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


def _build_pet_feeder_snapshot(
    iot_id: str,
    device_name: str,
    devicedata: dict[str, Any],
    product_key: str,
    label: str,
) -> NeakasaDeviceSnapshot:
    """Build a snapshot for a Riko wet-meal feeder (categoryKey ``petFeeder``)."""
    _log_missing_property_keys(iot_id, devicedata, PETFEEDER_EXPECTED_KEYS)
    network = _property_value(devicedata, "NetWorkStatus", {})
    if not isinstance(network, dict):
        network = {}
    pwr = _property_value(devicedata, "pwrStatus", {})
    if not isinstance(pwr, dict):
        pwr = {}
    bowl = _property_value(devicedata, "bowlStatus", {})
    if not isinstance(bowl, dict):
        bowl = {}
    fresh_mgr = _property_value(devicedata, "freshMgrCfg", {})
    if not isinstance(fresh_mgr, dict):
        fresh_mgr = {}
    deep_clean = _property_value(devicedata, "deepCleanCfg", {})
    if not isinstance(deep_clean, dict):
        deep_clean = {}
    def_fd = _property_value(devicedata, "defFdCfg", {})
    if not isinstance(def_fd, dict):
        def_fd = {}
    device_state = _property_value(devicedata, "deviceState", {})
    if not isinstance(device_state, dict):
        device_state = {}

    battery_percent_raw = pwr.get("batPercentage")
    desiccant_raw = _property_value(devicedata, "leftDrierDays")
    default_food_g, default_water_ratio = _configured_feed_defaults(def_fd)

    return NeakasaDeviceSnapshot(
        iot_id=iot_id,
        device_name=device_name,
        category_key="petFeeder",
        product_key=product_key,
        label=label,
        bin_full=False,
        clean_cfg={},
        sand_level_state=0,
        sand_level_percent=0,
        bucket_status=_to_int(device_state.get("state", 0)),
        room_of_bin=0,
        young_cat_mode=False,
        child_lock=_property_value(devicedata, "childLockOnOff", 0) == 1,
        auto_bury=False,
        auto_level=False,
        silent_mode=False,
        wifi_rssi=_to_int(network.get("WiFi_RSSI", 0)),
        auto_force_init=False,
        b_intrpt_range_det=False,
        stay_time=0,
        last_use=0,
        food_level_state=_to_int(_property_value(devicedata, "foodLvl", 0)),
        water_level_state=_to_int(_property_value(devicedata, "waterLvl", 0)),
        battery_percent=(
            None if battery_percent_raw is None else _to_int(battery_percent_raw)
        ),
        battery_level=(
            None if pwr.get("batLevel") is None else _to_int(pwr.get("batLevel"))
        ),
        bowl_present=_to_int(bowl.get("bBowlIn", 0)) == 1,
        cover_absent=_property_value(devicedata, "bCoverAbsent", 1) == 0,
        desiccant_days_left=(None if desiccant_raw is None else _to_int(desiccant_raw)),
        fresh_mgr_on=_to_int(fresh_mgr.get("bOnOff", 0)) == 1,
        deep_clean_on=_to_int(deep_clean.get("bOnOff", 0)) == 1,
        default_food_g=default_food_g,
        default_water_ratio=default_water_ratio,
        feed_cfg=dict(def_fd) if def_fd else None,
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

    KNOWN_PRODUCT_TYPES: ClassVar[frozenset[str]] = SUPPORTED_CATEGORY_KEYS

    _SERVICE_DISPATCH: ClassVar[dict[str, dict[str, str]]] = {
        "CatLitter": {
            "clean": "clean_now",
            "level": "sand_leveling",
        },
        "petFeeder": {
            "feed": "feed_once",  # /thing/service/invoke identifier feedOnce
        },
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
        self._account_devices: list[dict[str, Any]] = []
        self._devices_cache = ValueCacher(
            refresh_after=timedelta(minutes=DEVICE_LIST_REFRESH_MINUTES),
            discard_after=None,
        )
        self._last_full_auth: float | None = None
        self._recovery_attempts = 0
        self._pending_feed: dict[str, dict[str, int | None]] = {}
        self._feed_keep_as_new_defaults: dict[str, bool] = {}
        self._last_feed: dict[str, dict[str, Any]] = {}
        self._state_base: dict[str, str] = {}
        self._state_fingerprints: dict[str, Any] = {}
        self._state_manual_bumps: dict[str, int] = {}
        # Which client the account session belongs to, as last observed: we only
        # learn it by presenting the account, so it stays unknown until a scan
        # has asked.
        self._session_owner = SESSION_OWNER_UNKNOWN
        # Whether the account refused our last attempt, which is what makes the
        # record-based values ones we are holding rather than ones we read now.
        self._session_refused = False
        # When each claim was made, so the account sensor can show its evidence.
        # These are printable stamps only; nothing here depends on the clock.
        self._last_presented_when: str | None = None

        self._last_presented_call: str | None = None
        self._refused_when: str | None = None

        scan_interval = config_entry.options.get("scan_interval", 60)
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} ({entry_label(config_entry.entry_id)})",
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

    async def async_get_device_schema(self) -> dict[str, Any]:
        """
        Return a per-device wire schema for diagnostics/discovery.

        Exposes the raw property keys each device reports and the command/service
        schema from the product list, so missing Riko capabilities are visible in
        a shareable diagnostics download rather than guessed.
        """
        client = await self._get_client()
        products = await client.get_product_list()
        product_keys = {
            snap.product_key for snap in (self.data or {}).values() if snap.product_key
        }
        schema_by_product: dict[str, Any] = {}
        if isinstance(products, list):
            for entry in products:
                if (
                    not isinstance(entry, dict)
                    or entry.get("productKey") not in product_keys
                ):
                    continue
                schema_by_product[entry["productKey"]] = {
                    "categoryKey": entry.get("categoryKey"),
                    "productName": entry.get("name"),
                }

        devices: dict[str, Any] = {}
        for iot_id, snap in (self.data or {}).items():
            devicedata = await self._get_properties(iot_id, client)
            if not isinstance(devicedata, dict):
                devicedata = {}
            expected = (
                CATLITTER_EXPECTED_KEYS
                if snap.category_key != "petFeeder"
                else PETFEEDER_EXPECTED_KEYS
            )
            missing = [key for key in expected if key not in devicedata]
            devices[iot_id] = {
                "category_key": snap.category_key,
                "product_key": snap.product_key,
                "property_keys": sorted(devicedata),
                "missing_expected_keys": missing,
            }
            if snap.category_key == "petFeeder":
                devices[iot_id]["feed"] = {
                    "defFdCfg": _property_value(devicedata, "defFdCfg", {}),
                    "default_food_g": snap.default_food_g,
                    "default_water_ratio": snap.default_water_ratio,
                    "pending_feed": self._pending_feed.get(iot_id, {}),
                    "keep_as_new_defaults": self.feed_keep_as_new_defaults(iot_id),
                    "last_feed": self._last_feed.get(iot_id, {}),
                }
        return {"devices": devices, "products": schema_by_product}

    async def set_property(self, iot_id: str, key: str, value: Any) -> None:
        """Set a device property via the Aliyun IoT gateway."""
        client = await self._get_client()
        wire_key = self._SNAP_TO_WIRE.get(key, key)
        await client.set_device_properties(iot_id, {wire_key: value})
        if self.data and iot_id in self.data:
            setattr(self.data[iot_id], key, value)
            self._mark_state_changed(iot_id)
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
        if self.data and iot_id in self.data:
            # The machine ran a cycle, so the values that describe it are pushed
            # now: waiting for the next scan leaves Home Assistant showing the
            # state from before a press the user just made.
            self._mark_state_changed(iot_id)
            self.async_set_updated_data(self.data)

    def feed_values(self, iot_id: str) -> tuple[int, int]:
        """Return the portion (g) and water ratio the next feed would use."""
        pending = self._pending_feed.get(iot_id, {})
        snap = self.device_snapshot(iot_id)
        food_g = pending.get("food_g")
        if food_g is None and snap is not None:
            food_g = snap.default_food_g
        water_ratio = pending.get("water_ratio")
        if water_ratio is None and snap is not None:
            water_ratio = snap.default_water_ratio
        return (
            food_g if food_g is not None else DEFAULT_FEED_FOOD_G,
            water_ratio if water_ratio is not None else DEFAULT_FEED_WATER_RATIO,
        )

    def set_pending_feed(
        self,
        iot_id: str,
        *,
        food_g: int | None = None,
        water_ratio: int | None = None,
    ) -> None:
        """Remember amounts for the next feed; the machine itself is not written."""
        pending = self._pending_feed.setdefault(iot_id, {})
        if food_g is not None:
            pending["food_g"] = food_g
        if water_ratio is not None:
            pending["water_ratio"] = water_ratio
        if self.data and iot_id in self.data:
            self._mark_state_changed(iot_id)
            self.async_set_updated_data(self.data)

    def feed_keep_as_new_defaults(self, iot_id: str) -> bool:
        """
        Return whether a feed for *iot_id* stores the amounts it used.

        The per-device setting wins; the account option only seeds it, so devices
        that were never toggled behave as they did before.
        """
        stored = self._feed_keep_as_new_defaults.get(iot_id)
        if stored is not None:
            return stored
        return bool(self.config_entry.options.get("feed_keep_as_new_defaults", False))

    def last_feed(self, iot_id: str) -> dict[str, Any]:
        """Return the amounts the last feed for *iot_id* used, if any."""
        return dict(self._last_feed.get(iot_id, {}))

    def state_fingerprint(self, iot_id: str) -> Any:
        """
        Return the stamp that changes whenever the model for *iot_id* changes.

        Entities pass it to ``write_state_if_changed`` to skip reporting a state
        that cannot differ: a scan which rebuilt the same model leaves the stamp
        equal, so nothing is pushed to Home Assistant for it. Any user action
        which writes the model or stages values refreshes the stamp instead, so
        those changes are always reported. An unknown model returns None, which
        leaves entities reporting their unavailable state.
        """
        if self.device_snapshot(iot_id) is None:
            return None
        return self._state_fingerprints.get(iot_id)

    def _mark_state_changed(
        self,
        iot_id: str,
        props: Any = None,
        records: Any = None,
    ) -> None:
        """
        Refresh the stamp for *iot_id*.

        With *props* given, the stamp is taken from the wire payload just read, so
        a payload equal to the previous one gives an equal stamp. Without *props*,
        a user action changed the model directly and the stamp moves by a counter.
        """
        if props is not None:
            self._state_base[iot_id] = json.dumps(
                {"props": props, "records": records},
                sort_keys=True,
                default=str,
            )
        else:
            bumps = self._state_manual_bumps
            bumps[iot_id] = bump = bumps.get(iot_id, 0) + 1
            base = self._state_base.get(iot_id, "")
            self._state_base[iot_id] = f"{base} manual:{bump}"
        self._state_fingerprints[iot_id] = hash(
            (
                self._state_base[iot_id],
                json.dumps(
                    {
                        "pending": self._pending_feed.get(iot_id),
                        "keep": self._feed_keep_as_new_defaults.get(iot_id),
                        "last": self._last_feed.get(iot_id),
                    },
                    sort_keys=True,
                    default=str,
                ),
            )
        )

    def set_feed_keep_as_new_defaults(self, iot_id: str, *, value: bool) -> None:
        """Choose whether a feed for *iot_id* stores the amounts it used."""
        self._feed_keep_as_new_defaults[iot_id] = value
        if self.data and iot_id in self.data:
            self._mark_state_changed(iot_id)
            self.async_set_updated_data(self.data)

    async def feed_once(
        self,
        iot_id: str,
        food_g: int | None = None,
        water_ratio: int | None = None,
        *,
        save_as_default: bool | None = None,
    ) -> None:
        """
        Dispense one Riko wet meal.

        Observed wire shape: ``/thing/service/invoke`` identifier ``feedOnce`` with
        args ``{food: grams of food, water: grams of water, bSaveAsDef: 0|1}`` — the
        water argument is an amount of water, so the selected ratio is applied to the
        portion. Sending the ratio index instead made the machine keep adding water
        until it reported clogged water sprays. Omitted amounts fall back to the
        pending ones, then to the machine's stored defaults. ``bSaveAsDef`` asks the
        machine to keep the amounts it used; whether that flag is sent comes from
        the per-device switch ``feed_keep_as_new_defaults``, seeded from the
        account option of the same name. When storing, ``defFdCfg`` is written too.
        """
        fallback_food, fallback_ratio = self.feed_values(iot_id)
        food_g = food_g if food_g is not None else fallback_food
        water_ratio = water_ratio if water_ratio is not None else fallback_ratio
        self._validate_feed(food_g, water_ratio)
        keep = (
            save_as_default
            if save_as_default is not None
            else self.feed_keep_as_new_defaults(iot_id)
        )
        args = {
            "food": food_g,
            "water": food_g * water_ratio,
            "bSaveAsDef": 1 if keep else 0,
        }
        client = await self._get_client()
        _LOGGER.debug("Riko feedOnce %s: %s", device_label(iot_id), args)
        await client.invoke_service(iot_id, "feedOnce", args)
        self._last_feed[iot_id] = {"args": dict(args), "stored_defaults": keep}
        self._pending_feed.pop(iot_id, None)
        if keep:
            try:
                await self.set_feed_config(
                    iot_id, food_g=food_g, water_ratio=water_ratio
                )
                _LOGGER.debug(
                    "Riko stored defaults %s: food %d g, water %d g",
                    device_label(iot_id),
                    food_g,
                    food_g * water_ratio,
                )
            except NeakasaApiClientError as err:
                _LOGGER.warning(
                    "Failed to store the fed amounts as new defaults: %s", err
                )
        elif self.data and iot_id in self.data:
            self._mark_state_changed(iot_id)
            self.async_set_updated_data(self.data)

    def _validate_feed(self, food_g: int, water_ratio: int) -> None:
        """Raise ValueError if a feed portion/ratio is outside product bounds."""
        if not FEED_FOOD_MIN_G <= food_g <= FEED_FOOD_MAX_G:
            msg = (
                f"Food portion out of range: {food_g}g "
                f"(expected {FEED_FOOD_MIN_G}-{FEED_FOOD_MAX_G})"
            )
            raise ValueError(msg)
        if not FEED_WATER_RATIO_MIN <= water_ratio <= FEED_WATER_RATIO_MAX:
            msg = (
                f"Water ratio out of range: {water_ratio} "
                f"(expected {FEED_WATER_RATIO_MIN}-{FEED_WATER_RATIO_MAX})"
            )
            raise ValueError(msg)

    async def set_feed_config(self, iot_id: str, food_g: int, water_ratio: int) -> None:
        """
        Write the Riko feed defaults (portion and water ratio) to the machine.

        ``defFdCfg`` is a nested config object; new ``food``/``water`` are merged
        into the current value, preserving ``mixMin`` and any other keys. ``water``
        is written as an amount of water in grams (portion times ratio), which is the
        unit the machine stores. Confirmed through ``/thing/properties/set`` on a
        real Riko.
        """
        self._validate_feed(food_g, water_ratio)
        snap = self.data.get(iot_id) if self.data else None
        current_mix_min = 1
        if snap is not None and getattr(snap, "feed_cfg", None):
            current_mix_min = _to_int(snap.feed_cfg.get("mixMin", 1))
        payload = {
            "food": food_g,
            "water": food_g * water_ratio,
            "mixMin": current_mix_min,
        }
        client = await self._get_client()
        await client.set_device_properties(iot_id, {"defFdCfg": payload})
        if snap is not None:
            snap.default_food_g = food_g
            snap.default_water_ratio = water_ratio
            snap.feed_cfg = payload
            self._mark_state_changed(iot_id)
            self.async_set_updated_data(self.data)

    # ------------------------------------------------------------------
    # Debug probe (opt-in via options flow; never affects normal polling)
    # ------------------------------------------------------------------

    _DEBUG_PROBES: ClassVar[dict[str, tuple[str, str]]] = {
        "set_fresh_mgr_on": ("freshMgrCfg", "on"),
        "set_fresh_mgr_off": ("freshMgrCfg", "off"),
        "set_deep_clean_on": ("deepCleanCfg", "on"),
        "set_deep_clean_off": ("deepCleanCfg", "off"),
    }

    async def _run_debug_probe(self, payload: NeakasaPayload) -> None:
        """
        Exercise a user-selected write action once and log the wire result.

        Opt-in only (``debug_probe`` option); errors are swallowed so a
        mis-guessed identifier can never break polling. Runs a single time per
        selected probe rather than on every update.
        """
        probe = self.config_entry.options.get("debug_probe", "none")
        if probe == "none" or not payload:
            return
        if getattr(self, "_debug_probe_done", None) == (probe, self._device_ids):
            return

        target_iot_id = next(iter(payload), "")
        client = await self._get_client()
        try:
            match probe:
                case "invoke_custom":
                    identifier = str(
                        self.config_entry.options.get("debug_invoke_identifier", "")
                    )
                    raw_args = self.config_entry.options.get(
                        "debug_invoke_args_json", "{}"
                    )
                    args = json.loads(raw_args) if isinstance(raw_args, str) else {}
                    _LOGGER.debug("Debug probe invoke: %s %s", identifier, args)
                    await client.invoke_service(target_iot_id, identifier, args)
                case _ if probe in self._DEBUG_PROBES:
                    wire_key, mode = self._DEBUG_PROBES[probe]
                    current = await client.get_device_properties(target_iot_id)
                    cfg = dict(_property_value(current, wire_key, {}) or {})
                    cfg["bOnOff"] = 1 if mode == "on" else 0
                    _LOGGER.debug("Debug probe set %s=%s", wire_key, cfg)
                    await client.set_device_properties(target_iot_id, {wire_key: cfg})
                case _:
                    return
        except NeakasaApiClientError as err:
            _LOGGER.warning("Debug probe '%s' failed (ignored): %s", probe, err)
        else:
            self._debug_probe_done = (probe, list(self._device_ids))

    async def debug_token_churn(self, cycles: int = DEBUG_TOKEN_CHURN_CYCLES) -> None:
        """
        Sign in *cycles* times in a row so the account gains sessions.

        Temporary test tool for the app side: a natural token expiry costs
        exactly this, and waiting for one is slow. Each sign-in replaces the
        shared client, so after a press the account holds the same number of
        sessions it would have held after the same number of expiries.
        """
        for step in range(1, cycles + 1):
            _LOGGER.info("Debug token churn %d/%d: signing in", step, cycles)
            await force_reconnect_api(
                self.hass,
                self.username,
                self.password,
                f"debug token churn {step}/{cycles}",
            )
        _LOGGER.info("Debug token churn complete: %d sign-ins", cycles)

    async def debug_invalidate_tokens(self) -> None:
        """
        Break the tokens we hold so the next scan has to recover them.

        Temporary test tool for the branch's recovery path: the records call
        fails for the account token, which must be seen as an expired session
        and repaired by a sign-in.
        """
        client = await self._get_client()
        await client.debug_invalidate_tokens()
        _LOGGER.info("Debug tokens invalidated: the next scan must recover them")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get_client(
        self,
        cause: str = "coordinator asked for a client",
    ) -> NeakasaApiClient:
        """
        Return the shared API client for this coordinator's credentials.

        *cause* is passed on so that a sign-in this needs says why in the
        journal.
        """
        return await get_shared_api(self.hass, self.username, self.password, cause)

    async def _discover_devices(
        self, client: NeakasaApiClient | None = None
    ) -> list[dict[str, Any]]:
        """Return the account's devices, refetched at most every six hours."""

        async def fetch() -> list[dict[str, Any]]:
            return await self._fetch_account_devices(client)

        return await self._devices_cache.get_or_update(fetch)

    async def _fetch_account_devices(
        self, client: NeakasaApiClient | None = None
    ) -> list[dict[str, Any]]:
        """
        Fetch the account device list and register the supported ones.

        Presenting the account is what moves the session away from whoever else
        owns it, so a refusal here is evidence that another client holds it: the
        list we were last given is served instead, and the account sensor is
        told. A refusal with nothing held yet goes on as an error, because
        there is nothing to serve.
        """
        api_client = client if client is not None else await self._get_client()
        try:
            all_devices = await api_client.get_devices()
        except NeakasaApiClientSessionExpiredError as err:
            self._note_account_refused("device list", err)
            if not self._account_devices:
                raise
            return self._match_supported_devices(self._account_devices)
        # An accepted presentation is us holding the session: the state is ours
        # and the account sensor says we hold it.
        self._note_presented("device list")
        self._account_devices = all_devices
        return self._match_supported_devices(all_devices)

    def _match_supported_devices(
        self, devices: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Register the supported devices of *devices* and return them."""
        matched: list[dict[str, Any]] = []
        for d in devices:
            cat_key: str = d.get("categoryKey", "")
            if cat_key in self.KNOWN_PRODUCT_TYPES:
                iot_id: str = d.get("iotId", "")
                self._device_meta[iot_id] = {
                    "category_key": cat_key,
                    "product_key": d.get("productKey", ""),
                    "label": d.get("nickName", ""),
                }
                matched.append(d)
        return matched

    def force_refresh_devices(self) -> None:
        """Drop the cached device list so the next scan refetches it."""
        self._devices_cache.mark_as_stale()

    def _cache_for(self, iot_id: str) -> tuple[ValueCacher, ValueCacher]:
        """
        Return (records_cache, properties_cache) for *iot_id*.

        Records are only re-read when the device reports a new last-use, which
        is the one thing that can mean a new record exists: the cache is never
        stale on its own, so no scan is spent asking for records that cannot
        have changed. Properties always re-read, so the device values follow the
        scan interval.
        """
        if iot_id not in self._records_caches:
            self._records_caches[iot_id] = ValueCacher(
                refresh_after=None,
                discard_after=timedelta(hours=4),
            )
        if iot_id not in self._properties_caches:
            self._properties_caches[iot_id] = ValueCacher(
                refresh_after=timedelta(seconds=0),
                discard_after=timedelta(minutes=30),
            )
        return self._records_caches[iot_id], self._properties_caches[iot_id]

    async def _get_device_name(self, iot_id: str) -> str:
        """Resolve a user-facing device name, preferring the fetched device list."""
        if iot_id in self._device_names:
            return self._device_names[iot_id]
        for d in self._account_devices:
            if d.get("iotId") == iot_id:
                name = d.get("deviceName") or iot_id
                self._device_names[iot_id] = name
                return name
        client = await self._get_client()
        devices = await client.get_devices()
        self._account_devices = devices
        for d in devices:
            if d.get("iotId") == iot_id:
                name = d.get("deviceName") or iot_id
                self._device_names[iot_id] = name
                return name
        self._device_names[iot_id] = iot_id
        return iot_id

    async def _get_records(
        self, iot_id: str, client: NeakasaApiClient | None = None
    ) -> Any:
        """
        Fetch cached usage records for *iot_id*, reusing *client* when given.

        /catbox/record is signed with the account session, so asking it is what
        moves the session: when the account refuses it we are holding the
        records another client's session made, and we say so. A refusal with
        nothing held goes on as an error instead.
        """
        records_cache, _ = self._cache_for(iot_id)

        async def fetch() -> Any:
            device_name = await self._get_device_name(iot_id)
            api_client = client if client is not None else await self._get_client()
            try:
                records = await api_client.get_records(device_name)
            except NeakasaApiClientSessionExpiredError as err:
                self._note_account_refused("records", err)
                held = records_cache.value_if_not_discarded()
                if held is None:
                    raise
                return held
            self._note_presented("records")
            return records

        return await records_cache.get_or_update(fetch)

    async def _get_properties(
        self, iot_id: str, client: NeakasaApiClient | None = None
    ) -> Any:
        """Fetch device properties for *iot_id*, reusing *client* when given."""
        _, props_cache = self._cache_for(iot_id)

        async def fetch() -> Any:
            api_client = client if client is not None else await self._get_client()
            return await api_client.get_device_properties(iot_id)

        return await props_cache.get_or_update(fetch)

    async def _fetch_single_device(
        self, iot_id: str, client: NeakasaApiClient | None = None
    ) -> NeakasaDeviceSnapshot:
        """Fetch properties and records for one device, building a snapshot."""
        devicedata = await self._get_properties(iot_id, client)
        meta = self._device_meta.get(iot_id, {})
        category_key = meta.get("category_key", "CatLitter")

        if category_key != "CatLitter":
            # Only litter boxes expose cat/usage records; feeders do not.
            device_name = await self._get_device_name(iot_id)
            self._mark_state_changed(iot_id, devicedata, {})
            return _build_device_snapshot(
                iot_id,
                device_name,
                devicedata,
                {},
                0,
                category_key=category_key,
                product_key=meta.get("product_key", ""),
                label=meta.get("label", ""),
            )

        new_last_use = _get_last_use_date(devicedata)
        records_cache, _ = self._cache_for(iot_id)
        if self._last_use_dates.get(iot_id) != new_last_use:
            # A new last-use is the only thing that can mean a new record, so
            # the records are re-read on it and not otherwise.
            records_cache.mark_as_stale()
        self._last_use_dates[iot_id] = new_last_use

        records = await self._get_records(iot_id, client)
        device_name = await self._get_device_name(iot_id)
        self._mark_state_changed(iot_id, devicedata, records)
        return _build_device_snapshot(
            iot_id,
            device_name,
            devicedata,
            records,
            new_last_use,
            category_key=category_key,
            product_key=meta.get("product_key", ""),
            label=meta.get("label", ""),
        )

    # ------------------------------------------------------------------
    # Reconnection helpers
    # ------------------------------------------------------------------

    def _note_presented(self, what: str) -> None:
        """Record that we presented the account and the cloud accepted it."""
        self._session_owner = SESSION_OWNER_HOME_ASSISTANT
        self._session_refused = False
        self._last_presented_when = _utc_stamp()
        self._last_presented_call = what
        self._refused_when = None

    def _note_account_refused(self, what: str, err: BaseException) -> None:
        """Record that the account refused one of our calls."""
        self._session_owner = SESSION_OWNER_NOT_HOME_ASSISTANT
        self._session_refused = True
        self._refused_when = _utc_stamp()
        _LOGGER.warning(
            "The account refused '%s' (%s): another client holds the session, "
            "so its values stay as cached and the account sensor says so",
            what,
            err,
        )

    async def take_account_session_back(self, reason: str) -> None:
        """
        Sign in so the account session is ours again, and read what was refused.

        Costs one session, which is what the other client notices: it has to
        authenticate again. The re-auth cooldown does not apply here - taking
        control back on a button press is a decision of the user, not a
        reaction to a failure that should not be repeated.
        """
        self._last_full_auth = None
        await force_reconnect_api(self.hass, self.username, self.password, cause=reason)
        self._note_presented(f"session taken back ({reason})")
        # Having taken the session, the read that follows should use it: the
        # caches that served refused values are marked stale so they are read
        # again now.
        self.force_refresh_devices()
        for cache in [
            *self._records_caches.values(),
            *self._properties_caches.values(),
        ]:
            cache.mark_as_stale()

    @property
    def cloud_session_owner(self) -> str:
        """
        Which client the account session belongs to, as last observed.

        An accepted call proved we held it and a refusal proved we do not, so
        this is an observation of one moment rather than a fact about now: a
        session that stops being presented ages out on its own, which the run
        of 2026-10-26 measured with our client making no account call at all.
        The account sensor publishes the times beside the value, so a claim can
        be traced to the call that made it.
        """
        return self._session_owner

    @property
    def session_evidence(self) -> dict[str, Any]:
        """What the reported owner is based on, so the claim can be checked."""
        return {
            "last_presented_at": self._last_presented_when,
            "last_presented_call": self._last_presented_call,
            "refused_at": self._refused_when,
            "records_as_cached": self._session_refused,
        }

    @property
    def records_refused(self) -> bool:
        """Whether the record values we serve are ones we are holding."""
        return self._session_refused

    async def regain_cloud_session(self) -> None:
        """
        Take the account session back and refresh everything we can see.

        Costs one session: presenting the account is what moves it, so the
        mobile app has to sign in again after this press. It exists to make
        which client is current a user decision rather than a silent fight.
        """
        await self.take_account_session_back("user asked to refresh data")
        payload = await self.async_update_data()
        self.async_set_updated_data(payload)

    async def _renew_cloud_session(self) -> bool:
        """
        Renew the shared client's IoT token instead of signing in again.

        One call rather than the six a full re-login needs, and no sign-in -
        which is why it is tried before one. It is not free for the other
        client: the exchange resolves the account session, so it moves it, and
        the app has to sign in again after it (measured on 2026-10-26: an
        exchange at 17:15:15 was followed by the mobile app needing a sign-in
        at 17:15:30). Returns whether the renewal worked.
        """
        try:
            client = await self._get_client()
            await client.refresh_session()
        except NeakasaApiClientError as err:
            _LOGGER.debug("Cloud session renewal failed: %s", err)
            return False
        _LOGGER.debug("Renewed the cloud session without a full re-auth")
        return True

    async def _force_full_reauth(self, reason: str) -> bool:
        """
        Sign in from scratch, at most once per cooldown window.

        A full re-login mints a new session for the account, so the Neakasa
        app's own session is pushed out repeatedly when it happens often.
        Raises :class:`UpdateFailed` when re-authentication itself fails.
        Returns whether a re-authentication was performed.
        """
        now = time.monotonic()
        if self._last_full_auth is not None:
            elapsed = now - self._last_full_auth
            if elapsed < FULL_REAUTH_COOLDOWN_SECONDS:
                _LOGGER.debug(
                    "Not signing in again (%s): last full re-auth was %.0fs ago",
                    reason,
                    elapsed,
                )
                return False
        self._last_full_auth = now
        try:
            await force_reconnect_api(self.hass, self.username, self.password, reason)
        except NeakasaApiClientError as reconnect_err:
            msg = "Reconnection failed"
            raise UpdateFailed(msg) from reconnect_err
        # A sign-in is us presenting the account, so the session is ours again
        # and the account sensor says we hold it.
        self._note_presented(f"sign-in for {reason}")
        return True

    def _needs_full_reauth(self, err: BaseException | None) -> bool:
        """
        Return whether *err* rejects the account token rather than the IoT one.

        ``/catbox/record`` signs with the token the login response returned, so
        a message matching `_TOKEN_INVALID_PHRASES` can only be repaired by
        signing in again: exchanging the IoT token would leave that one stale.
        """
        if err is None:
            return False
        message = str(err).lower()
        return any(phrase in message for phrase in _TOKEN_INVALID_PHRASES)

    async def _reconnect_and_retry(
        self, reason: str = "session expired", err: BaseException | None = None
    ) -> NeakasaPayload:
        """
        Recover from a session/auth failure, then retry the update.

        A rejected IoT token is renewed with one call; a rejected account
        token goes straight to a sign-in, which the cooldown bounds. Recovery
        inside one update is attempted at most `MAX_SESSION_RECOVERY_ATTEMPTS`
        times, and the scan raises :class:`UpdateFailed` when it cannot recover.
        """
        self.force_refresh_devices()
        self._recovery_attempts += 1
        if self._recovery_attempts > MAX_SESSION_RECOVERY_ATTEMPTS:
            msg = (
                f"Session recovery attempted {self._recovery_attempts} times"
                " in one update"
            )
            raise UpdateFailed(msg)
        renew_without_signing_in = err is None or not self._needs_full_reauth(err)
        if renew_without_signing_in and await self._renew_cloud_session():
            return await self.async_update_data()
        if not await self._force_full_reauth(reason):
            msg = f"Cloud session unusable and re-auth cooling down: {reason}"
            raise UpdateFailed(msg)
        return await self.async_update_data()

    async def _reconnect_clear_and_retry(
        self, err: BaseException | None = None
    ) -> NeakasaPayload:
        """
        Fully clear the shared API and retry from scratch.

        Used for identityId-blank errors where a partial reconnect is
        insufficient.
        """
        clear_shared_api(self.username, self.password)
        return await self._reconnect_and_retry("identityId is blank", err)

    async def _recover_session_expired(self, err: BaseException) -> NeakasaPayload:
        """
        Log the expiry, try one recovery and retry the update.

        Shared by a whole-update expiry and by devices that failed because the
        session behind their token was gone, so both read the same in logs.
        """
        _LOGGER.warning("Session expired, reconnecting silently: %s", err)
        try:
            payload = await self._reconnect_and_retry("session expired", err)
        except Exception as exc:
            _LOGGER.warning("Reconnect+retry FAILED after session expiry: %s", exc)
            raise
        _LOGGER.info(
            "Reconnect+retry SUCCEEDED after session expiry — %d devices",
            len(payload),
        )
        return payload

    # ------------------------------------------------------------------
    # Main update loop
    # ------------------------------------------------------------------

    async def async_update_data(self) -> NeakasaPayload:
        """Fetch fresh data from all CatLitter devices on the account."""
        try:
            client = await self._get_client()
            devices = await self._discover_devices(client)
            self._device_ids = [d["iotId"] for d in devices]

            snapshots = await asyncio.gather(
                *(
                    self._fetch_single_device(iot_id, client)
                    for iot_id in self._device_ids
                ),
                return_exceptions=True,
            )

            payload: NeakasaPayload = {}
            session_failures: list[BaseException] = []
            for iot_id, result in zip(self._device_ids, snapshots, strict=False):
                if isinstance(result, BaseException):
                    _LOGGER.error(
                        "Failed to fetch device %s: %s", device_label(iot_id), result
                    )
                    if isinstance(result, NeakasaApiClientSessionExpiredError):
                        session_failures.append(result)
                    continue
                payload[iot_id] = result

            if session_failures:
                # One device failing for its token says the session is gone for
                # all of them, so it goes to the recovery path rather than being
                # a per-device gap in this update.
                return await self._recover_session_expired(session_failures[0])

            _LOGGER.debug("Coordinator update complete: %d devices", len(payload))
            self._recovery_attempts = 0  # a finished update ends any recovery run
            await self._run_debug_probe(payload)
            return payload  # noqa: TRY300

        except NeakasaApiClientSessionExpiredError as err:
            return await self._recover_session_expired(err)

        except NeakasaApiClientAuthenticationError as err:
            _LOGGER.warning("Authentication error, attempting reconnect: %s", err)
            try:
                return await self._reconnect_and_retry("authentication error", err)
            except UpdateFailed:
                _LOGGER.info(
                    "Starting reauth flow for entry %s",
                    entry_label(self.config_entry.entry_id),
                )
                self.hass.async_create_task(
                    self.config_entry.async_start_reauth(self.hass)
                )
                raise

        except NeakasaApiClientCommunicationError as err:
            if "identityId is blank" in str(err):
                _LOGGER.debug("IdentityId error, attempting automatic reconnection")
                return await self._reconnect_clear_and_retry(err)

            _LOGGER.warning("API communication error (retrying): %s", err)
            for delay in (2, 4, 8, 16, 32):
                _LOGGER.debug("Retrying after %ds ...", delay)
                await asyncio.sleep(delay)
                try:
                    return await self.async_update_data()
                except (
                    NeakasaApiClientCommunicationError
                ):  # pragma: no cover - never propagates
                    # The nested update recurses into this same retry loop, so
                    # this branch is unreachable in practice.
                    continue  # pragma: no cover
            _LOGGER.error(  # pragma: no cover - retries recurse until recovery
                "API communication error after all retries: %s", err
            )
            msg = f"Communication error after 5 retries: {err}"  # pragma: no cover
            raise UpdateFailed(msg) from err  # pragma: no cover

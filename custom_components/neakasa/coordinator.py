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
    DESICCANT_DAYS_MAX,
    DOMAIN,
    FEED_FOOD_MAX_G,
    FEED_FOOD_MIN_G,
    FEED_SOUND_VOLUME_MAX,
    FEED_SOUND_VOLUME_MIN,
    FEED_WATER_RATIO_MAX,
    FEED_WATER_RATIO_MIN,
    MIX_MIN_MAX,
    MIX_MIN_MIN,
    SUPPORTED_CATEGORY_KEYS,
)
from .exceptions import (
    NeakasaApiClientAuthenticationError,
    NeakasaApiClientCommunicationError,
    NeakasaApiClientDeviceBusyError,
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


def _clean_stamp() -> str:
    """
    Return now as the shape the machine's own date records use.

    A sibling device writes its dated records as `2026-10-19 07:18:49`, so a
    cleaning mark is written in that shape rather than a guessed one.
    """
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


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
    battery_state: int | None = None
    battery_ts: str | None = None
    bowl_present: bool = False
    cover_absent: bool = False
    desiccant_days_left: int | None = None
    desiccant_days_effective: int | None = None
    desiccant_reset_ts: str | None = None
    fresh_mgr_on: bool = False
    fresh_mgr_cfg: dict[str, Any] | None = None
    fresh_mgr_leftover_g: int | None = None
    fresh_mgr_hours: int | None = None
    deep_clean_on: bool = False
    deep_clean_state: int | None = None
    deep_clean_ts: str | None = None
    default_food_g: int | None = None
    default_water_ratio: int | None = None
    feed_cfg: dict[str, Any] | None = None
    mix_min_minutes: int | None = None
    bowl_weight_g: int | None = None
    bowl_tare_g: int | None = None
    scale_state_ts: str | None = None
    scale_live_g: float | None = None
    scale_live_tare_g: int | None = None
    scale_live_ts: str | None = None
    device_state: int = 0
    device_state_param: int | None = None
    device_state_ts: str | None = None
    display_type: int | None = None
    display_param: str | None = None
    display_when_idle: bool | None = None
    display_cfg: dict[str, Any] | None = None
    sound_index: int | None = None
    sound_volume: int | None = None
    feed_aud_cfg: dict[str, Any] | None = None
    dnd_active: bool | None = None
    dnd_cfg: dict[str, Any] | None = None
    last_water_bin_clean: str | None = None
    last_food_bin_clean: str | None = None
    firmware_version: str | None = None
    hardware_version: str | None = None
    feed_today_g: int | None = None
    device_serial: str = ""


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


def _optional_int(value: Any) -> int | None:
    """Return an int only when the machine actually answered with one."""
    if value is None or isinstance(value, bool):
        return None if value is None else int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _state_age(ts: Any) -> tuple[str | None, int | None]:
    """Return the moment a wrapper stamp states, and how many minutes ago that was."""
    if ts is None:
        return None, None
    try:
        when = datetime.fromtimestamp(int(float(ts)) / 1000, tz=UTC)
    except (ValueError, OverflowError, OSError):
        return None, None
    return when.isoformat(), max(
        0, int((datetime.now(UTC) - when).total_seconds() // 60)
    )


def _state_evidence(values: dict[str, Any], prefix: str, ts: Any) -> dict[str, Any]:
    """Return *values* with the moment they were stated and how long ago beside them."""
    out = dict(values)
    as_of, age = _state_age(ts)
    if as_of is not None and age is not None:
        out[f"{prefix}_as_of"] = as_of
        out[f"{prefix}_age_minutes"] = age
    return out


def _service_answer(reply: Any) -> dict[str, Any]:
    """
    Return the parameters a sync service answered with, or {} when it gave none.

    The gateway wraps the reply as `{"data": {"ReturnCode": 0, "Params": {…}}}`,
    and inside `Params` the machine names which kind of answer it sent, so a
    caller has to ask rather than assume: nothing here treats any answer as the
    kind another caller wanted.
    """
    if not isinstance(reply, dict):
        return {}
    inner = reply.get("data", reply)
    if not isinstance(inner, dict):
        return {}
    if _to_int(inner.get("ReturnCode", 0)) != 0:
        return {}
    params = inner.get("Params")
    if not isinstance(params, dict):
        return {}
    return params


def _live_scale(answer: Any) -> tuple[float | None, int | None]:
    """
    Return the weighing and the bowl's tare a live-read answer stated together.

    This unit answered `{"type": "scale", "str": {"bowlGram": 68, "gram": 89.08}}`
    twice on 2026-10-27 fourteen seconds apart, the second time with the gram at
    89.1, so the reading moves with the ask while the cloud's stored copy stayed
    at 67 g through that day. An answer labelled as anything else - the power
    state, a hopper level - is not a weighing and gives nothing.
    """
    if not isinstance(answer, dict) or answer.get("type") != "scale":
        return None, None
    values = answer.get("str")
    if not isinstance(values, dict):
        return None, None
    gram = values.get("gram")
    if gram is None or isinstance(gram, bool):
        return None, None
    try:
        weight = float(gram)
    except (TypeError, ValueError):
        return None, None
    tare = values.get("bowlGram")
    return weight, None if tare is None else _to_int(tare)


def _feed_grams_today(records: Any) -> int | None:
    """
    Sum the grams the machine recorded as delivered meals for the current day.

    The meal records the account-side endpoint answers with name each delivery
    (`feed_weight` in grams at `feed_time`); nothing here has that shape yet -
    no delivery has been recorded on this account - so an unrecognisable list
    returns None rather than a guessed zero, and the sensor shows no value. The
    day is the machine's clock read as UTC, because the record itself carries no
    timezone.
    """
    if not isinstance(records, dict):
        return None
    entries = records.get("record_list")
    if not isinstance(entries, list) or not entries:
        return None
    today = datetime.now(UTC).date()
    total = 0
    recognised = False
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        grams = _optional_int(entry.get("feed_weight", entry.get("weight")))
        when_seconds = _optional_int(
            entry.get("feed_time", entry.get("time", entry.get("ts")))
        )
        if grams is None or when_seconds is None:
            continue
        if when_seconds > 10**12:
            when_seconds //= 1000
        try:
            when = datetime.fromtimestamp(when_seconds, tz=UTC).date()
        except (OverflowError, ValueError, OSError):
            continue
        recognised = True
        if when == today:
            total += grams
    return total if recognised else None


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
    live: Any = None,
    live_asked_at: str | None = None,
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
            iot_id,
            device_name,
            devicedata,
            product_key,
            label,
            records,
            live,
            live_asked_at,
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
    records: dict[str, Any] | None = None,
    live: Any = None,
    live_asked_at: str | None = None,
) -> NeakasaDeviceSnapshot:
    """
    Build a snapshot for a Riko wet-meal feeder (categoryKey ``petFeeder``).

    The scale keeps two answers: the copy the cloud holds for `bowlStatus`, which
    only says what the machine last reported, and the weighing this unit stated
    when the integration asked for one (`live`, from the definition's 称重 read).
    Both are kept apart, so an entity can say which of the two it is showing.
    """
    _log_missing_property_keys(iot_id, devicedata, PETFEEDER_EXPECTED_KEYS)
    network = _property_value(devicedata, "NetWorkStatus", {})
    if not isinstance(network, dict):
        network = {}
    pwr = _property_value(devicedata, "pwrStatus", {})
    if not isinstance(pwr, dict):
        pwr = {}
    pwr_entry = devicedata.get("pwrStatus") if isinstance(devicedata, dict) else None
    pwr_stamp = pwr_entry.get("time") if isinstance(pwr_entry, dict) else None
    bowl = _property_value(devicedata, "bowlStatus", {})
    if not isinstance(bowl, dict):
        bowl = {}
    # The wrapper's own stamp is the moment the machine last pushed this key to
    # the cloud, and asking the cloud never re-reads what that push carried: this
    # unit re-reported `bowlStatus` on 2026-10-27T00:56:40Z - inside a whole-set
    # report, the same stamp as `pwrStatus`, `foodLvl`, `waterLvl`, `NetWorkStatus`
    # and `deviceState` - still stating `{bowlGram: 68, curWeight: 67}` with about
    # 22 g of food in the bowl while the app showed 22-23 g. Nothing on this path
    # re-reads the scale, so the age of the reading, not a claim about the present,
    # is what can honestly be said.
    bowl_entry = devicedata.get("bowlStatus") if isinstance(devicedata, dict) else None
    scale_stamp = bowl_entry.get("time") if isinstance(bowl_entry, dict) else None
    fresh_mgr = _property_value(devicedata, "freshMgrCfg", {})
    if not isinstance(fresh_mgr, dict):
        fresh_mgr = {}
    deep_clean = _property_value(devicedata, "deepCleanCfg", {})
    if not isinstance(deep_clean, dict):
        deep_clean = {}
    deep_clean_entry = (
        devicedata.get("deepCleanCfg") if isinstance(devicedata, dict) else None
    )
    deep_clean_stamp = (
        deep_clean_entry.get("time") if isinstance(deep_clean_entry, dict) else None
    )
    def_fd = _property_value(devicedata, "defFdCfg", {})
    if not isinstance(def_fd, dict):
        def_fd = {}
    device_state = _property_value(devicedata, "deviceState", {})
    if not isinstance(device_state, dict):
        device_state = {}
    device_entry = (
        devicedata.get("deviceState") if isinstance(devicedata, dict) else None
    )
    device_stamp = device_entry.get("time") if isinstance(device_entry, dict) else None
    display = _property_value(devicedata, "displayCfg", {})
    if not isinstance(display, dict):
        display = {}
    audio = _property_value(devicedata, "feedAudCfg", {})
    if not isinstance(audio, dict):
        audio = {}
    versions = _property_value(devicedata, "DeviceVer", {})
    if not isinstance(versions, dict):
        versions = {}
    dnd = _property_value(devicedata, "DND_Mode", {})
    if not isinstance(dnd, dict):
        dnd = {}

    battery_percent_raw = pwr.get("batPercentage")
    live_gram, live_tare = _live_scale(live)
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
        bucket_status=0,
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
        battery_state=_optional_int(pwr.get("batStatus")),
        battery_ts=str(pwr_stamp) if pwr_stamp is not None else None,
        bowl_present=_to_int(bowl.get("bBowlIn", 0)) == 1,
        cover_absent=_property_value(devicedata, "bCoverAbsent", 1) == 0,
        desiccant_days_left=(None if desiccant_raw is None else _to_int(desiccant_raw)),
        desiccant_days_effective=_optional_int(
            _property_value(devicedata, "drierEffeDays")
        ),
        desiccant_reset_ts=_property_value(devicedata, "drierResetTs"),
        fresh_mgr_on=_to_int(fresh_mgr.get("bOnOff", 0)) == 1,
        fresh_mgr_cfg=dict(fresh_mgr) if fresh_mgr else None,
        fresh_mgr_leftover_g=_optional_int(fresh_mgr.get("leftOverTTH")),
        fresh_mgr_hours=_optional_int(fresh_mgr.get("monitorTime")),
        deep_clean_on=_to_int(deep_clean.get("bOnOff", 0)) == 1,
        deep_clean_state=_optional_int(deep_clean.get("cleanState")),
        deep_clean_ts=str(deep_clean_stamp) if deep_clean_stamp is not None else None,
        default_food_g=default_food_g,
        default_water_ratio=default_water_ratio,
        feed_cfg=dict(def_fd) if def_fd else None,
        mix_min_minutes=_optional_int(def_fd.get("mixMin")),
        bowl_weight_g=_optional_int(bowl.get("curWeight")),
        bowl_tare_g=_optional_int(bowl.get("bowlGram")),
        scale_state_ts=str(scale_stamp) if scale_stamp is not None else None,
        scale_live_g=live_gram,
        scale_live_tare_g=live_tare if live_gram is not None else None,
        scale_live_ts=live_asked_at if live_gram is not None else None,
        device_state=_to_int(device_state.get("state", 0)),
        device_state_param=_optional_int(device_state.get("param")),
        device_state_ts=str(device_stamp) if device_stamp is not None else None,
        display_type=_optional_int(display.get("displayType")),
        display_param=display.get("displayParam"),
        display_when_idle=(
            None
            if "bDisplayIfIdle" not in display
            else _to_int(display["bDisplayIfIdle"]) == 1
        ),
        display_cfg=dict(display) if display else None,
        sound_index=_optional_int(audio.get("audIdx")),
        sound_volume=_optional_int(audio.get("volume")),
        feed_aud_cfg=dict(audio) if audio else None,
        dnd_active=(None if "active" not in dnd else _to_int(dnd["active"]) == 1),
        dnd_cfg=dict(dnd) if dnd else None,
        last_water_bin_clean=_property_value(devicedata, "lastWaterBinCleanTime"),
        last_food_bin_clean=_property_value(devicedata, "lastFoodBinCleanTime"),
        firmware_version=versions.get("FW_Version"),
        hardware_version=versions.get("HW_Version"),
        feed_today_g=_feed_grams_today(records),
        device_serial=device_name,
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
        "feed_cfg": "defFdCfg",
        "fresh_mgr_cfg": "freshMgrCfg",
        "display_cfg": "displayCfg",
        "feed_aud_cfg": "feedAudCfg",
        "desiccant_days_effective": "drierEffeDays",
        "desiccant_days_left": "leftDrierDays",
        "last_water_bin_clean": "lastWaterBinCleanTime",
        "last_food_bin_clean": "lastFoodBinCleanTime",
        "dnd_cfg": "DND_Mode",
    }

    # A nested config object is replaced as a whole by the gateway, so a setting
    # that owns one of its fields has to carry the others. They come from a read
    # of the machine taken when the press runs, not from the model: the model is
    # only as fresh as the last scan, and a change made in the mobile app inside
    # that window would otherwise be written back as the older value we still
    # hold - the journal showed presses at 22:47 and 23:07 pushing
    # `displayType: 2, displayParam: N/A` onto a machine the app had set to time
    # at 23:39. The read costs one extra GET per press, which is what a real
    # client (the app) does before writing, and it is never done by polling.
    NESTED_WRITES: ClassVar[frozenset[str]] = frozenset(
        {
            "cleanCfg",
            "deepCleanCfg",
            "freshMgrCfg",
            "defFdCfg",
            "feedAudCfg",
            "displayCfg",
            "DND_Mode",
        }
    )

    # Where a field of a written object also appears on the model as its own
    # value, so the entities follow what was sent rather than what was assumed.
    _NESTED_MODEL_FIELDS: ClassVar[dict[str, dict[str, tuple[str, str]]]] = {
        "display_cfg": {
            "displayType": ("display_type", "int"),
            "displayParam": ("display_param", "text"),
            "bDisplayIfIdle": ("display_when_idle", "bool"),
        },
        "fresh_mgr_cfg": {
            "bOnOff": ("fresh_mgr_on", "bool"),
            "monitorTime": ("fresh_mgr_hours", "int"),
            "leftOverTTH": ("fresh_mgr_leftover_g", "int"),
        },
        "feed_aud_cfg": {
            "audIdx": ("sound_index", "int"),
            "volume": ("sound_volume", "int"),
        },
        "feed_cfg": {"mixMin": ("mix_min_minutes", "int")},
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
            "reset_desiccant": "resetDrierTime",
            "reset_bowl_scale": "resetScaleZero",
            "calibrate_food_scale": "fdCalbration",
            "wash_bowl": "deepWashing",
            "display_animation": "ledScreenDisplay",
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

    def scale_state_evidence(self, iot_id: str) -> dict[str, Any]:
        """
        Return the evidence behind a bowl reading, so its age can be checked.

        The cloud's copy of `bowlStatus` is only as fresh as the machine's last
        push of that key, and that push repeats what the machine had stored
        rather than re-reading the scale: this unit re-reported the key at
        2026-10-27T00:56:40Z - a whole-set report, the same stamp as
        `pwrStatus`, `foodLvl`, `waterLvl`, `NetWorkStatus` and `deviceState` -
        still stating 67 g on the scale against a 68 g tare with about 22 g of
        food in the bowl while the app showed 22-23 g. `get` is answered with
        "service not found", and asking for this key leaves it as it was: the
        machine's own read command states a fresh weighing, and that is a
        different claim, kept in its own helper. So the evidence names the
        moment that reading was stated and how long ago that was, instead of
        presenting the number as if it were the present.
        """
        snap = self.device_snapshot(iot_id)
        if snap is None:
            return {}
        evidence: dict[str, Any] = {
            "scale_reading_g": snap.bowl_weight_g,
            "bowl_tare_g": snap.bowl_tare_g,
            "bowl_in_place": snap.bowl_present,
        }
        as_of, age = _state_age(snap.scale_state_ts)
        if as_of is None or age is None:
            return evidence
        evidence["scale_state_as_of"] = as_of
        evidence["scale_state_age_minutes"] = age
        return evidence

    def live_scale_evidence(self, iot_id: str) -> dict[str, Any]:
        """
        Return the weighing the machine stated to a live read, and when we asked.

        This is the scale's other answer: the reply to the definition's 称重 read,
        which this unit gave twice on 2026-10-27 fourteen seconds apart as 89.08
        g and 89.1 g above the 68 g tare it states in the same answer - while the
        stored copy stayed at 67 g for that whole day. The reply carries no
        timestamp of its own, only a message identifier, so the date here is the
        moment the answer arrived: the machine's reading as of the ask, and the
        only claim that answer supports.
        """
        snap = self.device_snapshot(iot_id)
        if snap is None or snap.scale_live_g is None:
            return {}
        return {
            "scale_live_g": snap.scale_live_g,
            "scale_live_tare_g": snap.scale_live_tare_g,
            "scale_live_as_of": snap.scale_live_ts,
        }

    def device_state_evidence(self, iot_id: str) -> dict[str, Any]:
        """
        Return the machine's reported state beside the moment it stated it.

        Unlike `bowlStatus`, the state keys here are re-pushed as the machine
        works: this unit's `deviceState` stamp moved four times across
        2026-10-26T11:05:05Z, 2026-10-27T00:40:17Z, 2026-10-27T00:56:40Z and
        2026-10-27T09:44:57Z while the value stayed 0, so the value is as fresh
        as the machine's last report of that key and the evidence says which
        moment that was.
        """
        snap = self.device_snapshot(iot_id)
        if snap is None:
            return {}
        return _state_evidence(
            {
                "state_value": snap.device_state,
                "state_param": snap.device_state_param,
            },
            "state",
            snap.device_state_ts,
        )

    def deep_clean_evidence(self, iot_id: str) -> dict[str, Any]:
        """Return the wash state the machine states, and when it stated it."""
        snap = self.device_snapshot(iot_id)
        if snap is None:
            return {}
        return _state_evidence(
            {
                "deep_clean_state": snap.deep_clean_state,
                "deep_clean_switch": snap.deep_clean_on,
            },
            "deep_clean",
            snap.deep_clean_ts,
        )

    def battery_state_evidence(self, iot_id: str) -> dict[str, Any]:
        """Return the battery state the machine states, and when it stated it."""
        snap = self.device_snapshot(iot_id)
        if snap is None:
            return {}
        return _state_evidence(
            {
                "battery_state": snap.battery_state,
                "battery_percent": snap.battery_percent,
            },
            "battery",
            snap.battery_ts,
        )

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
        """
        Write one device property, taking a nested object's siblings from the machine.

        A nested config (`displayCfg`, `freshMgrCfg`, `defFdCfg`, `feedAudCfg`,
        `cleanCfg`, `deepCleanCfg`, `DND_Mode`) is replaced as a whole, so the
        fields this control does not own are read from the device at this moment
        and merged in - the model's copy is only as fresh as the last scan, and
        re-sending it would push a value the machine no longer has back onto it.
        A field the caller changed is kept as the caller set it; a field that is
        only being carried along takes the machine's value. When the read states
        nothing for the object, what was asked is written as it is and the log
        says which path ran.
        """
        client = await self._get_client()
        wire_key = self._SNAP_TO_WIRE.get(key, key)
        snap = self.data.get(iot_id) if self.data else None
        payload = value
        if isinstance(value, dict) and wire_key in self.NESTED_WRITES:
            fresh = await self._get_properties(iot_id, client)
            stated = _property_value(fresh, wire_key, {})
            if not isinstance(stated, dict):
                stated = {}
            if stated:
                stale = getattr(snap, key, None) if snap is not None else None
                payload = dict(stated)
                for field, field_value in value.items():
                    if not isinstance(stale, dict) or field_value != stale.get(field):
                        payload[field] = field_value
            else:
                _LOGGER.debug(
                    "The machine stated nothing for %s, so writing what was asked",
                    wire_key,
                )
        await client.set_device_properties(iot_id, {wire_key: payload})
        if snap is None:
            return
        setattr(snap, key, payload if isinstance(payload, dict) else value)
        if isinstance(payload, dict):
            self._note_written_config(snap, key, payload)
        self._mark_state_changed(iot_id)
        self.async_set_updated_data(self.data)

    def _note_written_config(
        self,
        snap: NeakasaDeviceSnapshot,
        key: str,
        written: dict[str, Any],
    ) -> None:
        """
        Mirror a nested object that was just written into the model's fields.

        The model holds both the raw object and the per-field values the entities
        read. Both are set from what was actually written - the machine's siblings
        merged with the field this control owns - so a press is followed by the
        values it asked for, and a sibling the machine corrected is followed by
        that correction instead of by our older guess.
        """
        for wire_field, (attr, kind) in self._NESTED_MODEL_FIELDS.get(key, {}).items():
            if wire_field not in written:
                continue
            raw = written[wire_field]
            match kind:
                case "int":
                    setattr(snap, attr, _optional_int(raw))
                case "bool":
                    setattr(snap, attr, _to_int(raw) == 1)
                case "text":
                    setattr(snap, attr, raw)
        if key == "feed_cfg":
            food_g, ratio = _configured_feed_defaults(written)
            snap.default_food_g = food_g
            snap.default_water_ratio = ratio

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

    async def invoke_device_service(
        self, iot_id: str, service: str, args: dict[str, Any]
    ) -> None:
        """
        Invoke one of the feeder's own commands with its arguments.

        The command names and argument keys come from the machine's definition
        for the product; only ``feedOnce`` has been seen working here, so the
        answer of the others is whatever this firmware says. A refusal is not
        turned into a silent success: it reaches the caller as an error.
        """
        snap = self.data.get(iot_id) if self.data else None
        category = snap.category_key if snap is not None else "petFeeder"
        identifier = self._SERVICE_DISPATCH.get(category, {}).get(service)
        if identifier is None:
            msg = f"Unknown service: {service}"
            raise ValueError(msg)
        client = await self._get_client()
        await client.invoke_service(iot_id, identifier, args)
        if self.data and iot_id in self.data:
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

    async def set_rehydration_minutes(self, iot_id: str, minutes: int) -> None:
        """
        Write only the rehydration minutes of the machine's default meal.

        ``defFdCfg`` is replaced as a whole by the gateway, so the portion and
        water amount the machine currently stores are carried into the write
        unchanged. A machine that has never been configured keeps its
        ``{food:0,water:0}`` state rather than being given invented amounts.
        """
        if not MIX_MIN_MIN <= minutes <= MIX_MIN_MAX:
            msg = (
                f"Rehydration time out of range: {minutes} "
                f"(expected {MIX_MIN_MIN}-{MIX_MIN_MAX})"
            )
            raise ValueError(msg)
        snap = self.data.get(iot_id) if self.data else None
        current = dict(snap.feed_cfg) if snap is not None and snap.feed_cfg else {}
        payload = dict(current)
        payload["mixMin"] = minutes
        await self.set_property(iot_id, "feed_cfg", payload)

    async def set_feed_sound_volume(self, iot_id: str, volume: int) -> None:
        """
        Set the volume of the meal sound, keeping the clip the machine uses.

        The definition allows a volume up to 200, and this unit states 100; the
        integration offers 0-100 only, where 0 is silence, so a value here stays
        inside what the machine has been seen to use. The clip and any other key
        of `feedAudCfg` are carried by the shared write path, which takes them from
        a read of the machine at press time.
        """
        if not FEED_SOUND_VOLUME_MIN <= volume <= FEED_SOUND_VOLUME_MAX:
            msg = f"Sound volume out of range: {volume}"
            raise ValueError(msg)
        snap = self.data.get(iot_id) if self.data else None
        current = (
            dict(snap.feed_aud_cfg) if snap is not None and snap.feed_aud_cfg else {}
        )
        current["volume"] = volume
        await self.set_property(iot_id, "feed_aud_cfg", current)

    async def request_desiccant_reset(self, iot_id: str) -> None:
        """
        Tell the machine a fresh desiccant pack is in place.

        The command re-counts from the day budget given to it, so the budget is
        the one the machine states now when it states one, and otherwise the
        longest the definition allows rather than an invented number.
        """
        snap = self.data.get(iot_id) if self.data else None
        days = (
            (snap.desiccant_days_effective or DESICCANT_DAYS_MAX)
            if snap
            else DESICCANT_DAYS_MAX
        )
        await self.invoke_device_service(
            iot_id, "reset_desiccant", {"drierEffeDays": days}
        )

    async def request_bowl_scale_reset(
        self, iot_id: str, bowl_gram: int | None = None
    ) -> None:
        """Re-zero the scale against the bowl weight, keeping the machine's own."""
        snap = self.data.get(iot_id) if self.data else None
        grams = (
            bowl_gram if bowl_gram is not None else (snap.bowl_tare_g if snap else None)
        )
        if grams is None:
            msg = "No bowl weight to re-zero against"
            raise ValueError(msg)
        await self.invoke_device_service(
            iot_id, "reset_bowl_scale", {"bowlGram": grams}
        )

    async def request_food_scale_calibration(self, iot_id: str) -> None:
        """Ask the machine to recalibrate how it reads food weight."""
        await self.invoke_device_service(iot_id, "calibrate_food_scale", {})

    async def mark_bin_clean(self, iot_id: str, which: str) -> None:
        """Record that the water tank or the food bin was cleaned now."""
        wire_key = {
            "water": "lastWaterBinCleanTime",
            "food": "lastFoodBinCleanTime",
        }.get(which)
        if wire_key is None:
            msg = f"Unknown bin: {which}"
            raise ValueError(msg)
        client = await self._get_client()
        await client.set_device_properties(iot_id, {wire_key: _clean_stamp()})
        snap = self.data.get(iot_id) if self.data else None
        if snap is not None:
            stamp = _clean_stamp()
            if which == "water":
                snap.last_water_bin_clean = stamp
            else:
                snap.last_food_bin_clean = stamp
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
        await self.set_property(iot_id, "feed_cfg", payload)

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
        selected probe rather than on every update. What the run writes to the
        journal, and what was seen on the unit, is in docs/app-session-experiments.md.
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

    async def _read_live_scale(
        self, iot_id: str, client: NeakasaApiClient | None = None
    ) -> tuple[dict[str, Any], str | None]:
        """
        Ask the machine for its current weighing and return what it answered.

        The definition names a sync service `iotRead` (远程读取) whose readType 2 is
        称重 (the weighing), and this unit answers it: twice on 2026-10-27, fourteen
        seconds apart, the reply was `{"type": "scale", "str": {"bowlGram": 68,
        "gram": 89.08}}` then `89.1` - a reading that moves, while the cloud's copy
        of `bowlStatus` stayed at 67 g for the whole day. The moment the answer
        arrived is the only date the reply can be given, since it carries no stamp
        of its own, so it is taken here rather than claimed by the machine.
        A refused call is a gap, not an invention: the answer is empty and the
        stored copy keeps its place.
        """
        api_client = client if client is not None else await self._get_client()
        try:
            reply = await api_client.invoke_service(iot_id, "iotRead", {"readType": 2})
        except (
            NeakasaApiClientCommunicationError,
            NeakasaApiClientDeviceBusyError,
        ) as err:
            _LOGGER.debug(
                "The live scale read was refused (%s), so the stored copy stands",
                type(err).__name__,
            )
            return {}, None
        answer = _service_answer(reply)
        if not answer:
            return {}, None
        return answer, datetime.now(UTC).isoformat()

    async def _fetch_single_device(
        self, iot_id: str, client: NeakasaApiClient | None = None
    ) -> NeakasaDeviceSnapshot:
        """Fetch the reads one device answers for and build its snapshot."""
        devicedata = await self._get_properties(iot_id, client)
        meta = self._device_meta.get(iot_id, {})
        category_key = meta.get("category_key", "CatLitter")

        if category_key not in ("CatLitter", "petFeeder"):
            # An unknown product is read for its properties only: asking its
            # records would be a call whose answer nobody can interpret.
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

        live: dict[str, Any] = {}
        live_asked_at: str | None = None
        if category_key == "petFeeder":
            live, live_asked_at = await self._read_live_scale(iot_id, client)

        new_last_use = _get_last_use_date(devicedata)
        records_cache, _ = self._cache_for(iot_id)
        if self._last_use_dates.get(iot_id) != new_last_use:
            # A new last-use is the only thing that can mean a new record, so
            # the records are re-read on it and not otherwise.
            records_cache.mark_as_stale()
        self._last_use_dates[iot_id] = new_last_use

        records = await self._get_records(iot_id, client)
        device_name = await self._get_device_name(iot_id)
        stamp_props = devicedata if isinstance(devicedata, dict) else {}
        if live:
            # The live weighing changes what the bowl says without changing the
            # property set, so it belongs in the stamp: an unchanged answer
            # stays an unchanged state and is not re-pushed to Home Assistant.
            stamp_props = {**stamp_props, "liveScale": live}
        self._mark_state_changed(iot_id, stamp_props, records)
        return _build_device_snapshot(
            iot_id,
            device_name,
            devicedata,
            records,
            new_last_use,
            category_key=category_key,
            product_key=meta.get("product_key", ""),
            label=meta.get("label", ""),
            live=live,
            live_asked_at=live_asked_at,
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

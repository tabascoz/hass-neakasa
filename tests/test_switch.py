"""Tests for switch entities."""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.neakasa.coordinator import NeakasaDeviceSnapshot
from custom_components.neakasa.switch.auto_bury import NeakasaAutoBurySwitch
from custom_components.neakasa.switch.auto_clean import NeakasaAutoCleanSwitch
from custom_components.neakasa.switch.auto_level import NeakasaAutoLevelSwitch
from custom_components.neakasa.switch.child_lock import NeakasaChildLockSwitch
from custom_components.neakasa.switch.silent_mode import NeakasaSilentModeSwitch
from custom_components.neakasa.switch.young_cat_mode import NeakasaYoungCatModeSwitch

FAKE_SNAPSHOT = NeakasaDeviceSnapshot(
    iot_id="iot-001",
    category_key="CatLitter",
    product_key="a1nNMMJkLqG",
    device_name="T1 Plus",
    bin_full=False,
    clean_cfg={"active": True, "cleanInterval": 23, "workTime": 10, "delayTime": 5},
    sand_level_state=2,
    sand_level_percent=65,
    bucket_status=0,
    room_of_bin=0,
    young_cat_mode=False,
    child_lock=False,
    auto_bury=True,
    auto_level=True,
    silent_mode=False,
    wifi_rssi=-55,
    auto_force_init=False,
    b_intrpt_range_det=True,
    stay_time=120,
    last_use=1730000000,
    cat_list=[],
    record_list=[],
)

FAKE_DEVICE_INFO = {"identifiers": {("neakasa", "iot-001")}}


_SENTINEL = object()


def _mock_coord(snap: NeakasaDeviceSnapshot | None = _SENTINEL) -> MagicMock:
    c = MagicMock()
    if snap is _SENTINEL:
        c.device_snapshot.return_value = FAKE_SNAPSHOT
    else:
        c.device_snapshot.return_value = snap
    return c


# ---------------------------------------------------------------------------
# AutoCleanSwitch
# ---------------------------------------------------------------------------


async def test_auto_clean_is_on() -> None:
    sensor = NeakasaAutoCleanSwitch(_mock_coord(), FAKE_DEVICE_INFO, "iot-001")
    sensor.hass = MagicMock()
    assert sensor.is_on is True
    assert sensor.state == "on"
    assert sensor.translation_key == "auto_clean"


async def test_auto_clean_is_off() -> None:
    snap = NeakasaDeviceSnapshot(
        iot_id="iot-001",
        category_key="CatLitter",
        product_key="a1nNMMJkLqG",
        device_name="T1",
        bin_full=False,
        clean_cfg={"active": False},
        sand_level_state=0,
        sand_level_percent=0,
        bucket_status=0,
        room_of_bin=0,
        young_cat_mode=False,
        child_lock=False,
        auto_bury=False,
        auto_level=False,
        silent_mode=False,
        wifi_rssi=0,
        auto_force_init=False,
        b_intrpt_range_det=False,
        stay_time=0,
        last_use=0,
        cat_list=[],
        record_list=[],
    )
    sensor = NeakasaAutoCleanSwitch(_mock_coord(snap), FAKE_DEVICE_INFO, "iot-001")
    sensor.hass = MagicMock()
    assert sensor.is_on is False


async def test_auto_clean_missing_cfg() -> None:
    snap = NeakasaDeviceSnapshot(
        iot_id="iot-001",
        category_key="CatLitter",
        product_key="a1nNMMJkLqG",
        device_name="T1",
        bin_full=False,
        clean_cfg={},
        sand_level_state=0,
        sand_level_percent=0,
        bucket_status=0,
        room_of_bin=0,
        young_cat_mode=False,
        child_lock=False,
        auto_bury=False,
        auto_level=False,
        silent_mode=False,
        wifi_rssi=0,
        auto_force_init=False,
        b_intrpt_range_det=False,
        stay_time=0,
        last_use=0,
        cat_list=[],
        record_list=[],
    )
    sensor = NeakasaAutoCleanSwitch(_mock_coord(snap), FAKE_DEVICE_INFO, "iot-001")
    sensor.hass = MagicMock()
    assert sensor.is_on is False


# ---------------------------------------------------------------------------
# ChildLockSwitch
# ---------------------------------------------------------------------------


async def test_child_lock_is_on() -> None:
    snap = NeakasaDeviceSnapshot(
        iot_id="iot-001",
        category_key="CatLitter",
        product_key="a1nNMMJkLqG",
        device_name="T1",
        bin_full=False,
        clean_cfg={},
        sand_level_state=0,
        sand_level_percent=0,
        bucket_status=0,
        room_of_bin=0,
        young_cat_mode=False,
        child_lock=True,
        auto_bury=False,
        auto_level=False,
        silent_mode=False,
        wifi_rssi=0,
        auto_force_init=False,
        b_intrpt_range_det=False,
        stay_time=0,
        last_use=0,
        cat_list=[],
        record_list=[],
    )
    sensor = NeakasaChildLockSwitch(_mock_coord(snap), FAKE_DEVICE_INFO, "iot-001")
    sensor.hass = MagicMock()
    assert sensor.is_on is True
    assert sensor.translation_key == "child_lock"


# ---------------------------------------------------------------------------
# AutoBurySwitch
# ---------------------------------------------------------------------------


async def test_auto_bury_is_on() -> None:
    sensor = NeakasaAutoBurySwitch(_mock_coord(), FAKE_DEVICE_INFO, "iot-001")
    sensor.hass = MagicMock()
    assert sensor.is_on is True
    assert sensor.translation_key == "auto_bury"


# ---------------------------------------------------------------------------
# AutoLevelSwitch
# ---------------------------------------------------------------------------


async def test_auto_level_is_on() -> None:
    sensor = NeakasaAutoLevelSwitch(_mock_coord(), FAKE_DEVICE_INFO, "iot-001")
    sensor.hass = MagicMock()
    assert sensor.is_on is True
    assert sensor.translation_key == "auto_level"


# ---------------------------------------------------------------------------
# SilentModeSwitch
# ---------------------------------------------------------------------------


async def test_silent_mode_is_off() -> None:
    sensor = NeakasaSilentModeSwitch(_mock_coord(), FAKE_DEVICE_INFO, "iot-001")
    sensor.hass = MagicMock()
    assert sensor.is_on is False
    assert sensor.translation_key == "silent_mode"


# ---------------------------------------------------------------------------
# YoungCatModeSwitch
# ---------------------------------------------------------------------------


async def test_young_cat_mode_is_off() -> None:
    sensor = NeakasaYoungCatModeSwitch(_mock_coord(), FAKE_DEVICE_INFO, "iot-001")
    sensor.hass = MagicMock()
    assert sensor.is_on is False
    assert sensor.translation_key == "young_cat_mode"

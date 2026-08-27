"""Tests for sensor entities."""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.neakasa.coordinator import NeakasaDeviceSnapshot
from custom_components.neakasa.sensor.bin_state import NeakasaBinStateSensor
from custom_components.neakasa.sensor.bucket_status import NeakasaBucketStatusSensor
from custom_components.neakasa.sensor.last_usage import NeakasaLastUsageSensor
from custom_components.neakasa.sensor.sand_level_state import (
    NeakasaSandLevelStateSensor,
)
from custom_components.neakasa.sensor.sand_percent import NeakasaSandPercentSensor
from custom_components.neakasa.sensor.stay_time import NeakasaStayTimeSensor
from custom_components.neakasa.sensor.wifi_rssi import NeakasaWifiRssiSensor

FAKE_SNAPSHOT = NeakasaDeviceSnapshot(
    iot_id="iot-001",
    device_name="T1 Plus",
    category_key="CatLitter",
    product_key="a1nNMMJkLqG",
    bin_full=False,
    clean_cfg={},
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
# SandPercentSensor
# ---------------------------------------------------------------------------


def test_sand_percent_native_value() -> None:
    sensor = NeakasaSandPercentSensor(_mock_coord(), FAKE_DEVICE_INFO, "iot-001")
    sensor.hass = MagicMock()
    assert sensor.native_value == 65
    assert sensor.native_unit_of_measurement == "%"
    assert sensor.translation_key == "sand_percent"


def test_sand_percent_no_data() -> None:
    coord = _mock_coord(None)
    sensor = NeakasaSandPercentSensor(coord, FAKE_DEVICE_INFO, "iot-001")
    sensor.hass = MagicMock()
    assert sensor.native_value is None


# ---------------------------------------------------------------------------
# SandLevelStateSensor
# ---------------------------------------------------------------------------


def test_sand_level_state() -> None:
    sensor = NeakasaSandLevelStateSensor(_mock_coord(), FAKE_DEVICE_INFO, "iot-001")
    sensor.hass = MagicMock()
    assert sensor.native_value == "sufficient"
    assert sensor.translation_key == "sand_state"


# ---------------------------------------------------------------------------
# BucketStatusSensor
# ---------------------------------------------------------------------------


def test_bucket_status() -> None:
    sensor = NeakasaBucketStatusSensor(_mock_coord(), FAKE_DEVICE_INFO, "iot-001")
    sensor.hass = MagicMock()
    assert sensor.native_value == "idle"
    assert sensor.translation_key == "current_status"


# ---------------------------------------------------------------------------
# BinStateSensor
# ---------------------------------------------------------------------------


def test_bin_state() -> None:
    sensor = NeakasaBinStateSensor(_mock_coord(), FAKE_DEVICE_INFO, "iot-001")
    sensor.hass = MagicMock()
    assert sensor.native_value == "normal"
    assert sensor.translation_key == "bin_state"


def test_bin_state_full() -> None:
    snap = NeakasaDeviceSnapshot(
        iot_id="iot-001",
        category_key="CatLitter",
        product_key="a1nNMMJkLqG",
        device_name="T1",
        bin_full=True,
        clean_cfg={},
        sand_level_state=0,
        sand_level_percent=0,
        bucket_status=1,
        room_of_bin=1,
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
    sensor = NeakasaBinStateSensor(_mock_coord(snap), FAKE_DEVICE_INFO, "iot-001")
    sensor.hass = MagicMock()
    assert sensor.native_value == "full"


def test_bin_state_missing() -> None:
    snap = NeakasaDeviceSnapshot(
        iot_id="iot-001",
        category_key="CatLitter",
        product_key="a1nNMMJkLqG",
        device_name="T1",
        bin_full=False,
        clean_cfg={},
        sand_level_state=0,
        sand_level_percent=0,
        bucket_status=5,
        room_of_bin=2,
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
    sensor = NeakasaBinStateSensor(_mock_coord(snap), FAKE_DEVICE_INFO, "iot-001")
    sensor.hass = MagicMock()
    assert sensor.native_value == "missing"


# ---------------------------------------------------------------------------
# WifiRssiSensor
# ---------------------------------------------------------------------------


def test_wifi_rssi() -> None:
    sensor = NeakasaWifiRssiSensor(_mock_coord(), FAKE_DEVICE_INFO, "iot-001")
    sensor.hass = MagicMock()
    assert sensor.native_value == -55


# ---------------------------------------------------------------------------
# StayTimeSensor
# ---------------------------------------------------------------------------


def test_stay_time() -> None:
    sensor = NeakasaStayTimeSensor(_mock_coord(), FAKE_DEVICE_INFO, "iot-001")
    sensor.hass = MagicMock()
    assert sensor.native_value == 120


# ---------------------------------------------------------------------------
# LastUsageSensor
# ---------------------------------------------------------------------------


def test_last_usage() -> None:
    sensor = NeakasaLastUsageSensor(_mock_coord(), FAKE_DEVICE_INFO, "iot-001")
    sensor.hass = MagicMock()
    assert sensor.native_value is not None  # timestamp

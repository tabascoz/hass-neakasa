"""Tests for sensor entities."""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.neakasa.coordinator import NeakasaDeviceSnapshot
from custom_components.neakasa.sensor import async_setup_entry
from custom_components.neakasa.sensor.bin_state import NeakasaBinStateSensor
from custom_components.neakasa.sensor.bucket_status import NeakasaBucketStatusSensor
from custom_components.neakasa.sensor.cat_weight import NeakasaCatWeightSensor
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


# ---------------------------------------------------------------------------
# Cat weight sensor
# ---------------------------------------------------------------------------


def _cat_weight_snap(record_list: list) -> NeakasaDeviceSnapshot:
    return NeakasaDeviceSnapshot(
        iot_id="iot-001",
        device_name="T1 Plus",
        category_key="CatLitter",
        product_key="pk",
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
        record_list=record_list,
    )


FAKE_RECORDS_LIST = [
    {
        "cat_id": "cat-1",
        "weight": 4500,
        "start_time": 1730000000,
        "end_time": 1730000100,
    },
    {
        "cat_id": "cat-2",
        "weight": 3900,
        "start_time": 1730000100,
        "end_time": 1730000200,
    },
]


def test_cat_weight_no_records() -> None:
    sensor = NeakasaCatWeightSensor(
        _mock_coord(_cat_weight_snap([])),
        FAKE_DEVICE_INFO,
        "iot-001",
        cat_name="Whiskers",
        cat_id="cat-1",
    )
    sensor.hass = MagicMock()
    assert sensor.native_value is None
    assert sensor.extra_state_attributes == {}
    assert sensor.translation_key == "cat_sensor"
    assert sensor.translation_placeholders == {"name": "Whiskers"}
    assert sensor.unique_id == "iot-001-cat-cat-1"


def test_cat_weight_matching_record() -> None:
    sensor = NeakasaCatWeightSensor(
        _mock_coord(_cat_weight_snap(FAKE_RECORDS_LIST)),
        FAKE_DEVICE_INFO,
        "iot-001",
        cat_name="Whiskers",
        cat_id="cat-1",
    )
    sensor.hass = MagicMock()
    assert sensor.native_value == 4500
    attrs = sensor.extra_state_attributes
    assert attrs["start_time"].year == 2024
    assert attrs["end_time"] is not None


def test_cat_weight_no_matching_cat() -> None:
    sensor = NeakasaCatWeightSensor(
        _mock_coord(_cat_weight_snap(FAKE_RECORDS_LIST)),
        FAKE_DEVICE_INFO,
        "iot-001",
        cat_name="Ghost",
        cat_id="cat-99",
    )
    sensor.hass = MagicMock()
    assert sensor.native_value is None
    assert sensor.extra_state_attributes == {}


def test_cat_weight_missing_snapshot() -> None:
    sensor = NeakasaCatWeightSensor(
        _mock_coord(None),
        FAKE_DEVICE_INFO,
        "iot-001",
        cat_name="Whiskers",
        cat_id="cat-1",
    )
    sensor.hass = MagicMock()
    assert sensor.native_value is None
    assert sensor._records == []


# ---------------------------------------------------------------------------
# Edge cases: missing snapshot / out-of-range raw values
# ---------------------------------------------------------------------------


def test_sensors_without_snapshot() -> None:
    sensors = [
        NeakasaSandPercentSensor(_mock_coord(None), FAKE_DEVICE_INFO, "iot-001"),
        NeakasaWifiRssiSensor(_mock_coord(None), FAKE_DEVICE_INFO, "iot-001"),
        NeakasaStayTimeSensor(_mock_coord(None), FAKE_DEVICE_INFO, "iot-001"),
        NeakasaLastUsageSensor(_mock_coord(None), FAKE_DEVICE_INFO, "iot-001"),
        NeakasaBucketStatusSensor(_mock_coord(None), FAKE_DEVICE_INFO, "iot-001"),
        NeakasaSandLevelStateSensor(_mock_coord(None), FAKE_DEVICE_INFO, "iot-001"),
        NeakasaBinStateSensor(_mock_coord(None), FAKE_DEVICE_INFO, "iot-001"),
    ]
    for sensor in sensors:
        sensor.hass = MagicMock()
        assert sensor.native_value is None


def test_bin_state_out_of_range() -> None:
    snap = _cat_weight_snap([])
    snap.room_of_bin = 5
    sensor = NeakasaBinStateSensor(_mock_coord(snap), FAKE_DEVICE_INFO, "iot-001")
    sensor.hass = MagicMock()
    assert sensor.native_value == 5


def test_bucket_status_out_of_range() -> None:
    snap = _cat_weight_snap([])
    snap.bucket_status = 10
    sensor = NeakasaBucketStatusSensor(_mock_coord(snap), FAKE_DEVICE_INFO, "iot-001")
    sensor.hass = MagicMock()
    assert sensor.native_value == 10


def test_sand_level_state_out_of_range() -> None:
    snap = _cat_weight_snap([])
    snap.sand_level_state = 9
    sensor = NeakasaSandLevelStateSensor(_mock_coord(snap), FAKE_DEVICE_INFO, "iot-001")
    sensor.hass = MagicMock()
    assert sensor.native_value == 9


def test_last_usage_zero_and_invalid() -> None:
    zero = _cat_weight_snap([])
    zero.last_use = 0
    sensor = NeakasaLastUsageSensor(_mock_coord(zero), FAKE_DEVICE_INFO, "iot-001")
    sensor.hass = MagicMock()
    assert sensor.native_value is None

    invalid = _cat_weight_snap([])
    invalid.last_use = "not-a-number"
    sensor = NeakasaLastUsageSensor(_mock_coord(invalid), FAKE_DEVICE_INFO, "iot-001")
    sensor.hass = MagicMock()
    assert sensor.native_value is None


# ---------------------------------------------------------------------------
# Lifecycle methods (handle update / async_update / async_added_to_hass)
# ---------------------------------------------------------------------------


def _fake_platform_data() -> MagicMock:
    """Fake EntityPlatform.platform_data so async_write_ha_state can run."""
    platform_data = MagicMock()
    platform_data.platform_name = "sensor"
    platform_data.domain = "sensor"
    platform_data.platform_translations = {}
    platform_data.component_translations = {}
    platform_data.object_id_platform_translations = {}
    platform_data.object_id_component_translations = {}
    return platform_data


async def test_sensor_lifecycle_methods(hass) -> None:
    """Exercise the shared lifecycle methods on every sensor class."""
    sensor_classes = [
        NeakasaSandPercentSensor,
        NeakasaWifiRssiSensor,
        NeakasaStayTimeSensor,
        NeakasaLastUsageSensor,
        NeakasaBucketStatusSensor,
        NeakasaSandLevelStateSensor,
        NeakasaBinStateSensor,
        NeakasaCatWeightSensor,
    ]
    for index, sensor_cls in enumerate(sensor_classes):
        snapshot = _cat_weight_snap(FAKE_RECORDS_LIST)
        if sensor_cls is NeakasaCatWeightSensor:
            sensor = sensor_cls(
                _mock_coord(snapshot),
                FAKE_DEVICE_INFO,
                "iot-001",
                cat_name="Whiskers",
                cat_id="cat-1",
            )
        else:
            sensor = sensor_cls(_mock_coord(snapshot), FAKE_DEVICE_INFO, "iot-001")
        sensor.hass = hass
        sensor.platform_data = _fake_platform_data()
        fake_platform = MagicMock()
        fake_platform.platform_name = "sensor"
        fake_platform.entity_platform = MagicMock()
        sensor.platform = fake_platform
        sensor.entity_id = f"sensor.neakasa_{index}"
        await sensor.async_added_to_hass()
        sensor._handle_coordinator_update()
        await sensor.async_update()

        sensor.entity_id = None
        await sensor.async_update()


# ---------------------------------------------------------------------------
# Sensor platform setup
# ---------------------------------------------------------------------------


async def test_sensor_async_setup_entry(hass) -> None:
    """Test that setup registers base + per-cat sensors per device."""
    from custom_components.neakasa.const import DOMAIN

    snap = _cat_weight_snap([])
    snap.cat_list = [{"name": "Whiskers", "id": "cat-1", "weight": 4500}]

    coordinator = MagicMock()
    coordinator.data = {"iot-001": snap}
    coordinator.async_add_listener = MagicMock()

    config_entry = MagicMock()
    config_entry.runtime_data.coordinator = coordinator
    config_entry.async_on_unload = MagicMock()
    config_entry.domain = DOMAIN

    collected: list = []

    await async_setup_entry(hass, config_entry, collected.extend)

    assert len(collected) == 8  # 7 base sensors + 1 cat sensor
    assert any(isinstance(e, NeakasaCatWeightSensor) for e in collected)

    # Second discovery pass with a new device adds its entities only
    second_snap = _cat_weight_snap([])
    coordinator.data = {"iot-001": snap, "iot-002": second_snap}
    rediscover = coordinator.async_add_listener.call_args.args[0]
    before = len(collected)
    rediscover()
    assert len(collected) == before + 7

    # Third pass with unchanged data adds nothing
    rediscover()
    assert len(collected) == before + 7

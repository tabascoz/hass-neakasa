"""Tests for the Neakasa Riko (petFeeder) integration path."""

from __future__ import annotations

import copy
from unittest.mock import AsyncMock, MagicMock

from homeassistant.core import HomeAssistant

from custom_components.neakasa.binary_sensor.cover_absent import (
    NeakasaCoverAbsentBinarySensor,
)
from custom_components.neakasa.coordinator import (
    NeakasaCoordinator,
    _build_pet_feeder_snapshot,
)
from custom_components.neakasa.exceptions import (
    NeakasaApiClientCommunicationError,
)
from custom_components.neakasa.sensor.battery import NeakasaBatterySensor
from custom_components.neakasa.sensor.food_level import NeakasaFoodLevelSensor
from custom_components.neakasa.sensor.label import NeakasaLabelSensor
from custom_components.neakasa.sensor.water_level import NeakasaWaterLevelSensor

# Live wire shape captured from a real Riko (see docs/riko-protocol.md).
FAKE_RIKO_PROPERTIES: dict = {
    "foodLvl": {"value": 2},
    "waterLvl": {"value": 3},
    "pwrStatus": {
        "value": {
            "batPercentage": 90,
            "batLevel": 4,
            "batVoltage": 12209,
            "batTemp": 25.0,
            "pwrType": 0,
            "batStatus": 2,
        }
    },
    "bowlStatus": {"value": {"bowlGram": 68, "curWeight": 67, "bBowlIn": 1}},
    "bCoverAbsent": {"value": 1},
    "leftDrierDays": {"value": 40},
    "deviceState": {"value": {"param": 0, "state": 0}},
    "freshMgrCfg": {"value": {"monitorTime": 4, "leftOverTTH": 20, "bOnOff": 1}},
    "deepCleanCfg": {"value": {"bOnOff": 0, "cleanState": 0}},
    "childLockOnOff": {"value": 0},
    "NetWorkStatus": {"value": {"WiFi_RSSI": -43, "WiFi_Name": "MIAU"}},
}


def _riko_snapshot() -> object:
    return _build_pet_feeder_snapshot(
        "riko-001",
        "WL03002G26270011577",
        FAKE_RIKO_PROPERTIES,
        "a1ccEqBcaUD",
        "Catchief",
    )


def test_build_pet_feeder_reads_levels() -> None:
    snap = _riko_snapshot()
    assert snap.category_key == "petFeeder"
    assert snap.food_level_state == 2
    assert snap.water_level_state == 3
    assert snap.battery_percent == 90
    assert snap.battery_level == 4
    assert snap.bowl_present is True
    assert snap.cover_absent is False
    assert snap.desiccant_days_left == 40
    assert snap.fresh_mgr_on is True
    assert snap.deep_clean_on is False
    assert snap.wifi_rssi == -43
    assert snap.label == "Catchief"


def test_build_pet_feeder_missing_optional_keys() -> None:
    props = copy.deepcopy(FAKE_RIKO_PROPERTIES)
    for key in ("pwrStatus", "bowlStatus", "leftDrierDays", "deviceState"):
        props.pop(key)
    snap = _build_pet_feeder_snapshot("riko-001", "serial", props, "pk", "")
    assert snap.battery_percent is None
    assert snap.battery_level is None
    assert snap.bowl_present is False
    assert snap.desiccant_days_left is None
    assert snap.bucket_status == 0


def test_build_pet_feeder_empty_properties() -> None:
    snap = _build_pet_feeder_snapshot("riko-001", "serial", {}, "", "")
    assert snap.category_key == "petFeeder"
    assert snap.food_level_state == 0
    assert snap.cover_absent is False


# ---------------------------------------------------------------------------
# Entities
# ---------------------------------------------------------------------------

FAKE_DEVICE_INFO = {"identifiers": {("neakasa", "riko-001")}}


def _mock_coord(snap: object) -> MagicMock:
    c = MagicMock()
    c.device_snapshot.return_value = snap
    return c


def test_food_level_native_value() -> None:
    sensor = NeakasaFoodLevelSensor(
        _mock_coord(_riko_snapshot()), FAKE_DEVICE_INFO, "riko-001"
    )
    assert sensor.native_value == 2
    assert sensor.translation_key == "food_level"
    assert sensor.unique_id == "riko-001-food_level"


def test_water_level_native_value() -> None:
    sensor = NeakasaWaterLevelSensor(
        _mock_coord(_riko_snapshot()), FAKE_DEVICE_INFO, "riko-001"
    )
    assert sensor.native_value == 3
    assert sensor.translation_key == "water_level"


def test_battery_native_value() -> None:
    sensor = NeakasaBatterySensor(
        _mock_coord(_riko_snapshot()), FAKE_DEVICE_INFO, "riko-001"
    )
    assert sensor.native_value == 90
    assert sensor.translation_key == "battery"


def test_battery_none_when_missing() -> None:
    snap = _build_pet_feeder_snapshot("riko-001", "s", {}, "", "")
    sensor = NeakasaBatterySensor(_mock_coord(snap), FAKE_DEVICE_INFO, "riko-001")
    assert sensor.native_value is None


def test_label_native_value() -> None:
    sensor = NeakasaLabelSensor(
        _mock_coord(_riko_snapshot()), FAKE_DEVICE_INFO, "riko-001"
    )
    assert sensor.native_value == "Catchief"
    assert sensor.translation_key == "device_label"


def test_label_none_when_unset() -> None:
    snap = _build_pet_feeder_snapshot("riko-001", "s", {}, "", "")
    sensor = NeakasaLabelSensor(_mock_coord(snap), FAKE_DEVICE_INFO, "riko-001")
    assert sensor.native_value is None


def test_cover_absent_when_missing() -> None:
    props = dict(FAKE_RIKO_PROPERTIES)
    props["bCoverAbsent"] = {"value": 0}
    snap = _build_pet_feeder_snapshot("riko-001", "s", props, "pk", "")
    entity = NeakasaCoverAbsentBinarySensor(
        _mock_coord(snap), FAKE_DEVICE_INFO, "riko-001"
    )
    entity.hass = MagicMock()
    assert entity.is_on is True
    assert entity.state == "on"
    assert entity.translation_key == "cover_absent"


def test_cover_absent_off_when_present() -> None:
    entity = NeakasaCoverAbsentBinarySensor(
        _mock_coord(_riko_snapshot()), FAKE_DEVICE_INFO, "riko-001"
    )
    entity.hass = MagicMock()
    assert entity.is_on is False


def test_cover_absent_off_without_snapshot() -> None:
    coord = MagicMock()
    coord.device_snapshot.return_value = None
    entity = NeakasaCoverAbsentBinarySensor(coord, FAKE_DEVICE_INFO, "riko-001")
    entity.hass = MagicMock()
    assert entity.is_on is False


# ---------------------------------------------------------------------------
# Debug probe + diagnostics schema helpers
# ---------------------------------------------------------------------------


def _make_coordinator(hass: HomeAssistant, entry: MagicMock) -> NeakasaCoordinator:
    c = NeakasaCoordinator(hass, entry)
    c._get_client = AsyncMock()
    return c


async def test_debug_probe_none_is_noop(
    hass: HomeAssistant, mock_config_entry: MagicMock
) -> None:
    coordinator = _make_coordinator(hass, mock_config_entry)
    coordinator.config_entry.options = {"debug_probe": "none"}
    await coordinator._run_debug_probe({"iot-1": object()})
    coordinator._get_client.assert_not_called()


async def test_debug_probe_set_fresh_mgr_on(
    hass: HomeAssistant, mock_config_entry: MagicMock
) -> None:
    coordinator = _make_coordinator(hass, mock_config_entry)
    coordinator.config_entry.options = {"debug_probe": "set_fresh_mgr_on"}
    client = AsyncMock()
    client.get_device_properties = AsyncMock(
        return_value={"freshMgrCfg": {"value": {"monitorTime": 4, "bOnOff": 0}}}
    )
    client.set_device_properties = AsyncMock()
    coordinator._get_client = AsyncMock(return_value=client)

    await coordinator._run_debug_probe({"riko-1": object()})

    client.set_device_properties.assert_awaited_once_with(
        "riko-1", {"freshMgrCfg": {"monitorTime": 4, "bOnOff": 1}}
    )


async def test_debug_probe_invoke_custom_errors_swallowed(
    hass: HomeAssistant, mock_config_entry: MagicMock
) -> None:
    coordinator = _make_coordinator(hass, mock_config_entry)
    coordinator.config_entry.options = {
        "debug_probe": "invoke_custom",
        "debug_invoke_identifier": "feedNow",
        "debug_invoke_args_json": '{"bStartFeed":1}',
    }
    client = AsyncMock()
    client.invoke_service = AsyncMock(
        side_effect=NeakasaApiClientCommunicationError("no such service")
    )
    coordinator._get_client = AsyncMock(return_value=client)

    await coordinator._run_debug_probe({"riko-1": object()})

    client.invoke_service.assert_awaited_once_with(
        "riko-1", "feedNow", {"bStartFeed": 1}
    )


async def test_async_get_device_schema_reports_missing_keys(
    hass: HomeAssistant, mock_config_entry: MagicMock
) -> None:
    coordinator = _make_coordinator(hass, mock_config_entry)
    snap = _build_pet_feeder_snapshot(
        "riko-1", "serial", FAKE_RIKO_PROPERTIES, "a1ccEqBcaUD", "Catchief"
    )
    coordinator.data = {"riko-1": snap}
    client = AsyncMock()
    client.get_product_list = AsyncMock(return_value=[])
    client.get_device_properties = AsyncMock(
        return_value={k: v for k, v in FAKE_RIKO_PROPERTIES.items() if k != "waterLvl"}
    )
    coordinator._get_client = AsyncMock(return_value=client)

    schema = await coordinator.async_get_device_schema()

    assert schema["products"] == {}
    entry = schema["devices"]["riko-1"]
    assert entry["category_key"] == "petFeeder"
    assert entry["missing_expected_keys"] == ["waterLvl"]

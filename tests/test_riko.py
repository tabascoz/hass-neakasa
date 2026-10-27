"""Tests for the Neakasa Riko (petFeeder) integration path."""

from __future__ import annotations

import copy
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.neakasa.binary_sensor.cover_absent import (
    NeakasaCoverAbsentBinarySensor,
)
from custom_components.neakasa.button.feed_now import NeakasaFeedNowButton
from custom_components.neakasa.coordinator import (
    NeakasaCoordinator,
    _build_pet_feeder_snapshot,
)
from custom_components.neakasa.exceptions import (
    NeakasaApiClientCommunicationError,
)
from custom_components.neakasa.log_redact import device_label
from custom_components.neakasa.number.food_grams import NeakasaFoodGramsNumber
from custom_components.neakasa.number.water_ratio import NeakasaWaterRatioNumber
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
    "defFdCfg": {"value": {"mixMin": 1, "water": 15, "food": 5}},
    "NetWorkStatus": {"value": {"WiFi_RSSI": -43, "WiFi_Name": "MIAU"}},
}


def _riko_snapshot() -> object:
    return _build_pet_feeder_snapshot(
        "riko-001",
        "SERIALFAKE0000000000000",
        FAKE_RIKO_PROPERTIES,
        "a1ccEqBcaUD",
        "TestLabel",
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
    assert snap.deep_clean_state == 0
    assert snap.battery_state == 2
    assert snap.device_state == 0
    assert snap.bucket_status == 0, "a feeder keeps its own state, not the litter box's"
    assert snap.wifi_rssi == -43
    assert snap.label == "TestLabel"
    assert snap.default_food_g == 5
    assert snap.default_water_ratio == 3
    assert snap.feed_cfg == {"mixMin": 1, "water": 15, "food": 5}


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
    assert snap.battery_state is None
    assert snap.device_state_ts is None
    assert snap.device_state_param is None


def test_build_pet_feeder_empty_properties() -> None:
    snap = _build_pet_feeder_snapshot("riko-001", "serial", {}, "", "")
    assert snap.category_key == "petFeeder"
    assert snap.food_level_state == 0
    assert snap.cover_absent is False
    assert snap.default_food_g is None
    assert snap.default_water_ratio is None


def test_build_pet_feeder_unconfigured_defaults() -> None:
    """A machine that never stored a default meal reports neither amount."""
    props = copy.deepcopy(FAKE_RIKO_PROPERTIES)
    props["defFdCfg"] = {"value": {"mixMin": 1, "water": 0, "food": 0}}
    snap = _build_pet_feeder_snapshot("riko-001", "s", props, "pk", "")
    assert snap.feed_cfg == {"mixMin": 1, "water": 0, "food": 0}
    assert snap.default_food_g is None
    assert snap.default_water_ratio is None


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
    assert sensor.native_value == "TestLabel"
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
        "riko-1", "serial", FAKE_RIKO_PROPERTIES, "a1ccEqBcaUD", "TestLabel"
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


async def test_feed_once_sends_water_grams(
    hass: HomeAssistant, mock_config_entry: MagicMock
) -> None:
    """A feed sends the water amount in grams and keeps the machine's defaults."""
    coordinator = _make_coordinator(hass, mock_config_entry)
    client = AsyncMock()
    coordinator._get_client = AsyncMock(return_value=client)

    await coordinator.feed_once("riko-1", food_g=5, water_ratio=2)
    client.invoke_service.assert_awaited_once_with(
        "riko-1",
        "feedOnce",
        {"food": 5, "water": 10, "bSaveAsDef": 0},
    )
    client.set_device_properties.assert_not_called()

    with pytest.raises(ValueError, match="Food portion out of range"):
        await coordinator.feed_once("riko-1", food_g=20, water_ratio=2)
    with pytest.raises(ValueError, match="Water ratio out of range"):
        await coordinator.feed_once("riko-1", food_g=5, water_ratio=9)
    client.invoke_service.assert_awaited_once_with(
        "riko-1",
        "feedOnce",
        {"food": 5, "water": 10, "bSaveAsDef": 0},
    )


async def test_feed_once_logs_and_records_the_last_feed(
    hass: HomeAssistant, mock_config_entry: MagicMock
) -> None:
    """The exact payload is logged and remembered for diagnostics."""
    coordinator = _make_coordinator(hass, mock_config_entry)
    client = AsyncMock()
    coordinator._get_client = AsyncMock(return_value=client)

    with patch("custom_components.neakasa.coordinator._LOGGER") as logger:
        await coordinator.feed_once("riko-1", food_g=6, water_ratio=2)

    logger.debug.assert_any_call(
        "Riko feedOnce %s: %s",
        device_label("riko-1"),
        {"food": 6, "water": 12, "bSaveAsDef": 0},
    )
    assert coordinator.last_feed("riko-1") == {
        "args": {"food": 6, "water": 12, "bSaveAsDef": 0},
        "stored_defaults": False,
    }


async def test_feed_once_falls_back_to_device_defaults(
    hass: HomeAssistant, mock_config_entry: MagicMock
) -> None:
    """No amounts given: the machine's stored defaults are fed."""
    coordinator = _make_coordinator(hass, mock_config_entry)
    coordinator.data = {"riko-1": _riko_snapshot()}
    client = AsyncMock()
    coordinator._get_client = AsyncMock(return_value=client)

    await coordinator.feed_once("riko-1")
    client.invoke_service.assert_awaited_once_with(
        "riko-1",
        "feedOnce",
        {"food": 5, "water": 15, "bSaveAsDef": 0},
    )


async def test_feed_once_uses_pending_amounts(
    hass: HomeAssistant, mock_config_entry: MagicMock
) -> None:
    """Staged amounts win, then they are cleared so the defaults show again."""
    coordinator = _make_coordinator(hass, mock_config_entry)
    coordinator.data = {"riko-1": _riko_snapshot()}
    coordinator.set_pending_feed("riko-1", food_g=9, water_ratio=2)
    client = AsyncMock()
    coordinator._get_client = AsyncMock(return_value=client)

    await coordinator.feed_once("riko-1")
    client.invoke_service.assert_awaited_once_with(
        "riko-1",
        "feedOnce",
        {"food": 9, "water": 18, "bSaveAsDef": 0},
    )
    assert coordinator.feed_values("riko-1") == (5, 3)


async def test_feed_once_keeps_new_defaults(
    hass: HomeAssistant, mock_config_entry: MagicMock
) -> None:
    """With the option on the fed amounts become the machine's defaults."""
    coordinator = _make_coordinator(hass, mock_config_entry)
    coordinator.config_entry.options = {
        "scan_interval": 60,
        "feed_keep_as_new_defaults": True,
    }
    client = AsyncMock()
    coordinator._get_client = AsyncMock(return_value=client)

    await coordinator.feed_once("riko-1", food_g=5, water_ratio=3)
    client.invoke_service.assert_awaited_once_with(
        "riko-1",
        "feedOnce",
        {"food": 5, "water": 15, "bSaveAsDef": 1},
    )
    client.set_device_properties.assert_awaited_once_with(
        "riko-1", {"defFdCfg": {"food": 5, "water": 15, "mixMin": 1}}
    )


async def test_feed_once_toggled_per_device(
    hass: HomeAssistant, mock_config_entry: MagicMock
) -> None:
    """The per-device setting wins over the account option."""
    coordinator = _make_coordinator(hass, mock_config_entry)
    coordinator.config_entry.options = {
        "scan_interval": 60,
        "feed_keep_as_new_defaults": False,
    }
    coordinator.set_feed_keep_as_new_defaults("riko-1", value=True)
    client = AsyncMock()
    coordinator._get_client = AsyncMock(return_value=client)

    await coordinator.feed_once("riko-1", food_g=5, water_ratio=3)
    client.invoke_service.assert_awaited_once_with(
        "riko-1",
        "feedOnce",
        {"food": 5, "water": 15, "bSaveAsDef": 1},
    )
    client.set_device_properties.assert_awaited_once_with(
        "riko-1", {"defFdCfg": {"food": 5, "water": 15, "mixMin": 1}}
    )
    assert coordinator.feed_keep_as_new_defaults("riko-1") is True
    assert coordinator.last_feed("riko-1") == {
        "args": {"food": 5, "water": 15, "bSaveAsDef": 1},
        "stored_defaults": True,
    }


async def test_feed_once_toggled_per_device_off(
    hass: HomeAssistant, mock_config_entry: MagicMock
) -> None:
    """A device toggled off stays off even when the option is on."""
    coordinator = _make_coordinator(hass, mock_config_entry)
    coordinator.config_entry.options = {
        "scan_interval": 60,
        "feed_keep_as_new_defaults": True,
    }
    coordinator.set_feed_keep_as_new_defaults("riko-1", value=False)
    client = AsyncMock()
    coordinator._get_client = AsyncMock(return_value=client)

    await coordinator.feed_once("riko-1", food_g=5, water_ratio=3)
    client.invoke_service.assert_awaited_once_with(
        "riko-1",
        "feedOnce",
        {"food": 5, "water": 15, "bSaveAsDef": 0},
    )
    client.set_device_properties.assert_not_called()
    assert coordinator.feed_keep_as_new_defaults("riko-1") is False


async def test_feed_once_override_per_call(
    hass: HomeAssistant, mock_config_entry: MagicMock
) -> None:
    """An explicit flag wins over the account-wide option."""
    coordinator = _make_coordinator(hass, mock_config_entry)
    coordinator.config_entry.options = {
        "scan_interval": 60,
        "feed_keep_as_new_defaults": True,
    }
    client = AsyncMock()
    coordinator._get_client = AsyncMock(return_value=client)

    await coordinator.feed_once("riko-1", save_as_default=False)
    client.invoke_service.assert_awaited_once_with(
        "riko-1",
        "feedOnce",
        {"food": 5, "water": 5, "bSaveAsDef": 0},
    )
    client.set_device_properties.assert_not_called()


async def test_set_feed_config_preserves_mixmin(
    hass: HomeAssistant, mock_config_entry: MagicMock
) -> None:
    """Writing new defaults stores water grams and preserves the existing mixMin."""
    coordinator = _make_coordinator(hass, mock_config_entry)
    snap = _riko_snapshot()
    coordinator.data = {"riko-1": snap}
    client = AsyncMock()
    coordinator._get_client = AsyncMock(return_value=client)

    await coordinator.set_feed_config("riko-1", food_g=8, water_ratio=3)
    client.set_device_properties.assert_awaited_once_with(
        "riko-1", {"defFdCfg": {"food": 8, "water": 24, "mixMin": 1}}
    )
    assert snap.default_food_g == 8
    assert snap.default_water_ratio == 3

    with pytest.raises(ValueError, match="Food portion out of range"):
        await coordinator.set_feed_config("riko-1", food_g=0, water_ratio=3)


async def test_feed_now_button_presses_without_own_amounts() -> None:
    """Feed now asks the coordinator to feed; it never picks amounts itself."""
    coord = MagicMock()
    coord.feed_once = AsyncMock()
    button = NeakasaFeedNowButton(coord, FAKE_DEVICE_INFO, "riko-001")
    button.hass = MagicMock()
    assert button.translation_key == "feed_now"
    assert button.unique_id == "riko-001-feed_now"

    await button.async_press()
    coord.feed_once.assert_awaited_once_with("riko-001")


async def test_editing_the_numbers_stages_without_writing_the_machine() -> None:
    """Each number stages the next feed; neither writes defFdCfg by itself."""
    food_coord = MagicMock()
    food_coord.feed_values.return_value = (5, 3)
    food = NeakasaFoodGramsNumber(food_coord, FAKE_DEVICE_INFO, "riko-001")
    food.hass = MagicMock()
    food.async_write_ha_state = MagicMock()
    await food.async_set_native_value(9.0)
    food_coord.set_pending_feed.assert_called_once_with("riko-001", food_g=9)
    food_coord.async_update_setup_entry_data.assert_not_called()
    food_coord.async_update_setup_completion_data.assert_not_called()

    ratio_coord = MagicMock()
    ratio_coord.feed_values.return_value = (10, 3)
    ratio = NeakasaWaterRatioNumber(ratio_coord, FAKE_DEVICE_INFO, "riko-001")
    ratio.hass = MagicMock()
    ratio.async_write_ha_state = MagicMock()
    await ratio.async_set_native_value(4.0)
    ratio_coord.set_pending_feed.assert_called_once_with("riko-001", water_ratio=4)
    ratio_coord.async_update_setup_entry_data.assert_not_called()
    ratio_coord.async_update_setup_completion_data.assert_not_called()


async def test_numbers_show_the_amounts_a_feed_would_use() -> None:
    """Both numbers display the effective amounts, not what is staged or stored."""
    coord = MagicMock()
    coord.feed_values.return_value = (9, 2)
    food = NeakasaFoodGramsNumber(coord, FAKE_DEVICE_INFO, "riko-001")
    food.hass = MagicMock()
    food.async_write_ha_state = MagicMock()
    food._handle_coordinator_update()
    assert food._attr_native_value == 9.0

    ratio = NeakasaWaterRatioNumber(coord, FAKE_DEVICE_INFO, "riko-001")
    ratio.hass = MagicMock()
    ratio.async_write_ha_state = MagicMock()
    ratio._handle_coordinator_update()
    assert ratio._attr_native_value == 2.0

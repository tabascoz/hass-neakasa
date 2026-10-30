"""Tests for the Riko controls beyond feeding: what the machine holds.

Several of these wire shapes exist in the product's definition and have never
been answered by the unit, so the tests that keep a value unknown matter as much
as the tests that read one.
"""

from __future__ import annotations

import copy
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest
from homeassistant.core import HomeAssistant

from custom_components.neakasa.binary_sensor.bowl_in_place import (
    NeakasaBowlInPlaceBinarySensor,
)
from custom_components.neakasa.binary_sensor.serving_food import (
    NeakasaServingFoodBinarySensor,
)
from custom_components.neakasa.button.calibrate_food_scale import (
    NeakasaCalibrateFoodScaleButton,
)
from custom_components.neakasa.button.mark_food_bin_clean import (
    NeakasaMarkFoodBinCleanButton,
)
from custom_components.neakasa.button.mark_water_bin_clean import (
    NeakasaMarkWaterBinCleanButton,
)
from custom_components.neakasa.button.reset_bowl_scale import (
    NeakasaResetBowlScaleButton,
)
from custom_components.neakasa.button.reset_desiccant import (
    NeakasaResetDesiccantButton,
)
from custom_components.neakasa.const import (
    DESICCANT_DAYS_MAX,
    FEED_SOUND_VOLUME_MAX,
    MIX_MIN_MAX,
)
from custom_components.neakasa.coordinator import (
    NeakasaCoordinator,
    _build_pet_feeder_snapshot,
    _live_scale,
    _served_rows,
    _served_today,
    _service_answer,
)
from custom_components.neakasa.exceptions import (
    NeakasaApiClientCommunicationError,
)
from custom_components.neakasa.number.desiccant_days import NeakasaDesiccantDaysNumber
from custom_components.neakasa.number.feed_sound_volume import (
    NeakasaFeedSoundVolumeNumber,
)
from custom_components.neakasa.number.rehydration_minutes import (
    NeakasaRehydrationMinutesNumber,
)
from custom_components.neakasa.select.display_standby_kind import (
    NeakasaDisplayStandbyKindSelect,
)
from custom_components.neakasa.sensor.battery import NeakasaBatterySensor
from custom_components.neakasa.sensor.battery_state import (
    NeakasaBatteryStateSensor,
)
from custom_components.neakasa.sensor.bowl_weight import NeakasaBowlWeightSensor
from custom_components.neakasa.sensor.deep_clean_state import (
    NeakasaDeepCleanStateSensor,
)
from custom_components.neakasa.sensor.desiccant_days_left import (
    NeakasaDesiccantDaysLeftSensor,
)
from custom_components.neakasa.sensor.device_serial import NeakasaDeviceSerialSensor
from custom_components.neakasa.sensor.device_status import (
    NeakasaDeviceStatusSensor,
)
from custom_components.neakasa.sensor.firmware_version import (
    NeakasaFirmwareVersionSensor,
)
from custom_components.neakasa.sensor.food_intake_today import (
    NeakasaFoodIntakeTodaySensor,
)
from custom_components.neakasa.sensor.food_intake_today_liquid import (
    NeakasaFoodIntakeTodayLiquidSensor,
)
from custom_components.neakasa.sensor.food_intake_today_solids import (
    NeakasaFoodIntakeTodaySolidsSensor,
)
from custom_components.neakasa.sensor.food_level import NeakasaFoodLevelSensor
from custom_components.neakasa.sensor.label import NeakasaLabelSensor
from custom_components.neakasa.sensor.last_bin_clean_food import (
    NeakasaFoodBinCleanSensor,
)
from custom_components.neakasa.sensor.last_bin_clean_water import (
    NeakasaWaterBinCleanSensor,
)
from custom_components.neakasa.sensor.water_level import NeakasaWaterLevelSensor
from custom_components.neakasa.switch.display_standby import NeakasaDisplayStandbySwitch
from custom_components.neakasa.switch.do_not_disturb import NeakasaDoNotDisturbSwitch
from custom_components.neakasa.switch.fresh_meal_manager import (
    NeakasaFreshMealManagerSwitch,
)
from custom_components.neakasa.text.display_custom_message import (
    NeakasaDisplayCustomMessageText,
)

ANSWERED: dict = {
    "displayCfg": {
        "value": {"displayType": 1, "displayParam": "N/A", "bDisplayIfIdle": 1}
    },
    "feedAudCfg": {"value": {"audIdx": 0, "volume": 100}},
    "drierEffeDays": {"value": 40},
    "drierResetTs": {"value": "1792757949"},
    "DND_Mode": {
        "value": {
            "active": 1,
            "startTime": 3600,
            "endTime": 7200,
            "weekRept": 127,
        }
    },
    "lastWaterBinCleanTime": {"value": "2026-10-19 07:18:49"},
    "DeviceVer": {
        "value": {"FW_Version": "1.0.0-0033", "HW_Version": "1.00.01", "type": 0}
    },
    "pwrStatus": {
        "time": 1793062600623,
        "value": {"batPercentage": 90, "batLevel": 4, "batStatus": 2},
    },
    "deepCleanCfg": {
        "time": 1793062600808,
        "value": {"bOnOff": 0, "cleanState": 0},
    },
    "deviceState": {
        "time": 1793094297980,
        "value": {"param": 0, "state": 0},
    },
}

BASE: dict = {
    "foodLvl": {"value": 2},
    "waterLvl": {"value": 3},
    "bowlStatus": {
        "time": 1792872600147,
        "value": {"bowlGram": 68, "curWeight": 67, "bBowlIn": 1},
    },
    "leftDrierDays": {"value": 38},
    "defFdCfg": {"value": {"mixMin": 3, "water": 4, "food": 4}},
    "freshMgrCfg": {"value": {"monitorTime": 4, "leftOverTTH": 20, "bOnOff": 0}},
}


def _answered() -> dict:
    """Return a wire shape that answers every control."""
    props = copy.deepcopy(BASE)
    props.update(copy.deepcopy(ANSWERED))
    return props


def _snapshot(props: dict, records: dict | None = None) -> object:
    return _build_pet_feeder_snapshot(
        "riko-001",
        "SERIALFAKE0000000000000",
        props,
        "a1ccEqBcaUD",
        "TestLabel",
        records,
    )


def test_definition_named_controls_are_read_when_answered() -> None:
    snap = _snapshot(_answered())
    assert snap.bowl_weight_g == 67
    assert snap.bowl_tare_g == 68
    assert snap.scale_state_ts == "1792872600147"
    assert snap.desiccant_days_effective == 40
    assert snap.display_type == 1
    assert snap.display_when_idle is True
    assert snap.sound_volume == 100
    assert snap.dnd_active is True
    assert snap.firmware_version == "1.0.0-0033"
    assert snap.device_serial == "SERIALFAKE0000000000000"
    assert snap.device_state == 0
    assert snap.device_state_param == 0
    assert snap.device_state_ts == "1793094297980"
    assert snap.deep_clean_state == 0
    assert snap.deep_clean_ts == "1793062600808"
    assert snap.battery_state == 2
    assert snap.battery_ts == "1793062600623"
    assert snap.bucket_status == 0, "a feeder keeps its own state, not the litter box's"


def test_unanswered_controls_stay_unknown() -> None:
    """Nothing is invented for a key the machine has never answered."""
    snap = _snapshot(BASE)
    assert snap.display_type is None
    assert snap.display_when_idle is None
    assert snap.sound_volume is None
    assert snap.desiccant_days_effective is None
    assert snap.firmware_version is None
    assert snap.feed_today_solids_g is None
    assert snap.feed_today_liquid_g is None
    assert snap.device_state_ts is None
    assert snap.device_state_param is None
    assert snap.deep_clean_state is None
    assert snap.battery_state is None


def _fixed_local_day() -> tuple[int, datetime]:
    """Return a half-hour-offset day's start and the midnight that states it."""
    midnight = datetime(2026, 10, 29, tzinfo=ZoneInfo("Asia/Kolkata"))
    return int(midnight.timestamp()), midnight


def test_the_day_being_run_groups_the_rows_and_another_zones_day_does_not() -> None:
    """Rows either side of a half-hour midnight are told apart."""
    day_start, midnight = _fixed_local_day()
    rows = [
        {"feed_time": day_start - 60, "feed_weight": 99, "water_weight": 99},
        {"feed_time": day_start + 60, "feed_weight": 10, "water_weight": 9},
        {
            "feed_time": day_start + 3600,
            "feed_weight": 0,
            "water_weight": 0,
            "way": "reflesh",
        },
    ]
    with patch(
        "custom_components.neakasa.coordinator.start_of_local_day",
        return_value=midnight,
    ):
        assert _served_today({"feed_list": rows}) == (
            10,
            9,
            (day_start + 60, day_start + 3600),
        )


def test_millisecond_rows_are_the_same_meals() -> None:
    """A row stamped in milliseconds is the row stamped in seconds."""
    day_start, midnight = _fixed_local_day()
    rows = [{"feed_time": (day_start + 60) * 1000 + 250, "feed_weight": 10}]
    with patch(
        "custom_components.neakasa.coordinator.start_of_local_day",
        return_value=midnight,
    ):
        assert _served_today({"feed_list": rows}) == (10, 0, (day_start + 60,))


def test_a_meal_that_ran_without_grams_states_a_known_zero() -> None:
    """The machine's own refresh grounded nothing; that is a zero, not a gap."""
    day_start, midnight = _fixed_local_day()
    rows = [
        {
            "feed_time": day_start + 60,
            "feed_weight": 0,
            "water_weight": 0,
            "way": "reflesh",
        }
    ]
    with patch(
        "custom_components.neakasa.coordinator.start_of_local_day",
        return_value=midnight,
    ):
        assert _served_today({"feed_list": rows}) == (0, 0, (day_start + 60,))


def test_a_planned_meal_is_never_counted_as_served() -> None:
    """What the machine only planned is not what ran."""
    day_start, midnight = _fixed_local_day()
    rows = [
        {
            "feed_time": day_start + 60,
            "plan_feed_weight": 10,
            "plan_water_weight": 10,
        }
    ]
    with patch(
        "custom_components.neakasa.coordinator.start_of_local_day",
        return_value=midnight,
    ):
        assert _served_today({"feed_list": rows}) == (0, 0, (day_start + 60,))


def test_unrecognisable_records_produce_no_number() -> None:
    """An answer with no rows is not reported as zero grams."""
    assert _served_today({"feed_list": []}) == (None, None, ())
    assert _served_today({"record_list": [{"feed_weight": 12}]}) == (None, None, ())
    assert _served_today(None) == (None, None, ())


def test_only_the_running_day_is_grouped_and_a_row_without_a_moment_is_left_out() -> (
    None
):
    """The walk the figure and its provenance share keeps one day and nothing else."""
    day_start, midnight = _fixed_local_day()
    rows = [
        {"feed_time": day_start - 1, "feed_weight": 99, "water_weight": 99},
        {
            "feed_time": (day_start + 60) * 1000 + 500,
            "feed_weight": 10,
            "water_weight": 9,
        },
        {"feed_weight": 7},
        "not-a-row",
    ]
    with patch(
        "custom_components.neakasa.coordinator.start_of_local_day",
        return_value=midnight,
    ):
        grouped = _served_rows({"feed_list": rows})
        assert [when for when, _ in grouped] == [day_start + 60]
        assert _served_today({"feed_list": rows}) == (10, 9, (day_start + 60,))
    assert _served_rows({"record_list": rows}) == []
    assert _served_rows(None) == []


def test_the_grouped_meals_reach_the_model_apart_from_the_grams() -> None:
    """The meals a day figure groups are kept beside it, not only their sum."""
    day_start, midnight = _fixed_local_day()
    rows = [
        {"feed_time": day_start - 1, "feed_weight": 99, "water_weight": 99},
        {"feed_time": day_start + 60, "feed_weight": 10, "water_weight": 9},
    ]
    with patch(
        "custom_components.neakasa.coordinator.start_of_local_day",
        return_value=midnight,
    ):
        snap = _snapshot(_answered(), {"feed_list": rows})
    assert snap.feed_today_solids_g == 10
    assert snap.feed_today_liquid_g == 9
    assert snap.meals_today == 1
    assert snap.meal_times == (day_start + 60,)
    assert _snapshot(_answered()).meals_today is None
    assert _snapshot(_answered()).meal_times == ()


def _mock_coord(snapshot: object) -> MagicMock:
    """A coordinator stand-in that only answers a read."""
    coordinator = MagicMock()
    coordinator.device_snapshot.return_value = snapshot
    coordinator.set_property = AsyncMock()
    return coordinator


def _make_coordinator(
    hass: HomeAssistant, entry: MagicMock, snapshot: object
) -> NeakasaCoordinator:
    """A real coordinator whose data is one feeder snapshot."""
    coordinator = NeakasaCoordinator(hass, entry)
    coordinator.data = {"riko-001": snapshot}
    coordinator._get_client = AsyncMock()
    return coordinator


DEVICE_INFO = {"identifiers": {("neakasa", "riko-001")}}


async def test_the_bowl_reading_carries_its_own_age(
    hass: HomeAssistant, mock_config_entry: MagicMock
) -> None:
    """A cloud reading that is old says how old it is, instead of posing as now."""
    coordinator = _make_coordinator(hass, mock_config_entry, _snapshot(_answered()))
    evidence = coordinator.scale_state_evidence("riko-001")
    assert evidence["scale_state_as_of"].startswith("2026-10-24T20:10")
    assert evidence["scale_state_age_minutes"] > 60 * 24
    assert evidence["scale_reading_g"] == 67
    assert evidence["bowl_tare_g"] == 68

    weight = NeakasaBowlWeightSensor(coordinator, DEVICE_INFO, "riko-001")
    assert weight.extra_state_attributes == evidence


async def test_the_weighing_the_machine_answers_is_the_fresher_claim(
    hass: HomeAssistant, mock_config_entry: MagicMock
) -> None:
    """The 称重 read moves and the stored copy does not; both stay labelled apart."""
    answer = {"type": "scale", "str": {"bowlGram": 68, "gram": 89.08}}
    asked_at = "2026-10-27T14:44:07+00:00"
    snap = _build_pet_feeder_snapshot(
        "riko-001",
        "SERIALFAKE0000000000000",
        _answered(),
        "a1ccEqBcaUD",
        "TestLabel",
        None,
        answer,
        asked_at,
    )
    assert snap.scale_live_g == 89.08
    assert snap.scale_live_tare_g == 68
    assert snap.scale_live_ts == asked_at

    coordinator = _make_coordinator(hass, mock_config_entry, snap)
    live = coordinator.live_scale_evidence("riko-001")
    assert live["scale_live_g"] == 89.08
    assert live["scale_live_as_of"] == asked_at
    assert "scale_state_as_of" not in live, "one answer's evidence names nothing else"

    weight = NeakasaBowlWeightSensor(coordinator, DEVICE_INFO, "riko-001")
    assert weight.native_value == 21, (
        "89.08 g over the 68 g tare the same answer states"
    )
    attributes = weight.extra_state_attributes
    assert attributes["scale_live_g"] == 89.08
    assert attributes["scale_live_as_of"] == asked_at
    assert attributes["scale_reading_g"] == 67, (
        "the stored copy stays visible beside it"
    )


def test_only_an_answer_the_machine_labels_as_a_weighing_is_read_as_one() -> None:
    """A refusal, another read type or an unreadable number invents nothing."""
    assert (
        _service_answer({"data": {"ReturnCode": 1, "Params": {"type": "scale"}}}) == {}
    )
    assert _live_scale({"type": "pwr", "str": {"bat": {"percent": 85}}}) == (None, None)
    assert _live_scale(
        {"type": "scale", "str": {"gram": "89.08", "bowlGram": "68"}}
    ) == (89.08, 68)

    props = copy.deepcopy(_answered())
    props["bowlStatus"] = {
        "time": 1793100000000,
        "value": {"bowlGram": 68, "curWeight": 90, "bBowlIn": 1},
    }
    snap = _build_pet_feeder_snapshot(
        "riko-001",
        "SERIALFAKE0000000000000",
        props,
        "a1ccEqBcaUD",
        "TestLabel",
        None,
        {"type": "waterLv", "str": {"vol": 1677, "lv": 3}},
        "2026-10-27T14:44:07+00:00",
    )
    assert snap.scale_live_g is None
    assert snap.scale_live_ts is None
    weight = NeakasaBowlWeightSensor(_mock_coord(snap), DEVICE_INFO, "riko-001")
    assert weight.native_value == 22, "the stored copy still says what it stated"


async def test_the_scan_asks_the_machine_for_the_weighing_once(
    hass: HomeAssistant, mock_config_entry: MagicMock
) -> None:
    """The read is the definition's 称重 command; a refusal claims no moment."""
    coordinator = _make_coordinator(hass, mock_config_entry, _snapshot(_answered()))
    client = AsyncMock()
    client.invoke_service = AsyncMock(
        return_value={
            "data": {
                "ReturnCode": 0,
                "Params": {"type": "scale", "str": {"bowlGram": 68, "gram": 89.08}},
            },
            "messageId": "849220164",
        }
    )
    coordinator._get_client = AsyncMock(return_value=client)

    answer, asked_at = await coordinator._read_live_scale("riko-001", client)
    client.invoke_service.assert_awaited_once_with(
        "riko-001", "iotRead", {"readType": 2}
    )
    assert answer["str"]["gram"] == 89.08
    assert asked_at is not None

    client.invoke_service = AsyncMock(
        side_effect=NeakasaApiClientCommunicationError("gateway.hsf.invoke.timeout")
    )
    answer, asked_at = await coordinator._read_live_scale("riko-001", client)
    assert answer == {}
    assert asked_at is None, "a refusal states nothing, so no moment is claimed"


async def test_a_state_report_carries_the_moment_that_report_made(
    hass: HomeAssistant, mock_config_entry: MagicMock
) -> None:
    """The state keys are re-pushed, so each one is dated by its own stamp."""
    coordinator = _make_coordinator(hass, mock_config_entry, _snapshot(_answered()))
    state = coordinator.device_state_evidence("riko-001")
    assert state["state_value"] == 0
    assert state["state_param"] == 0
    assert state["state_as_of"].startswith("2026-10-27T09:44")
    assert state["state_age_minutes"] >= 0
    assert "deep_clean_as_of" not in state, "one state's evidence names nothing else"

    wash = coordinator.deep_clean_evidence("riko-001")
    assert wash["deep_clean_state"] == 0
    assert wash["deep_clean_as_of"].startswith("2026-10-27T00:56")

    battery = coordinator.battery_state_evidence("riko-001")
    assert battery["battery_state"] == 2
    assert battery["battery_as_of"].startswith("2026-10-27T00:56")

    status = NeakasaDeviceStatusSensor(coordinator, DEVICE_INFO, "riko-001")
    assert status.extra_state_attributes == state

    serving = NeakasaServingFoodBinarySensor(coordinator, DEVICE_INFO, "riko-001")
    assert serving.extra_state_attributes == state

    in_place = NeakasaBowlInPlaceBinarySensor(coordinator, DEVICE_INFO, "riko-001")
    assert in_place.extra_state_attributes == coordinator.scale_state_evidence(
        "riko-001"
    )


def test_the_state_sensors_name_their_codes_as_the_definition_spells_them() -> None:
    """The state names are the definition's; an unknown code passes through."""
    props = copy.deepcopy(_answered())
    props["deviceState"] = {"time": 1, "value": {"param": 7, "state": 2}}
    props["deepCleanCfg"] = {"time": 1, "value": {"bOnOff": 1, "cleanState": 3}}
    props["pwrStatus"] = {"time": 1, "value": {"batStatus": 1}}
    snap = _snapshot(props)
    coordinator = _mock_coord(snap)

    status = NeakasaDeviceStatusSensor(coordinator, DEVICE_INFO, "riko-001")
    assert status.native_value == "serving_food"

    serving = NeakasaServingFoodBinarySensor(coordinator, DEVICE_INFO, "riko-001")
    assert serving.is_on is True

    wash = NeakasaDeepCleanStateSensor(coordinator, DEVICE_INFO, "riko-001")
    assert wash.native_value == "rinsing_water_channel"

    battery = NeakasaBatteryStateSensor(coordinator, DEVICE_INFO, "riko-001")
    assert battery.native_value == "charging"

    other = _snapshot(
        {**_answered(), "deviceState": {"time": 1, "value": {"state": 12, "param": 0}}}
    )
    unknown = NeakasaDeviceStatusSensor(_mock_coord(other), DEVICE_INFO, "riko-001")
    assert unknown.native_value == 12, "an unknown code is not given an invented name"

    off = _snapshot(
        {**_answered(), "deviceState": {"time": 1, "value": {"state": 5, "param": 0}}}
    )
    dormant = NeakasaServingFoodBinarySensor(_mock_coord(off), DEVICE_INFO, "riko-001")
    assert dormant.is_on is False

    no_bowl = _snapshot(
        {k: v for k, v in _answered().items() if k != "bowlStatus"}
        | {
            "bowlStatus": {
                "time": 1,
                "value": {"bowlGram": 68, "curWeight": 90, "bBowlIn": 0},
            }
        }
    )
    bowl = NeakasaBowlInPlaceBinarySensor(_mock_coord(no_bowl), DEVICE_INFO, "riko-001")
    assert bowl.is_on is False


def test_read_only_sensors_show_what_the_machine_states() -> None:
    snap = _snapshot(_answered())
    weight = NeakasaBowlWeightSensor(_mock_coord(snap), DEVICE_INFO, "riko-001")
    assert weight.native_value == 0, "the bowl's contents, not the scale's raw reading"
    assert weight.translation_key == "bowl_weight"
    assert weight.unique_id == "riko-001-bowl_weight"

    days = NeakasaDesiccantDaysLeftSensor(_mock_coord(snap), DEVICE_INFO, "riko-001")
    assert days.native_value == 38

    firmware = NeakasaFirmwareVersionSensor(_mock_coord(snap), DEVICE_INFO, "riko-001")
    assert firmware.native_value == "1.0.0-0033"
    assert firmware.extra_state_attributes == {"hw_version": "1.00.01"}

    serial = NeakasaDeviceSerialSensor(_mock_coord(snap), DEVICE_INFO, "riko-001")
    assert serial.native_value == "SERIALFAKE0000000000000"

    water_clean = NeakasaWaterBinCleanSensor(_mock_coord(snap), DEVICE_INFO, "riko-001")
    assert water_clean.native_value == "2026-10-19 07:18:49"
    food_clean = NeakasaFoodBinCleanSensor(_mock_coord(snap), DEVICE_INFO, "riko-001")
    assert food_clean.native_value is None

    intake = NeakasaFoodIntakeTodaySensor(_mock_coord(snap), DEVICE_INFO, "riko-001")
    assert intake.native_value is None
    solids = NeakasaFoodIntakeTodaySolidsSensor(
        _mock_coord(snap), DEVICE_INFO, "riko-001"
    )
    assert solids.native_value is None
    assert solids.unique_id == "riko-001-food_intake_today_solids"
    assert solids.translation_key == "food_intake_today_solids"
    assert solids.entity_registry_enabled_default is False
    liquid = NeakasaFoodIntakeTodayLiquidSensor(
        _mock_coord(snap), DEVICE_INFO, "riko-001"
    )
    assert liquid.native_value is None
    assert liquid.unique_id == "riko-001-food_intake_today_liquid"
    assert liquid.translation_key == "food_intake_today_liquid"
    assert liquid.entity_registry_enabled_default is False


def test_the_three_day_figures_read_the_meals_recorded() -> None:
    """The total is the two halves, and each half is only its own."""
    day_start, midnight = _fixed_local_day()
    rows = [
        {"feed_time": day_start - 60, "feed_weight": 99, "water_weight": 99},
        {"feed_time": day_start + 60, "feed_weight": 10, "water_weight": 9},
    ]
    with patch(
        "custom_components.neakasa.coordinator.start_of_local_day",
        return_value=midnight,
    ):
        answered = _snapshot(_answered(), {"feed_list": rows})
        coordinator = _mock_coord(answered)
        total = NeakasaFoodIntakeTodaySensor(coordinator, DEVICE_INFO, "riko-001")
        solids = NeakasaFoodIntakeTodaySolidsSensor(
            coordinator, DEVICE_INFO, "riko-001"
        )
        liquid = NeakasaFoodIntakeTodayLiquidSensor(
            coordinator, DEVICE_INFO, "riko-001"
        )
    assert total.native_value == 19
    assert solids.native_value == 10
    assert liquid.native_value == 9
    assert total.unique_id == "riko-001-food_intake_today"


async def test_the_day_figure_names_the_meals_it_groups(
    hass: HomeAssistant, mock_config_entry: MagicMock
) -> None:
    """A grouped figure states the meals it came from and when they were read."""
    day_start, midnight = _fixed_local_day()
    rows = [{"feed_time": day_start + 60, "feed_weight": 10, "water_weight": 9}]
    with patch(
        "custom_components.neakasa.coordinator.start_of_local_day",
        return_value=midnight,
    ):
        snap = _snapshot(_answered(), {"feed_list": rows})
    coordinator = _make_coordinator(hass, mock_config_entry, snap)
    coordinator._records_when = {"riko-001": day_start + 120}
    evidence = coordinator.served_today_evidence("riko-001")
    assert evidence["meals_today"] == 1
    assert evidence["solid_g"] == 10
    assert evidence["liquid_g"] == 9
    assert evidence["meal_times"] == [
        datetime.fromtimestamp(day_start + 60, tz=UTC).isoformat()
    ]
    assert (
        evidence["records_as_of"]
        == datetime.fromtimestamp(day_start + 120, tz=UTC).isoformat()
    )
    assert evidence["records_age_minutes"] >= 0

    total = NeakasaFoodIntakeTodaySensor(coordinator, DEVICE_INFO, "riko-001")
    assert total.native_value == 19
    assert total.extra_state_attributes == evidence

    blank = _make_coordinator(hass, mock_config_entry, _snapshot(_answered()))
    assert blank.served_today_evidence("riko-001") == {}, (
        "a figure with no meals behind it names none either"
    )


def test_settings_read_the_state_without_inventing_one() -> None:
    """A control the machine never stated is off/unknown, not a default."""
    answered = _snapshot(_answered())
    manager = NeakasaFreshMealManagerSwitch(
        _mock_coord(answered), DEVICE_INFO, "riko-001"
    )
    assert manager.is_on is False
    display = NeakasaDisplayStandbySwitch(
        _mock_coord(answered), DEVICE_INFO, "riko-001"
    )
    assert display.is_on is True
    dnd = NeakasaDoNotDisturbSwitch(_mock_coord(answered), DEVICE_INFO, "riko-001")
    assert dnd.is_on is True

    bare = _snapshot(BASE)
    quiet = NeakasaDoNotDisturbSwitch(_mock_coord(bare), DEVICE_INFO, "riko-001")
    assert quiet.is_on is False
    volume = NeakasaFeedSoundVolumeNumber(_mock_coord(bare), DEVICE_INFO, "riko-001")
    assert volume.value is None
    kind = NeakasaDisplayStandbyKindSelect(_mock_coord(bare), DEVICE_INFO, "riko-001")
    assert kind.current_option is None


def test_ranges_stop_at_the_product_definition() -> None:
    """The rehydration minutes and the sound volume stop at their bounds."""
    assert MIX_MIN_MAX == 30
    assert FEED_SOUND_VOLUME_MAX == 100
    assert DESICCANT_DAYS_MAX == 60
    number = NeakasaRehydrationMinutesNumber(MagicMock(), DEVICE_INFO, "riko-001")
    assert number.max_value == float(MIX_MIN_MAX)
    assert number.min_value == 0.0


async def test_switch_writes_keep_the_untouched_parts() -> None:
    """Toggling one part of a nested config leaves the rest as it was."""
    snap = _snapshot(_answered())
    coordinator = _mock_coord(snap)

    manager = NeakasaFreshMealManagerSwitch(coordinator, DEVICE_INFO, "riko-001")
    await manager.async_turn_on()
    coordinator.set_property.assert_any_await(
        "riko-001",
        "fresh_mgr_cfg",
        {"monitorTime": 4, "leftOverTTH": 20, "bOnOff": 1},
    )

    display = NeakasaDisplayStandbySwitch(coordinator, DEVICE_INFO, "riko-001")
    await display.async_turn_off()
    coordinator.set_property.assert_any_await(
        "riko-001",
        "display_cfg",
        {"displayType": 1, "displayParam": "N/A", "bDisplayIfIdle": 0},
    )

    dnd = NeakasaDoNotDisturbSwitch(coordinator, DEVICE_INFO, "riko-001")
    await dnd.async_turn_off()
    coordinator.set_property.assert_any_await(
        "riko-001",
        "dnd_cfg",
        {"active": 0, "startTime": 3600, "endTime": 7200, "weekRept": 127},
    )


async def test_numbers_write_only_the_value_they_own(
    hass: HomeAssistant, mock_config_entry: MagicMock
) -> None:
    """A setting writes its own key and keeps its siblings."""
    coordinator = _make_coordinator(hass, mock_config_entry, _snapshot(_answered()))
    client = AsyncMock()
    coordinator._get_client = AsyncMock(return_value=client)
    snap = coordinator.data["riko-001"]

    minutes = NeakasaRehydrationMinutesNumber(coordinator, DEVICE_INFO, "riko-001")
    await minutes.async_set_native_value(12)
    client.set_device_properties.assert_any_call(
        "riko-001", {"defFdCfg": {"mixMin": 12, "water": 4, "food": 4}}
    )
    assert snap.mix_min_minutes == 12

    days = NeakasaDesiccantDaysNumber(coordinator, DEVICE_INFO, "riko-001")
    await days.async_set_native_value(45)
    client.set_device_properties.assert_any_call("riko-001", {"drierEffeDays": 45})
    assert snap.desiccant_days_effective == 45

    volume = NeakasaFeedSoundVolumeNumber(coordinator, DEVICE_INFO, "riko-001")
    await volume.async_set_native_value(0)
    client.set_device_properties.assert_any_call(
        "riko-001", {"feedAudCfg": {"audIdx": 0, "volume": 0}}
    )
    assert snap.sound_volume == 0


async def test_display_kind_and_message_write_the_display_config(
    hass: HomeAssistant, mock_config_entry: MagicMock
) -> None:
    """The kind and the text are two halves of the same nested config."""
    coordinator = _make_coordinator(hass, mock_config_entry, _snapshot(_answered()))
    snap = coordinator.data["riko-001"]

    kind = NeakasaDisplayStandbyKindSelect(coordinator, DEVICE_INFO, "riko-001")
    await kind.async_select_option("custom")
    assert snap.display_cfg["displayType"] == 2
    assert snap.display_cfg["displayParam"] == "N/A"

    message = NeakasaDisplayCustomMessageText(coordinator, DEVICE_INFO, "riko-001")
    await message.async_set_value("Neakasa")
    assert snap.display_cfg["displayParam"] == "NEAKASA"
    assert snap.display_cfg["displayType"] == 2


async def test_a_display_that_states_no_message_still_takes_one(
    hass: HomeAssistant, mock_config_entry: MagicMock
) -> None:
    """An empty message is a state, so the field stays typeable."""
    props = copy.deepcopy(BASE)
    props["displayCfg"] = {"value": {"displayType": 2, "bDisplayIfIdle": 1}}
    coordinator = _make_coordinator(hass, mock_config_entry, _snapshot(props))
    snap = coordinator.data["riko-001"]

    message = NeakasaDisplayCustomMessageText(coordinator, DEVICE_INFO, "riko-001")
    assert message.native_value == ""
    assert message.state == ""
    await message.async_set_value("Neakasa")
    assert snap.display_cfg == {
        "displayType": 2,
        "bDisplayIfIdle": 1,
        "displayParam": "NEAKASA",
    }


async def test_a_press_takes_its_siblings_from_the_machine(
    hass: HomeAssistant, mock_config_entry: MagicMock
) -> None:
    """A change made outside Home Assistant is not written back by a press."""
    coordinator = _make_coordinator(hass, mock_config_entry, _snapshot(_answered()))
    snap = coordinator.data["riko-001"]
    assert snap.display_cfg["displayParam"] == "N/A", "the model holds an older state"

    client = AsyncMock()
    client.get_device_properties = AsyncMock(
        return_value={
            "displayCfg": {
                "time": 1793056632778,
                "value": {"displayType": 0, "displayParam": "", "bDisplayIfIdle": 1},
            }
        }
    )
    coordinator._get_client = AsyncMock(return_value=client)

    kind = NeakasaDisplayStandbyKindSelect(coordinator, DEVICE_INFO, "riko-001")
    await kind.async_select_option("custom")
    client.set_device_properties.assert_called_once_with(
        "riko-001",
        {"displayCfg": {"displayType": 2, "displayParam": "", "bDisplayIfIdle": 1}},
    )
    assert snap.display_type == 2
    assert snap.display_param == "", "the machine's message, not the older one"


async def test_buttons_ask_the_machine_its_own_commands(
    hass: HomeAssistant, mock_config_entry: MagicMock
) -> None:
    """Each press asks for the command the definition names for it."""
    coordinator = _make_coordinator(hass, mock_config_entry, _snapshot(_answered()))
    client = AsyncMock()
    coordinator._get_client = AsyncMock(return_value=client)

    await NeakasaResetDesiccantButton(
        coordinator, DEVICE_INFO, "riko-001"
    ).async_press()
    client.invoke_service.assert_called_with(
        "riko-001", "resetDrierTime", {"drierEffeDays": 40}
    )

    await NeakasaResetBowlScaleButton(
        coordinator, DEVICE_INFO, "riko-001"
    ).async_press()
    client.invoke_service.assert_called_with(
        "riko-001", "resetScaleZero", {"bowlGram": 68}
    )

    await NeakasaCalibrateFoodScaleButton(
        coordinator, DEVICE_INFO, "riko-001"
    ).async_press()
    client.invoke_service.assert_called_with("riko-001", "fdCalbration", {})

    with patch(
        "custom_components.neakasa.coordinator._clean_stamp",
        return_value="2026-10-26 19:53:00",
    ):
        await NeakasaMarkWaterBinCleanButton(
            coordinator, DEVICE_INFO, "riko-001"
        ).async_press()
        client.set_device_properties.assert_called_with(
            "riko-001", {"lastWaterBinCleanTime": "2026-10-26 19:53:00"}
        )
        await NeakasaMarkFoodBinCleanButton(
            coordinator, DEVICE_INFO, "riko-001"
        ).async_press()
        client.set_device_properties.assert_called_with(
            "riko-001", {"lastFoodBinCleanTime": "2026-10-26 19:53:00"}
        )


async def test_a_config_entry_registers_the_new_platforms(
    hass: HomeAssistant, mock_config_entry: MagicMock
) -> None:
    """The feeder's new controls are offered for a feeder, not for a litter box."""
    from custom_components.neakasa import PLATFORMS
    from custom_components.neakasa.select import async_setup_entry as select_setup
    from custom_components.neakasa.text import async_setup_entry as text_setup

    assert "select" in [str(platform.value) for platform in PLATFORMS]
    assert "text" in [str(platform.value) for platform in PLATFORMS]

    coordinator = _make_coordinator(hass, mock_config_entry, _snapshot(_answered()))
    mock_config_entry.runtime_data.coordinator = coordinator
    mock_config_entry.async_on_unload = MagicMock()

    selected: list = []
    await select_setup(hass, mock_config_entry, selected.extend)
    assert len(selected) == 1
    assert isinstance(selected[0], NeakasaDisplayStandbyKindSelect)

    written: list = []
    await text_setup(hass, mock_config_entry, written.extend)
    assert len(written) == 1
    assert isinstance(written[0], NeakasaDisplayCustomMessageText)


async def test_a_litter_box_gets_none_of_the_feeder_controls(
    hass: HomeAssistant, mock_config_entry: MagicMock
) -> None:
    """A cat device never receives a feeder's settings."""
    from custom_components.neakasa.select import async_setup_entry as select_setup

    litter = MagicMock()
    litter.category_key = "CatLitter"
    coordinator = _make_coordinator(hass, mock_config_entry, litter)
    mock_config_entry.runtime_data.coordinator = coordinator
    mock_config_entry.async_on_unload = MagicMock()

    selected: list = []
    await select_setup(hass, mock_config_entry, selected.extend)
    assert selected == []


async def test_a_bowl_weight_the_machine_never_stated_is_refused(
    hass: HomeAssistant, mock_config_entry: MagicMock
) -> None:
    """Re-zeroing the scale cannot invent a bowl weight to use."""
    no_bowl = _snapshot({k: v for k, v in BASE.items() if k != "bowlStatus"})
    coordinator = _make_coordinator(hass, mock_config_entry, no_bowl)
    coordinator._get_client = AsyncMock()
    with pytest.raises(ValueError, match="No bowl weight"):
        await NeakasaResetBowlScaleButton(
            coordinator, DEVICE_INFO, "riko-001"
        ).async_press()


def test_riko_sensors_answer_nothing_without_a_snapshot() -> None:
    """A device the coordinator has no model for reports no value."""
    sensor_classes = [
        NeakasaBatterySensor,
        NeakasaBatteryStateSensor,
        NeakasaBowlWeightSensor,
        NeakasaDeepCleanStateSensor,
        NeakasaDesiccantDaysLeftSensor,
        NeakasaDeviceSerialSensor,
        NeakasaDeviceStatusSensor,
        NeakasaFirmwareVersionSensor,
        NeakasaFoodIntakeTodaySensor,
        NeakasaFoodIntakeTodaySolidsSensor,
        NeakasaFoodIntakeTodayLiquidSensor,
        NeakasaFoodBinCleanSensor,
        NeakasaWaterBinCleanSensor,
        NeakasaFoodLevelSensor,
        NeakasaLabelSensor,
        NeakasaWaterLevelSensor,
    ]
    coordinator = _mock_coord(None)
    for sensor_cls in sensor_classes:
        sensor = sensor_cls(coordinator, DEVICE_INFO, "riko-001")
        sensor.hass = MagicMock()
        assert sensor.native_value is None


def test_a_battery_state_the_definition_never_named_stays_the_number_it_is() -> None:
    """An unknown code is passed through; a state never stated is none."""
    props = copy.deepcopy(_answered())
    props["pwrStatus"] = {"time": 1, "value": {"batPercentage": 90, "batStatus": 7}}
    answered_state = _mock_coord(_snapshot(props))
    stated = NeakasaBatteryStateSensor(answered_state, DEVICE_INFO, "riko-001")
    assert stated.native_value == 7, "an unknown code is not given an invented name"

    never_stated = _mock_coord(_snapshot(BASE))
    never = NeakasaBatteryStateSensor(never_stated, DEVICE_INFO, "riko-001")
    assert never.native_value is None, "no state was stated, so none is shown"


def _fake_platform_data() -> MagicMock:
    """Enough of an EntityPlatform.platform_data to let a state write run."""
    platform_data = MagicMock()
    platform_data.platform_name = "sensor"
    platform_data.domain = "sensor"
    platform_data.platform_translations = {}
    platform_data.component_translations = {}
    platform_data.object_id_platform_translations = {}
    platform_data.object_id_component_translations = {}
    return platform_data


async def test_riko_entities_write_only_once_registered(hass: HomeAssistant) -> None:
    """An entity stays silent until it has an entity_id to write to."""
    sensor_classes = [
        NeakasaBatterySensor,
        NeakasaBatteryStateSensor,
        NeakasaBowlWeightSensor,
        NeakasaDeepCleanStateSensor,
        NeakasaDesiccantDaysLeftSensor,
        NeakasaDeviceSerialSensor,
        NeakasaDeviceStatusSensor,
        NeakasaFirmwareVersionSensor,
        NeakasaFoodIntakeTodaySensor,
        NeakasaFoodIntakeTodaySolidsSensor,
        NeakasaFoodIntakeTodayLiquidSensor,
        NeakasaFoodBinCleanSensor,
        NeakasaWaterBinCleanSensor,
        NeakasaFoodLevelSensor,
        NeakasaLabelSensor,
        NeakasaWaterLevelSensor,
    ]
    for index, sensor_cls in enumerate(sensor_classes):
        coordinator = _mock_coord(_snapshot(_answered()))
        sensor = sensor_cls(coordinator, DEVICE_INFO, "riko-001")
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
        assert coordinator.state_fingerprint.called

        before = coordinator.state_fingerprint.call_count
        sensor.entity_id = None
        await sensor.async_update()
        assert coordinator.state_fingerprint.call_count == before, (
            "an entity with no entity_id writes no state"
        )

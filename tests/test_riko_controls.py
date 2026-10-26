"""Tests for the Riko controls beyond feeding: what the machine holds.

Several of these wire shapes exist in the product's definition and have never
been answered by the unit, so the tests that keep a value unknown matter as much
as the tests that read one.
"""

from __future__ import annotations

import copy
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant

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
    _feed_grams_today,
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
from custom_components.neakasa.sensor.bowl_weight import NeakasaBowlWeightSensor
from custom_components.neakasa.sensor.desiccant_days_left import (
    NeakasaDesiccantDaysLeftSensor,
)
from custom_components.neakasa.sensor.device_serial import NeakasaDeviceSerialSensor
from custom_components.neakasa.sensor.firmware_version import (
    NeakasaFirmwareVersionSensor,
)
from custom_components.neakasa.sensor.food_intake_today import (
    NeakasaFoodIntakeTodaySensor,
)
from custom_components.neakasa.sensor.last_bin_clean_food import (
    NeakasaFoodBinCleanSensor,
)
from custom_components.neakasa.sensor.last_bin_clean_water import (
    NeakasaWaterBinCleanSensor,
)
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
}

BASE: dict = {
    "foodLvl": {"value": 2},
    "waterLvl": {"value": 3},
    "bowlStatus": {"value": {"bowlGram": 68, "curWeight": 67, "bBowlIn": 1}},
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
    assert snap.desiccant_days_effective == 40
    assert snap.display_type == 1
    assert snap.display_when_idle is True
    assert snap.sound_volume == 100
    assert snap.dnd_active is True
    assert snap.firmware_version == "1.0.0-0033"
    assert snap.device_serial == "SERIALFAKE0000000000000"


def test_unanswered_controls_stay_unknown() -> None:
    """Nothing is invented for a key the machine has never answered."""
    snap = _snapshot(BASE)
    assert snap.display_type is None
    assert snap.display_when_idle is None
    assert snap.sound_volume is None
    assert snap.desiccant_days_effective is None
    assert snap.firmware_version is None
    assert snap.feed_today_g is None


def test_meals_recorded_today_are_summed() -> None:
    """A delivery record names its grams and the time it ran at."""
    now = int(time.time())
    records = {
        "record_list": [
            {"feed_time": now - 60, "feed_weight": 12},
            {"feed_time": now - 60, "water_weight": 24},
            {"feed_time": now - 60 - 9 * 86400, "feed_weight": 99},
        ]
    }
    assert _feed_grams_today(records) == 12


def test_unrecognisable_records_produce_no_number() -> None:
    """An answer with no grams is not reported as zero grams."""
    assert _feed_grams_today({"record_list": []}) is None
    assert _feed_grams_today({"record_list": [{"plan": "x"}]}) is None
    assert _feed_grams_today(None) is None


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


def test_read_only_sensors_show_what_the_machine_states() -> None:
    snap = _snapshot(_answered())
    weight = NeakasaBowlWeightSensor(_mock_coord(snap), DEVICE_INFO, "riko-001")
    assert weight.native_value == 67
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
    assert snap.display_cfg["displayParam"] == "Neakasa"
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
        "displayParam": "Neakasa",
    }


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

"""Tests for the number platform: the settings a Riko feeder accepts.

A setting is only claimed by a device that can hold it, and a machine that never
stated a value leaves the setting empty rather than inventing a plausible one.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant

from custom_components.neakasa.const import (
    DEFAULT_FEED_FOOD_G,
    DEFAULT_FEED_WATER_RATIO,
    DESICCANT_DAYS_MAX,
    DESICCANT_DAYS_MIN,
    FEED_FOOD_MAX_G,
    FEED_FOOD_MIN_G,
    FEED_WATER_RATIO_MAX,
    FEED_WATER_RATIO_MIN,
)
from custom_components.neakasa.coordinator import NeakasaDeviceSnapshot
from custom_components.neakasa.number import async_setup_entry
from custom_components.neakasa.number.desiccant_days import NeakasaDesiccantDaysNumber
from custom_components.neakasa.number.feed_sound_volume import (
    NeakasaFeedSoundVolumeNumber,
)
from custom_components.neakasa.number.food_grams import NeakasaFoodGramsNumber
from custom_components.neakasa.number.rehydration_minutes import (
    NeakasaRehydrationMinutesNumber,
)
from custom_components.neakasa.number.water_ratio import NeakasaWaterRatioNumber

NUMBER_CLASSES: tuple[type, ...] = (
    NeakasaDesiccantDaysNumber,
    NeakasaFeedSoundVolumeNumber,
    NeakasaFoodGramsNumber,
    NeakasaRehydrationMinutesNumber,
    NeakasaWaterRatioNumber,
)

DEVICE_INFO = {"identifiers": {("neakasa", "riko-001")}}


def _device(category_key: str, iot_id: str, device_name: str) -> NeakasaDeviceSnapshot:
    """A snapshot whose only role here is to name the product it belongs to."""
    return NeakasaDeviceSnapshot(
        iot_id=iot_id,
        device_name=device_name,
        category_key=category_key,
        product_key="a1ccEqBcaUD",
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
    )


_UNCHANGED = "the-same-model"


def _stated(*, answered: bool) -> MagicMock:
    """A coordinator stand-in that answers every setting or none of them."""
    coordinator = MagicMock()
    coordinator.state_fingerprint.return_value = _UNCHANGED
    if not answered:
        coordinator.device_snapshot.return_value = None
        coordinator.feed_values.return_value = (
            DEFAULT_FEED_FOOD_G,
            DEFAULT_FEED_WATER_RATIO,
        )
        return coordinator
    snap = _device("petFeeder", "riko-001", "Riko")
    snap.desiccant_days_effective = 40
    snap.sound_volume = 100
    snap.mix_min_minutes = 12
    coordinator.device_snapshot.return_value = snap
    coordinator.feed_values.return_value = (14, 4)
    coordinator.set_property = AsyncMock()
    coordinator.set_feed_sound_volume = AsyncMock()
    coordinator.set_rehydration_minutes = AsyncMock()
    return coordinator


def _read(number_cls: type, *, answered: bool) -> float | None:
    """Read one setting through its update path, with the state write skipped."""
    number = number_cls(_stated(answered=answered), DEVICE_INFO, "riko-001")
    number._last_state_stamp = _UNCHANGED
    number._handle_coordinator_update()
    return number.value


async def test_number_setup_claims_only_feeders(hass: HomeAssistant) -> None:
    """A Riko feeder gets its five settings; a litter box gets none of them."""
    coordinator = MagicMock()
    coordinator.data = {
        "riko-001": _device("petFeeder", "riko-001", "Riko"),
        "iot-001": _device("CatLitter", "iot-001", "T1 Plus"),
    }
    config_entry = MagicMock()
    config_entry.runtime_data.coordinator = coordinator
    config_entry.async_on_unload = MagicMock()

    collected: list = []
    await async_setup_entry(hass, config_entry, collected.extend)

    assert {entity.unique_id for entity in collected} == {
        "riko-001-desiccant_days",
        "riko-001-feed_sound_volume",
        "riko-001-food_grams",
        "riko-001-rehydration_minutes",
        "riko-001-water_ratio",
    }
    assert all(isinstance(entity, NUMBER_CLASSES) for entity in collected)
    config_entry.async_on_unload.assert_called_once()

    rediscover = coordinator.async_add_listener.call_args.args[0]

    coordinator.data = {
        "riko-001": _device("petFeeder", "riko-001", "Riko"),
        "riko-002": _device("petFeeder", "riko-002", "Riko 2"),
    }
    before = len(collected)
    rediscover()
    assert len(collected) == before + 5
    assert {entity.unique_id for entity in collected[-5:]} == {
        "riko-002-desiccant_days",
        "riko-002-feed_sound_volume",
        "riko-002-food_grams",
        "riko-002-rehydration_minutes",
        "riko-002-water_ratio",
    }

    rediscover()
    assert len(collected) == before + 5


def test_settings_read_what_the_machine_stated() -> None:
    """Each setting shows the value its own key states."""
    assert _read(NeakasaDesiccantDaysNumber, answered=True) == 40.0
    assert _read(NeakasaFeedSoundVolumeNumber, answered=True) == 100.0
    assert _read(NeakasaRehydrationMinutesNumber, answered=True) == 12.0
    assert _read(NeakasaFoodGramsNumber, answered=True) == 14.0
    assert _read(NeakasaWaterRatioNumber, answered=True) == 4.0


MACHINE_STATED_SETTINGS: tuple[type, ...] = (
    NeakasaDesiccantDaysNumber,
    NeakasaFeedSoundVolumeNumber,
    NeakasaRehydrationMinutesNumber,
)


def test_settings_answer_nothing_when_the_machine_never_stated_them() -> None:
    """A setting the machine never stated is empty, not a plausible default."""
    for number_cls in MACHINE_STATED_SETTINGS:
        assert _read(number_cls, answered=False) is None


def test_feed_settings_show_the_amounts_the_next_feed_would_use() -> None:
    """The feed pair reports the coordinator's claim, defaults included."""
    assert _read(NeakasaFoodGramsNumber, answered=False) == float(DEFAULT_FEED_FOOD_G)
    assert _read(NeakasaWaterRatioNumber, answered=False) == float(
        DEFAULT_FEED_WATER_RATIO
    )


def test_settings_stop_at_the_product_definition() -> None:
    """The offered ranges are the definition's, never the machine's wider one."""
    grams = NeakasaFoodGramsNumber(MagicMock(), DEVICE_INFO, "riko-001")
    assert grams.min_value == float(FEED_FOOD_MIN_G)
    assert grams.max_value == float(FEED_FOOD_MAX_G)
    ratio = NeakasaWaterRatioNumber(MagicMock(), DEVICE_INFO, "riko-001")
    assert ratio.min_value == float(FEED_WATER_RATIO_MIN)
    assert ratio.max_value == float(FEED_WATER_RATIO_MAX)
    days = NeakasaDesiccantDaysNumber(MagicMock(), DEVICE_INFO, "riko-001")
    assert days.min_value == float(DESICCANT_DAYS_MIN)
    assert days.max_value == float(DESICCANT_DAYS_MAX)


async def test_number_lifecycle_methods(hass: HomeAssistant) -> None:
    """Register every number and show it stays silent before it has an id."""
    for index, number_cls in enumerate(NUMBER_CLASSES):
        number = number_cls(_stated(answered=True), DEVICE_INFO, "riko-001")
        number.hass = hass
        platform_data = MagicMock()
        platform_data.platform_name = "number"
        platform_data.domain = "number"
        platform_data.platform_translations = {}
        platform_data.component_translations = {}
        platform_data.object_id_platform_translations = {}
        platform_data.object_id_component_translations = {}
        number.platform_data = platform_data
        fake_platform = MagicMock()
        fake_platform.platform_name = "number"
        fake_platform.entity_platform = MagicMock()
        number.platform = fake_platform
        number.entity_id = f"number.neakasa_{index}"
        await number.async_added_to_hass()
        await number.async_update()
        assert number.value is not None

        number.entity_id = None
        await number.async_update()


async def test_feed_settings_hold_the_amounts_until_the_next_feed() -> None:
    """A feed amount set here is remembered for the next feed, not written."""
    coordinator = _stated(answered=True)
    grams = NeakasaFoodGramsNumber(coordinator, DEVICE_INFO, "riko-001")
    await grams.async_set_native_value(9)
    coordinator.set_pending_feed.assert_any_call("riko-001", food_g=9)

    ratio = NeakasaWaterRatioNumber(coordinator, DEVICE_INFO, "riko-001")
    await ratio.async_set_native_value(5)
    coordinator.set_pending_feed.assert_any_call("riko-001", water_ratio=5)


async def test_settings_write_the_machine_key_they_own() -> None:
    """The settings that do reach the machine write only their own key."""
    coordinator = _stated(answered=True)
    days = NeakasaDesiccantDaysNumber(coordinator, DEVICE_INFO, "riko-001")
    await days.async_set_native_value(45)
    coordinator.set_property.assert_awaited_once_with(
        "riko-001", "desiccant_days_effective", 45
    )

    volume = NeakasaFeedSoundVolumeNumber(coordinator, DEVICE_INFO, "riko-001")
    await volume.async_set_native_value(0)
    coordinator.set_feed_sound_volume.assert_awaited_once_with("riko-001", 0)

    minutes = NeakasaRehydrationMinutesNumber(coordinator, DEVICE_INFO, "riko-001")
    await minutes.async_set_native_value(12)
    coordinator.set_rehydration_minutes.assert_awaited_once_with("riko-001", 12)


async def test_desiccant_days_refuses_a_budget_the_definition_does_not_allow() -> None:
    """A day budget outside the range never reaches the machine."""
    coordinator = _stated(answered=True)
    days = NeakasaDesiccantDaysNumber(coordinator, DEVICE_INFO, "riko-001")
    with pytest.raises(ValueError, match="Days out of range"):
        await days.async_set_native_value(DESICCANT_DAYS_MAX + 1)
    coordinator.set_property.assert_not_called()

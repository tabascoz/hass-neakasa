"""Tests for switch entities."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from homeassistant.core import HomeAssistant

from custom_components.neakasa.coordinator import NeakasaDeviceSnapshot
from custom_components.neakasa.switch.auto_bury import NeakasaAutoBurySwitch
from custom_components.neakasa.switch.auto_clean import NeakasaAutoCleanSwitch
from custom_components.neakasa.switch.auto_level import NeakasaAutoLevelSwitch
from custom_components.neakasa.switch.auto_recovery import NeakasaAutoRecoverySwitch
from custom_components.neakasa.switch.child_lock import NeakasaChildLockSwitch
from custom_components.neakasa.switch.feed_keep_defaults import (
    NeakasaFeedKeepDefaultsSwitch,
)
from custom_components.neakasa.switch.silent_mode import NeakasaSilentModeSwitch
from custom_components.neakasa.switch.unstoppable_cycle import (
    NeakasaUnstoppableCycleSwitch,
)
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


# ---------------------------------------------------------------------------
# Remaining switch classes + turn on/off
# ---------------------------------------------------------------------------


async def test_auto_recovery_is_on() -> None:
    snap = NeakasaDeviceSnapshot(
        iot_id="iot-001",
        category_key="CatLitter",
        product_key="pk",
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
        auto_force_init=True,
        b_intrpt_range_det=False,
        stay_time=0,
        last_use=0,
        cat_list=[],
        record_list=[],
    )
    switch = NeakasaAutoRecoverySwitch(_mock_coord(snap), FAKE_DEVICE_INFO, "iot-001")
    switch.hass = MagicMock()
    assert switch.is_on is True
    assert switch.state == "on"
    assert switch.translation_key == "auto_recovery"


async def test_auto_recovery_turn_off() -> None:
    switch = NeakasaAutoRecoverySwitch(_mock_coord(), FAKE_DEVICE_INFO, "iot-001")
    switch.hass = MagicMock()
    switch.coordinator.set_property = AsyncMock()
    await switch.async_turn_off()
    switch.coordinator.set_property.assert_awaited_once()
    assert switch.coordinator.set_property.await_args.args[1:] == ("auto_force_init", 0)


async def test_auto_recovery_turn_on() -> None:
    switch = NeakasaAutoRecoverySwitch(_mock_coord(), FAKE_DEVICE_INFO, "iot-001")
    switch.hass = MagicMock()
    switch.coordinator.set_property = AsyncMock()
    await switch.async_turn_on()
    switch.coordinator.set_property.assert_awaited_once()
    assert switch.coordinator.set_property.await_args.args[1:] == ("auto_force_init", 1)


async def test_unstoppable_cycle_is_on() -> None:
    snap = NeakasaDeviceSnapshot(
        iot_id="iot-001",
        category_key="CatLitter",
        product_key="pk",
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
        b_intrpt_range_det=True,
        stay_time=0,
        last_use=0,
        cat_list=[],
        record_list=[],
    )
    switch = NeakasaUnstoppableCycleSwitch(
        _mock_coord(snap), FAKE_DEVICE_INFO, "iot-001"
    )
    switch.hass = MagicMock()
    assert switch.is_on is True
    assert switch.translation_key == "unstoppable_cycle"


async def test_unstoppable_cycle_turn_on() -> None:
    switch = NeakasaUnstoppableCycleSwitch(_mock_coord(), FAKE_DEVICE_INFO, "iot-001")
    switch.hass = MagicMock()
    switch.coordinator.set_property = AsyncMock()
    await switch.async_turn_on()
    switch.coordinator.set_property.assert_awaited_once()
    assert switch.coordinator.set_property.await_args.args[1:] == (
        "b_intrpt_range_det",
        1,
    )


async def test_unstoppable_cycle_turn_off() -> None:
    switch = NeakasaUnstoppableCycleSwitch(_mock_coord(), FAKE_DEVICE_INFO, "iot-001")
    switch.hass = MagicMock()
    switch.coordinator.set_property = AsyncMock()
    await switch.async_turn_off()
    switch.coordinator.set_property.assert_awaited_once()
    assert switch.coordinator.set_property.await_args.args[1:] == (
        "b_intrpt_range_det",
        0,
    )


async def test_missing_snapshot_switches_off() -> None:
    coord = _mock_coord(None)
    for cls in (
        NeakasaAutoBurySwitch,
        NeakasaAutoCleanSwitch,
        NeakasaAutoLevelSwitch,
        NeakasaChildLockSwitch,
        NeakasaSilentModeSwitch,
        NeakasaYoungCatModeSwitch,
        NeakasaAutoRecoverySwitch,
        NeakasaUnstoppableCycleSwitch,
    ):
        switch = cls(coord, FAKE_DEVICE_INFO, "iot-001")
        switch.hass = MagicMock()
        assert switch.is_on is False


async def test_turn_on_off_all_switches() -> None:
    coord = _mock_coord()
    coord.set_property = AsyncMock()
    cases: list[tuple[object, str]] = [
        (NeakasaAutoBurySwitch(coord, FAKE_DEVICE_INFO, "iot-001"), "auto_bury"),
        (NeakasaAutoCleanSwitch(coord, FAKE_DEVICE_INFO, "iot-001"), "clean_cfg"),
        (NeakasaAutoLevelSwitch(coord, FAKE_DEVICE_INFO, "iot-001"), "auto_level"),
        (NeakasaChildLockSwitch(coord, FAKE_DEVICE_INFO, "iot-001"), "child_lock"),
        (NeakasaSilentModeSwitch(coord, FAKE_DEVICE_INFO, "iot-001"), "silent_mode"),
        (
            NeakasaYoungCatModeSwitch(coord, FAKE_DEVICE_INFO, "iot-001"),
            "young_cat_mode",
        ),
    ]
    for switch, _key in cases:
        await switch.async_turn_on()
        await switch.async_turn_off()
    assert coord.set_property.await_count == 12


async def test_auto_clean_set_active_without_snapshot() -> None:
    switch = NeakasaAutoCleanSwitch(_mock_coord(None), FAKE_DEVICE_INFO, "iot-001")
    switch.hass = MagicMock()
    switch.coordinator.set_property = AsyncMock()
    await switch._set_active(1)
    switch.coordinator.set_property.assert_not_awaited()


async def test_auto_clean_set_active_updates_cfg() -> None:
    switch = NeakasaAutoCleanSwitch(_mock_coord(), FAKE_DEVICE_INFO, "iot-001")
    switch.hass = MagicMock()
    switch.coordinator.set_property = AsyncMock()
    await switch._set_active(0)
    switch.coordinator.set_property.assert_awaited_once_with(
        "iot-001",
        "clean_cfg",
        {"active": 0, "cleanInterval": 23, "workTime": 10, "delayTime": 5},
    )


# ---------------------------------------------------------------------------
# Lifecycle methods
# ---------------------------------------------------------------------------


def _fake_platform_data() -> MagicMock:
    """Fake EntityPlatform.platform_data so async_write_ha_state can run."""
    platform_data = MagicMock()
    platform_data.platform_name = "switch"
    platform_data.domain = "switch"
    platform_data.platform_translations = {}
    platform_data.component_translations = {}
    platform_data.object_id_platform_translations = {}
    platform_data.object_id_component_translations = {}
    return platform_data


async def test_switch_lifecycle(hass: HomeAssistant) -> None:
    """Exercise lifecycle methods on every switch class."""
    switch_classes = [
        NeakasaAutoBurySwitch,
        NeakasaAutoCleanSwitch,
        NeakasaAutoLevelSwitch,
        NeakasaAutoRecoverySwitch,
        NeakasaChildLockSwitch,
        NeakasaSilentModeSwitch,
        NeakasaUnstoppableCycleSwitch,
        NeakasaYoungCatModeSwitch,
    ]
    for index, switch_cls in enumerate(switch_classes):
        switch = switch_cls(_mock_coord(), FAKE_DEVICE_INFO, "iot-001")
        switch.hass = hass
        switch.platform_data = _fake_platform_data()
        switch.entity_id = f"switch.neakasa_{index}"
        await switch.async_added_to_hass()
        switch._handle_coordinator_update()
        await switch.async_update()

        switch.entity_id = None
        await switch.async_update()


# ---------------------------------------------------------------------------
# Switch platform setup
# ---------------------------------------------------------------------------


async def test_switch_async_setup_entry(hass: HomeAssistant) -> None:
    """Test that setup registers all switches per device."""
    from custom_components.neakasa.const import DOMAIN
    from custom_components.neakasa.switch import async_setup_entry as switch_setup

    coordinator = MagicMock()
    coordinator.data = {"iot-001": FAKE_SNAPSHOT}
    coordinator.async_add_listener = MagicMock()

    config_entry = MagicMock()
    config_entry.runtime_data.coordinator = coordinator
    config_entry.async_on_unload = MagicMock()
    config_entry.domain = DOMAIN

    collected: list = []

    await switch_setup(hass, config_entry, collected.extend)

    assert len(collected) == 8
    assert any(isinstance(e, NeakasaAutoBurySwitch) for e in collected)
    assert any(isinstance(e, NeakasaUnstoppableCycleSwitch) for e in collected)

    second_snap = NeakasaDeviceSnapshot(
        iot_id="iot-002",
        category_key="CatLitter",
        product_key="pk",
        device_name="T2",
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
    coordinator.data = {"iot-001": FAKE_SNAPSHOT, "iot-002": second_snap}
    rediscover = coordinator.async_add_listener.call_args.args[0]
    rediscover()
    assert len(collected) == 16

    rediscover()
    assert len(collected) == 16


# ---------------------------------------------------------------------------
# Riko feed defaults switch (integration-local setting, no wire key)
# ---------------------------------------------------------------------------


def _pet_feeder_snapshot() -> MagicMock:
    """Minimum the platform needs to recognise a Riko device."""
    snap = MagicMock()
    snap.category_key = "petFeeder"
    snap.device_name = "Riko"
    snap.product_key = "a1ccEqBcaUD"
    return snap


async def test_feed_keep_defaults_seeded_off() -> None:
    """Without a toggle the state comes from the account option (off)."""
    coord = MagicMock()
    coord.feed_keep_as_new_defaults.return_value = False
    switch = NeakasaFeedKeepDefaultsSwitch(coord, FAKE_DEVICE_INFO, "riko-001")
    switch.hass = MagicMock()
    assert switch.is_on is False
    assert switch.state == "off"
    assert switch.translation_key == "feed_keep_as_new_defaults"
    assert switch.unique_id == "riko-001-feed_keep_as_new_defaults"


async def test_feed_keep_defaults_turn_on() -> None:
    """Turning the switch on stores the amounts a feed uses."""
    coord = MagicMock()
    coord.set_feed_keep_as_new_defaults = MagicMock()
    switch = NeakasaFeedKeepDefaultsSwitch(coord, FAKE_DEVICE_INFO, "riko-001")
    switch.hass = MagicMock()
    await switch.async_turn_on()
    coord.set_feed_keep_as_new_defaults.assert_called_once_with("riko-001", value=True)


async def test_feed_keep_defaults_turn_off() -> None:
    """Turning it off keeps the machine's defaults untouched."""
    coord = MagicMock()
    coord.set_feed_keep_as_new_defaults = MagicMock()
    switch = NeakasaFeedKeepDefaultsSwitch(coord, FAKE_DEVICE_INFO, "riko-001")
    switch.hass = MagicMock()
    await switch.async_turn_off()
    coord.set_feed_keep_as_new_defaults.assert_called_once_with("riko-001", value=False)


async def test_feed_keep_defaults_async_setup_entry(hass: HomeAssistant) -> None:
    """A Riko gets this switch only; cat devices keep their eight switches."""
    from custom_components.neakasa.const import DOMAIN
    from custom_components.neakasa.switch import async_setup_entry as switch_setup

    coordinator = MagicMock()
    coordinator.data = {"riko-001": _pet_feeder_snapshot()}
    coordinator.async_add_listener = MagicMock()

    config_entry = MagicMock()
    config_entry.runtime_data.coordinator = coordinator
    config_entry.async_on_unload = MagicMock()
    config_entry.domain = DOMAIN

    collected: list = []
    await switch_setup(hass, config_entry, collected.extend)

    assert len(collected) == 1
    assert isinstance(collected[0], NeakasaFeedKeepDefaultsSwitch)

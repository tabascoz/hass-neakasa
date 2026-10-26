"""Tests for button entities and platform setup."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from custom_components.neakasa.button import async_setup_entry
from custom_components.neakasa.button.clean import NeakasaCleanButton
from custom_components.neakasa.button.level import NeakasaLevelButton
from custom_components.neakasa.button.refresh_data import NeakasaRefreshDataButton
from custom_components.neakasa.coordinator import NeakasaDeviceSnapshot

FAKE_SNAPSHOT = NeakasaDeviceSnapshot(
    iot_id="iot-001",
    device_name="T1 Plus",
    category_key="CatLitter",
    product_key="a1nNMMJkLqG",
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

FAKE_DEVICE_INFO = {"identifiers": {("neakasa", "iot-001")}}


async def test_clean_button_press() -> None:
    coord = MagicMock()
    coord.invoke_service = AsyncMock()
    button = NeakasaCleanButton(coord, FAKE_DEVICE_INFO, "iot-001")
    button.hass = MagicMock()
    assert button.translation_key == "clean"

    await button.async_press()

    coord.invoke_service.assert_awaited_once_with("iot-001", "clean")


async def test_level_button_press() -> None:
    coord = MagicMock()
    coord.invoke_service = AsyncMock()
    button = NeakasaLevelButton(coord, FAKE_DEVICE_INFO, "iot-001")
    button.hass = MagicMock()
    assert button.translation_key == "level"

    await button.async_press()

    coord.invoke_service.assert_awaited_once_with("iot-001", "level")


def _fake_platform_data() -> MagicMock:
    """Fake EntityPlatform.platform_data so async_write_ha_state can run."""
    platform_data = MagicMock()
    platform_data.platform_name = "button"
    platform_data.domain = "button"
    platform_data.platform_translations = {}
    platform_data.component_translations = {}
    platform_data.object_id_platform_translations = {}
    platform_data.object_id_component_translations = {}
    return platform_data


async def test_button_lifecycle(hass) -> None:
    """Test coordinator update handler, async_update and async_added_to_hass."""
    coord = MagicMock()
    clean = NeakasaCleanButton(coord, FAKE_DEVICE_INFO, "iot-001")
    clean.hass = hass
    clean.platform_data = _fake_platform_data()
    clean.entity_id = "button.neakasa_clean"
    await clean.async_added_to_hass()
    assert coord.async_add_listener.called
    clean._handle_coordinator_update()
    await clean.async_update()
    clean.entity_id = None
    await clean.async_update()

    level = NeakasaLevelButton(coord, FAKE_DEVICE_INFO, "iot-001")
    level.hass = hass
    level.platform_data = _fake_platform_data()
    level.entity_id = "button.neakasa_level"
    await level.async_added_to_hass()
    level._handle_coordinator_update()
    await level.async_update()
    level.entity_id = None
    await level.async_update()


async def test_async_setup_entry(hass) -> None:
    """Setup registers the device buttons and the account button once."""
    from custom_components.neakasa.const import DOMAIN

    coordinator = MagicMock()
    coordinator.data = {"iot-001": FAKE_SNAPSHOT}
    coordinator.async_add_listener = MagicMock()

    config_entry = MagicMock()
    config_entry.runtime_data.coordinator = coordinator
    config_entry.async_on_unload = MagicMock()
    config_entry.domain = DOMAIN

    collected: list = []

    await async_setup_entry(hass, config_entry, collected.extend)

    assert len(collected) == 3  # clean, level and the account button
    assert any(isinstance(e, NeakasaCleanButton) for e in collected)
    assert any(isinstance(e, NeakasaLevelButton) for e in collected)
    assert sum(isinstance(e, NeakasaRefreshDataButton) for e in collected) == 1
    assert config_entry.async_on_unload.called

    # A second discovery pass must not duplicate the entities
    rediscover = coordinator.async_add_listener.call_args.args[0]
    rediscover()
    # A second pass adds no account button: there is one account.
    assert len(collected) == 3

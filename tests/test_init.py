"""Tests for __init__.py — integration setup/teardown."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from custom_components.neakasa import (
    DOMAIN,
    PLATFORMS,
    _async_update_listener,
    _current_identifiers,
    _prune_devices_this_entry_no_longer_describes,
    async_migrate_entry,
    async_remove_config_entry_device,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.neakasa.log_redact import device_label


async def test_platforms_present() -> None:
    """Verify we register all expected platforms."""
    for platform_name in ("sensor", "binary_sensor", "switch", "button"):
        assert any(p.value == platform_name for p in PLATFORMS), (
            f"Missing platform: {platform_name}"
        )


async def test_async_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_get_shared_api: MagicMock,
) -> None:
    """Test that setup_entry creates coordinator and forwards platforms."""
    with (
        patch(
            "custom_components.neakasa.NeakasaCoordinator",
            autospec=True,
        ) as mock_coord_cls,
        patch.object(hass.config_entries, "async_forward_entry_setups") as fwd,
    ):
        mock_coordinator = mock_coord_cls.return_value
        mock_coordinator.data = {}
        mock_coordinator.async_config_entry_first_refresh.return_value = None

        result = await async_setup_entry(hass, mock_config_entry)
        assert result is True
        mock_coordinator.async_config_entry_first_refresh.assert_awaited_once()
        fwd.assert_awaited_once()


async def test_async_setup_entry_assigns_runtime_data(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_get_shared_api: MagicMock,
) -> None:
    """Test that setup_entry stores coordinator in runtime_data."""
    mock_config_entry.runtime_data = MagicMock()
    with (
        patch(
            "custom_components.neakasa.NeakasaCoordinator",
            autospec=True,
        ) as mock_coord_cls,
        patch.object(hass.config_entries, "async_forward_entry_setups"),
    ):
        mock_coordinator = mock_coord_cls.return_value
        mock_coordinator.data = {}
        mock_coordinator.async_config_entry_first_refresh.return_value = None

        await async_setup_entry(hass, mock_config_entry)
        assert mock_config_entry.runtime_data.coordinator is mock_coordinator
        mock_config_entry.add_update_listener.assert_called_once_with(
            _async_update_listener
        )
        assert mock_config_entry.async_on_unload.called


async def test_async_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
) -> None:
    """Test that unload_entry unloads platforms and clears shared API."""
    with (
        patch.object(
            hass.config_entries, "async_unload_platforms", return_value=True
        ) as unload,
        patch("custom_components.neakasa.clear_shared_api") as clear_api,
    ):
        result = await async_unload_entry(hass, mock_config_entry)
        assert result is True
        unload.assert_awaited_once()
        clear_api.assert_called_once()


async def test_async_migrate_entry_v1() -> None:
    """Test migrating a V1 config entry to V2."""
    hass = MagicMock()
    hass.config_entries.async_update_entry = MagicMock()
    entry = MagicMock()
    entry.version = 1
    entry.entry_id = "entry-1"
    entry.data = {
        CONF_USERNAME: "User@Example.com",
        CONF_PASSWORD: "hunter2",
    }

    result = await async_migrate_entry(hass, entry)

    assert result is True
    hass.config_entries.async_update_entry.assert_called_once()
    call_kwargs = hass.config_entries.async_update_entry.call_args.kwargs
    assert call_kwargs["data"] == {
        CONF_USERNAME: "User@Example.com",
        CONF_PASSWORD: "hunter2",
    }
    assert call_kwargs["unique_id"] == "account:user@example.com"
    assert call_kwargs["version"] == 2


async def test_async_migrate_entry_v2_already() -> None:
    """Test that V2 entries are left untouched."""
    hass = MagicMock()
    hass.config_entries.async_update_entry = MagicMock()
    entry = MagicMock()
    entry.version = 2

    result = await async_migrate_entry(hass, entry)

    assert result is True
    hass.config_entries.async_update_entry.assert_not_called()


async def test_update_listener_reloads_entry() -> None:
    """Test that the update listener reloads the config entry."""
    hass = MagicMock()
    hass.config_entries.async_reload = AsyncMock()
    entry = MagicMock()
    entry.entry_id = "entry-1"

    await _async_update_listener(hass, entry)

    hass.config_entries.async_reload.assert_awaited_once_with("entry-1")


def _registry_device(identifiers: set[tuple[str, str]], entry: str) -> MagicMock:
    """A device entry as the registry would hand one over."""
    device = MagicMock()
    device.identifiers = identifiers
    device.config_entry_id = entry
    device.name = "Neakasa account"
    device.id = "device-" + ",".join(f"{kind}:{value}" for kind, value in identifiers)
    return device


def test_the_account_device_is_named_by_the_entry() -> None:
    """The identifiers this entry describes now come from the entry."""
    config_entry = MagicMock(entry_id="entry-1")
    coordinator = MagicMock()
    coordinator.data = {"iot-1": {}}
    assert _current_identifiers(config_entry, coordinator) == {
        (DOMAIN, "account:entry-1"),
        (DOMAIN, "iot-1"),
    }


def test_other_credentials_describe_the_same_account_device() -> None:
    """Reconfiguring to another Neakasa account changes no identifier."""
    first = MagicMock(entry_id="entry-1")
    first.data = {CONF_USERNAME: "tabascoz@gmail.com"}
    second = MagicMock(entry_id="entry-1")
    second.data = {CONF_USERNAME: "consultor.fcunha@gmail.com"}
    coordinator = MagicMock()
    coordinator.data = {"iot-1": {}}

    assert _current_identifiers(first, coordinator) == _current_identifiers(
        second, coordinator
    )
    for identifier in _current_identifiers(first, coordinator):
        assert "tabascoz" not in str(identifier)
        assert "consultor" not in str(identifier)


def test_a_previous_accounts_device_is_pruned() -> None:
    """Devices this entry made under other credentials are forgotten."""
    config_entry = MagicMock(entry_id="entry-1")
    coordinator = MagicMock()
    coordinator.data = {"iot-1": {}}
    registry = MagicMock()
    current_account = _registry_device({(DOMAIN, "account:entry-1")}, "entry-1")
    machine = _registry_device({(DOMAIN, "iot-1")}, "entry-1")
    stale_account = _registry_device(
        {(DOMAIN, "account:tabascoz@gmail.com")}, "entry-1"
    )
    with (
        patch(
            "custom_components.neakasa.get_device_registry",
            return_value=registry,
        ),
        patch(
            "custom_components.neakasa.async_entries_for_config_entry",
            return_value=[machine, current_account, stale_account],
        ) as listed,
    ):
        _prune_devices_this_entry_no_longer_describes(
            MagicMock(), config_entry, coordinator
        )

    listed.assert_called_once_with(registry, "entry-1")
    removed = [call.args[0] for call in registry.async_remove_device.call_args_list]
    assert removed == [stale_account.id]


def test_the_prune_asks_only_for_this_entrys_devices() -> None:
    """The enumeration is scoped by entry, so no other entry is ever offered."""
    config_entry = MagicMock(entry_id="entry-1")
    coordinator = MagicMock()
    coordinator.data = {}
    registry = MagicMock()
    with (
        patch(
            "custom_components.neakasa.get_device_registry",
            return_value=registry,
        ),
        patch(
            "custom_components.neakasa.async_entries_for_config_entry",
            return_value=[],
        ) as listed,
    ):
        _prune_devices_this_entry_no_longer_describes(
            MagicMock(), config_entry, coordinator
        )

    listed.assert_called_once_with(registry, "entry-1")
    assert not registry.async_remove_device.call_args_list


async def test_the_removal_hook_accepts_only_stale_devices() -> None:
    """Home Assistant may drop the account device, never one in use."""
    config_entry = MagicMock(entry_id="entry-1")
    config_entry.runtime_data = MagicMock()
    config_entry.runtime_data.coordinator.data = {"iot-1": {}}
    stale = _registry_device({(DOMAIN, "account:tabascoz@gmail.com")}, "entry-1")
    current = _registry_device({(DOMAIN, "account:entry-1")}, "entry-1")

    assert await async_remove_config_entry_device(MagicMock(), config_entry, stale)
    assert not await async_remove_config_entry_device(
        MagicMock(), config_entry, current
    )


def test_a_forgotten_machine_is_named_by_its_label() -> None:
    """Which machine left stays readable; its serial does not reach the log."""
    config_entry = MagicMock(entry_id="entry-1")
    coordinator = MagicMock()
    coordinator.data = {"iot-1": {}}
    registry = MagicMock()
    stale_machine = _registry_device(
        {(DOMAIN, "4TQDtRLglcQJ5goDNlug000000")}, "entry-1"
    )
    with (
        patch("custom_components.neakasa.get_device_registry", return_value=registry),
        patch(
            "custom_components.neakasa.async_entries_for_config_entry",
            return_value=[stale_machine],
        ),
        patch("custom_components.neakasa._LOGGER.info") as info,
    ):
        _prune_devices_this_entry_no_longer_describes(
            MagicMock(), config_entry, coordinator
        )
    info.assert_called_once_with(
        "Forgetting device %s: this entry no longer describes it",
        device_label("4TQDtRLglcQJ5goDNlug000000"),
    )

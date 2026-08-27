"""Neakasa integration."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, cast

from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    Platform,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import NeakasaAPI
from .api_client import NeakasaApiClient
from .const import _LOGGER
from .coordinator import NeakasaCoordinator
from .data import NeakasaConfigEntry, NeakasaData

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.BUTTON,
]

# Global shared API clients and locks
_shared_clients: dict[str, NeakasaApiClient] = {}
_shared_locks: dict[str, asyncio.Lock] = {}


async def get_shared_api(
    hass: HomeAssistant, username: str, password: str
) -> NeakasaApiClient:
    """Get or create a shared API client for the given credentials."""
    credentials_key = f"{username}:{password}"

    if credentials_key not in _shared_locks:
        _shared_locks[credentials_key] = asyncio.Lock()

    async with _shared_locks[credentials_key]:
        if credentials_key in _shared_clients:
            client = _shared_clients[credentials_key]
            if client.connected:
                _LOGGER.debug("Reusing existing shared API client for %s", username)
                return client
            _LOGGER.debug("Clearing invalid API client for %s", username)
            del _shared_clients[credentials_key]

        session = async_get_clientsession(hass)
        api = NeakasaAPI(session, hass.async_add_executor_job)

        try:
            _LOGGER.debug("Authenticating new shared API client for %s", username)
            await api.connect(username, password)
            client = NeakasaApiClient(api)
            _shared_clients[credentials_key] = client
            _LOGGER.debug("Authenticated shared API client for %s", username)
            return client  # noqa: TRY300
        except Exception as e:
            _LOGGER.error("Failed to authenticate shared API for %s: %s", username, e)
            raise


def clear_shared_api(username: str, password: str) -> None:
    """Clear the shared API client for the given credentials."""
    credentials_key = f"{username}:{password}"
    _shared_clients.pop(credentials_key, None)
    _shared_locks.pop(credentials_key, None)


async def force_reconnect_api(
    hass: HomeAssistant, username: str, password: str
) -> NeakasaApiClient:
    """Force reconnection of the API client for the given credentials."""
    credentials_key = f"{username}:{password}"
    _shared_clients.pop(credentials_key, None)
    return await get_shared_api(hass, username, password)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """
    Migrate config entry from VERSION 1 → 2.

    V1 entries stored ``device_id``, ``friendly_name``, ``username``, ``password``
    in data and used the device IOT ID as the unique_id.  V2 keeps only
    ``username`` + ``password`` and uses ``account:{username}`` as the unique_id.
    """
    if config_entry.version == 1:
        _LOGGER.debug("Migrating config entry %s from V1 to V2", config_entry.entry_id)

        username = config_entry.data[CONF_USERNAME]
        password = config_entry.data[CONF_PASSWORD]

        new_data = {
            CONF_USERNAME: username,
            CONF_PASSWORD: password,
        }
        new_unique_id = f"account:{username.lower()}"

        hass.config_entries.async_update_entry(
            config_entry,
            data=new_data,
            unique_id=new_unique_id,
            version=2,
        )
        _LOGGER.debug("Migrated config entry %s to V2", config_entry.entry_id)
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Neakasa Integration from a config entry."""
    entry = cast("NeakasaConfigEntry", config_entry)

    coordinator = NeakasaCoordinator(hass, config_entry)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = NeakasaData(coordinator=coordinator)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def _async_update_listener(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Handle config options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    entry = cast("NeakasaConfigEntry", config_entry)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        coordinator = entry.runtime_data.coordinator
        clear_shared_api(coordinator.username, coordinator.password)

    return unload_ok

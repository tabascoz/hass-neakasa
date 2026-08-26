from __future__ import annotations

import asyncio
from typing import Dict, cast

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, _LOGGER
from .coordinator import NeakasaCoordinator
from .api import NeakasaAPI
from .data import NeakasaConfigEntry, NeakasaData

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.SWITCH, Platform.BUTTON]

# Global shared API instances and locks
_shared_apis: Dict[str, NeakasaAPI] = {}
_shared_locks: Dict[str, asyncio.Lock] = {}


async def get_shared_api(hass: HomeAssistant, username: str, password: str) -> NeakasaAPI:
    """Get or create a shared API instance for the given credentials."""
    credentials_key = f"{username}:{password}"
    
    if credentials_key not in _shared_locks:
        _shared_locks[credentials_key] = asyncio.Lock()
    
    async with _shared_locks[credentials_key]:
        if credentials_key in _shared_apis:
            api = _shared_apis[credentials_key]
            if api.connected and hasattr(api, '_iotToken') and api._iotToken:
                _LOGGER.debug("Reusing existing shared API instance for %s", username)
                return api
            _LOGGER.debug(
                "Clearing invalid API instance for %s (connected: %s, has_token: %s)",
                username, api.connected, hasattr(api, '_iotToken') and api._iotToken,
            )
                del _shared_apis[credentials_key]
        
        session = async_get_clientsession(hass)
        api = NeakasaAPI(session, hass.async_add_executor_job)
        
        try:
            _LOGGER.debug("Authenticating new shared API instance for %s", username)
            await api.connect(username, password)
            _shared_apis[credentials_key] = api
            _LOGGER.debug("Successfully created and authenticated shared API instance for %s", username)
            return api
        except Exception as e:
            _LOGGER.error("Failed to authenticate shared API for %s: %s", username, e)
            raise


def clear_shared_api(username: str, password: str) -> None:
    """Clear the shared API instance for the given credentials."""
    credentials_key = f"{username}:{password}"
    _shared_apis.pop(credentials_key, None)
    _shared_locks.pop(credentials_key, None)
async def force_reconnect_api(hass: HomeAssistant, username: str, password: str) -> NeakasaAPI:
    """Force reconnection of the API for the given credentials."""
    credentials_key = f"{username}:{password}"
    _shared_apis.pop(credentials_key, None)
    return await get_shared_api(hass, username, password)


def _count_entries_for_credentials(hass: HomeAssistant, username: str, password: str) -> int:
    """Return how many config entries share the given credentials."""
    count = 0
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.data.get("username") == username and entry.data.get("password") == password:
            count += 1
    return count


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Neakasa Integration from a config entry."""
    entry = cast(NeakasaConfigEntry, config_entry)

    coordinator = NeakasaCoordinator(hass, config_entry)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = NeakasaData(coordinator=coordinator)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Handle config options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    entry = cast(NeakasaConfigEntry, config_entry)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator = entry.runtime_data.coordinator
        remaining = _count_entries_for_credentials(hass, coordinator.username, coordinator.password)
        if remaining <= 1:
            clear_shared_api(coordinator.username, coordinator.password)
    return unload_ok


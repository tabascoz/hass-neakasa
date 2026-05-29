from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Dict

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, _LOGGER
from .coordinator import NeakasaCoordinator
from .api import NeakasaAPI

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.SWITCH, Platform.BUTTON]


@dataclass
class RuntimeData:
    """Class to hold your data."""

    coordinator: DataUpdateCoordinator
    cancel_update_listener: Callable


# Global shared API instances and locks
_shared_apis: Dict[str, NeakasaAPI] = {}
_shared_locks: Dict[str, asyncio.Lock] = {}


async def get_shared_api(hass: HomeAssistant, username: str, password: str) -> NeakasaAPI:
    """Get or create a shared API instance for the given credentials."""
    credentials_key = f"{username}:{password}"
    
    # Initialize lock for this credential set if it doesn't exist
    if credentials_key not in _shared_locks:
        _shared_locks[credentials_key] = asyncio.Lock()
    
    # Use lock to prevent concurrent authentication attempts
    async with _shared_locks[credentials_key]:
        # Check if we already have a valid API instance for these credentials
        if credentials_key in _shared_apis:
            api = _shared_apis[credentials_key]
            # If the API is connected and has valid tokens, return it
            if api.connected and hasattr(api, '_iotToken') and api._iotToken:
                _LOGGER.debug(f"Reusing existing shared API instance for {username}")
                return api
            else:
                # Clear invalid API instance
                _LOGGER.debug(f"Clearing invalid API instance for {username} (connected: {api.connected}, has_token: {hasattr(api, '_iotToken') and api._iotToken})")
                del _shared_apis[credentials_key]
        
        # Create new API instance
        session = async_get_clientsession(hass)
        api = NeakasaAPI(session, hass.async_add_executor_job)
        
        try:
            # Authenticate the API
            _LOGGER.debug(f"Authenticating new shared API instance for {username}")
            await api.connect(username, password)
            _shared_apis[credentials_key] = api
            _LOGGER.debug(f"Successfully created and authenticated shared API instance for {username}")
            return api
        except Exception as e:
            _LOGGER.error(f"Failed to authenticate shared API for {username}: {e}")
            raise


def clear_shared_api(username: str, password: str):
    """Clear the shared API instance for the given credentials."""
    credentials_key = f"{username}:{password}"
    if credentials_key in _shared_apis:
        del _shared_apis[credentials_key]
    if credentials_key in _shared_locks:
        del _shared_locks[credentials_key]


async def force_reconnect_api(hass: HomeAssistant, username: str, password: str) -> NeakasaAPI:
    """Force reconnection of the API for the given credentials."""
    credentials_key = f"{username}:{password}"
    
    # Clear existing instance
    if credentials_key in _shared_apis:
        del _shared_apis[credentials_key]
    
    # Get a fresh API instance
    return await get_shared_api(hass, username, password)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Example Integration from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    # Initialise the coordinator that manages data updates from your api.
    # This is defined in coordinator.py
    coordinator = NeakasaCoordinator(hass, config_entry)

    # Perform an initial data load from api.
    # async_config_entry_first_refresh() is special in that it does not log errors if it fails
    await coordinator.async_config_entry_first_refresh()

    # Test to see if api initialised correctly, else raise ConfigNotReady to make HA retry setup
    # The API connection is now handled by the shared API manager
    # We'll let the coordinator handle any connection issues during data updates

    # Initialise a listener for config flow options changes.
    # See config_flow for defining an options setting that shows up as configure on the integration.
    cancel_update_listener = config_entry.add_update_listener(_async_update_listener)

    # Add the coordinator and update listener to hass data to make
    hass.data[DOMAIN][config_entry.entry_id] = RuntimeData(
        coordinator, cancel_update_listener
    )

    # Setup platforms (based on the list of entity types in PLATFORMS defined above)
    # This calls the async_setup method in each of your entity type files.
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS);

    # Return true to denote a successful setup.
    return True


async def _async_update_listener(hass: HomeAssistant, config_entry):
    """Handle config options update."""
    # Reload the integration when the options change.
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # This is called when you remove your integration or shutdown HA.
    # If you have created any custom services, they need to be removed here too.

    # Remove the config options update listener
    hass.data[DOMAIN][config_entry.entry_id].cancel_update_listener()

    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    # Remove the config entry from the hass data object.
    if unload_ok:
        # Get coordinator info before removing the entry
        coordinator = hass.data[DOMAIN][config_entry.entry_id].coordinator
        username = coordinator.username
        password = coordinator.password
        
        # Remove the entry from hass data
        hass.data[DOMAIN].pop(config_entry.entry_id)
        
        # Check if any other devices are using the same credentials
        other_devices_using_creds = False
        for entry_id, runtime_data in hass.data[DOMAIN].items():
            other_coordinator = runtime_data.coordinator
            if (other_coordinator.username == username and 
                other_coordinator.password == password):
                other_devices_using_creds = True
                break
        
        # Only clear the shared API if no other devices are using these credentials
        if not other_devices_using_creds:
            clear_shared_api(username, password)

    # Return that unloading was successful.
    return unload_ok

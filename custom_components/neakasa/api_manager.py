"""Shared API client manager — extracted from __init__.py to avoid circular imports."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import NeakasaAPI
from .api_client import NeakasaApiClient
from .const import _LOGGER

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

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
                _LOGGER.debug("Reusing shared API client for %s", username)
                return client
            _LOGGER.debug("Clearing invalid API client for %s", username)
            del _shared_clients[credentials_key]

        session = async_get_clientsession(hass)
        api = NeakasaAPI(session, hass.async_add_executor_job)
        try:
            _LOGGER.debug("Authenticating shared API client for %s", username)
            await api.connect(username, password)
            client = NeakasaApiClient(api)
            _shared_clients[credentials_key] = client
            _LOGGER.debug("Authenticated shared API client for %s", username)
        except Exception:
            _LOGGER.error(
                "Failed to authenticate shared API for %s", username, exc_info=True
            )
            raise
        else:
            return client


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

"""Shared API client manager — extracted from __init__.py to avoid circular imports."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import NeakasaAPI
from .api_client import NeakasaApiClient
from .const import _LOGGER
from .log_redact import account_label

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_shared_clients: dict[str, NeakasaApiClient] = {}
_shared_locks: dict[str, asyncio.Lock] = {}
# Sign-ins this process has asked the account for, per username. A sign-in is
# the only call that hands the account's session to us instead of to whoever
# else holds it, and the Neakasa app notices exactly that: today its login
# page came back 3 seconds after our login at 10:14:37. Numbering every
# sign-in in the journal is what makes "the app lost its session" answerable
# from the log rather than from the phone, so the count and the reason are
# logged together. The account is named by `log_redact.account_label`, a hash
# of its login: the login is an email, and these lines are read on the box by
# anyone who tails the journal.
_session_mints: dict[str, int] = {}
# Creating the per-credentials lock must itself be serialised, otherwise two
# concurrent first-setup paths each get their own lock and authenticate twice.
_shared_registry_lock = asyncio.Lock()


async def get_shared_api(
    hass: HomeAssistant,
    username: str,
    password: str,
    cause: str = "coordinator asked for a client",
) -> NeakasaApiClient:
    """
    Get or create a shared API client for the given credentials.

    *cause* names why the caller wanted a client, so the sign-in line states
    the reason instead of leaving it to be inferred from the lines around it.
    """
    credentials_key = f"{username}:{password}"
    label = account_label(username)
    async with _shared_registry_lock:
        lock = _shared_locks.setdefault(credentials_key, asyncio.Lock())
    async with lock:
        if credentials_key in _shared_clients:
            client = _shared_clients[credentials_key]
            if client.connected:
                _LOGGER.debug("Reusing shared API client for %s", label)
                return client
            _LOGGER.debug("Clearing invalid client for %s: not connected", label)
            del _shared_clients[credentials_key]
            why = "the cached client was not connected"
        else:
            why = "nothing cached for these credentials yet"

        session = async_get_clientsession(hass)
        api = NeakasaAPI(session)
        try:
            # Counted before the call: a rejected sign-in still reached the
            # cloud and still vied for the account session, so it belongs in
            # the count just as a successful one does.
            _session_mints[username] = _session_mints.get(username, 0) + 1
            _LOGGER.info(
                "Account session minted #%d for %s: cause=%s (%s)",
                _session_mints[username],
                label,
                cause,
                why,
            )
            _LOGGER.debug("Authenticating shared API client for %s", label)
            await api.connect(username, password)
            client = NeakasaApiClient(api)
            _shared_clients[credentials_key] = client
            _LOGGER.debug("Authenticated shared API client for %s", label)
        except Exception:
            _LOGGER.error(
                "Failed to authenticate shared API for %s", label, exc_info=True
            )
            raise
        else:
            return client


def clear_shared_api(username: str, password: str) -> None:
    """
    Clear the shared API client for the given credentials.

    The per-credentials lock is kept so concurrent callers cannot each start
    their own authentication afterwards.
    """
    credentials_key = f"{username}:{password}"
    _shared_clients.pop(credentials_key, None)


async def force_reconnect_api(
    hass: HomeAssistant,
    username: str,
    password: str,
    cause: str = "forced reconnect",
) -> NeakasaApiClient:
    """
    Force reconnection of the API client for the given credentials.

    The whole client is dropped, so the next step is a sign-in; *cause* says
    what made the caller decide that, and the journal line repeats it.
    """
    credentials_key = f"{username}:{password}"
    _shared_clients.pop(credentials_key, None)
    return await get_shared_api(hass, username, password, cause)

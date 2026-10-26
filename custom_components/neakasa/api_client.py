"""API client facade with translated error hierarchy."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from .api import APIAuthError, APIConnectionError, NeakasaAPI
from .exceptions import (
    NeakasaApiClientAuthenticationError,
    NeakasaApiClientCommunicationError,
    NeakasaApiClientSessionExpiredError,
)

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


_EXPIRED_TOKEN_PHRASES: tuple[str, ...] = (
    "session",
    "expired",
    "auth",
    "tokeninvalid",
    "token is abnormal",
)


def _is_expired_token(message: str) -> bool:
    """
    Return whether *message* words a rejected token or session.

    The IoT gateway answers with ``request auth error`` and its session words,
    while the account web API behind ``/catbox/record`` answers with
    ``TokenInvalid`` followed by ``token is abnormal``. All of them mean the
    session we signed into is gone rather than the network having failed, so
    they must take the session-recovery path and not the communication ladder.
    """
    lowered = message.lower()
    return any(phrase in lowered for phrase in _EXPIRED_TOKEN_PHRASES)


@asynccontextmanager
async def _translate_errors() -> AsyncIterator[None]:
    """Map legacy API exceptions into the typed NeakasaApiClientError hierarchy."""
    try:
        yield
    except APIAuthError as err:
        message = str(err)
        if _is_expired_token(message):
            _LOGGER.info(
                "Error translation: APIAuthError -> SessionExpired"
                " (matched a token/auth phrase in: %r)",
                message,
            )
            raise NeakasaApiClientSessionExpiredError(message) from err
        _LOGGER.info(
            "Error translation: APIAuthError -> AuthenticationError"
            " (no token/auth phrase in: %r)",
            message,
        )
        raise NeakasaApiClientAuthenticationError(message) from err
    except APIConnectionError as err:
        message = str(err)
        if _is_expired_token(message):
            _LOGGER.info(
                "Error translation: APIConnectionError -> SessionExpired"
                " (matched a token/auth phrase in: %r)",
                message,
            )
            raise NeakasaApiClientSessionExpiredError(message) from err
        _LOGGER.info(
            "Error translation: APIConnectionError -> CommunicationError"
            " (no token/auth phrase in: %r)",
            message,
        )
        raise NeakasaApiClientCommunicationError(message) from err


class NeakasaApiClient:
    """Thin facade around :class:`NeakasaAPI` that translates legacy errors."""

    def __init__(self, api: NeakasaAPI) -> None:
        """Wrap an authenticated *api* instance."""
        self._api = api

    @property
    def connected(self) -> bool:
        """Return whether the underlying API is authenticated."""
        return self._api.connected

    async def connect(self, username: str, password: str) -> None:
        """Delegate connect call without translation (used during initial setup)."""
        await self._api.connect(username, password)

    async def refresh_session(self) -> None:
        """Renew the IoT session token without a full re-login, translating errors."""
        async with _translate_errors():
            await self._api.refresh_session()

    async def debug_invalidate_tokens(self) -> None:
        """Break the tokens this client holds, so the next scan must recover them."""
        await self._api.debug_invalidate_tokens()

    async def get_devices(self, page_no: int = 1, page_size: int = 20) -> Any:
        """Fetch devices, translating errors."""
        async with _translate_errors():
            return await self._api.get_devices(page_no, page_size)

    async def get_device_properties(self, iot_id: str) -> Any:
        """Fetch device properties, translating errors."""
        async with _translate_errors():
            return await self._api.get_device_properties(iot_id)

    async def set_device_properties(self, iot_id: str, items: dict[str, Any]) -> None:
        """Set device properties, translating errors."""
        async with _translate_errors():
            await self._api.set_device_properties(iot_id, items)

    async def clean_now(self, iot_id: str) -> None:
        """Trigger an immediate clean cycle."""
        async with _translate_errors():
            await self._api.clean_now(iot_id)

    async def sand_leveling(self, iot_id: str) -> None:
        """Trigger an immediate sand-leveling cycle."""
        async with _translate_errors():
            await self._api.sand_leveling(iot_id)

    async def get_records(self, device_name: str) -> Any:
        """Fetch toilet records, translating errors."""
        async with _translate_errors():
            return await self._api.get_records(device_name)

    async def get_statistics(self, device_name: str) -> Any:
        """Fetch statistics, translating errors."""
        async with _translate_errors():
            return await self._api.get_statistics(device_name)

    async def invoke_service(
        self, iot_id: str, identifier: str, args: dict[str, Any]
    ) -> None:
        """Invoke an arbitrary device service by wire identifier."""
        async with _translate_errors():
            await self._api.invoke_service(iot_id, identifier, args)

    async def get_product_list(self) -> Any:
        """Fetch the account's product schema (commands/properties)."""
        async with _translate_errors():
            return await self._api.get_product_list()

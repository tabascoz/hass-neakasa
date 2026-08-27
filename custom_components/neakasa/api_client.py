"""API client facade with translated error hierarchy."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from .api import APIAuthError, APIConnectionError, NeakasaAPI
from .exceptions import (
    NeakasaApiClientAuthenticationError,
    NeakasaApiClientCommunicationError,
    NeakasaApiClientSessionExpiredError,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


@asynccontextmanager
async def _translate_errors() -> AsyncIterator[None]:
    """Map legacy API exceptions into the typed NeakasaApiClientError hierarchy."""
    try:
        yield
    except APIAuthError as err:
        message = str(err)
        if "session" in message.lower() or "expired" in message.lower():
            raise NeakasaApiClientSessionExpiredError(message) from err
        raise NeakasaApiClientAuthenticationError(message) from err
    except APIConnectionError as err:
        message = str(err)
        if "auth" in message.lower():
            raise NeakasaApiClientSessionExpiredError(message) from err
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

    async def get_devices(self, page_no: int = 1, page_size: int = 20) -> Any:
        """Fetch devices, translating errors."""
        async with _translate_errors():
            return await self._api.getDevices(page_no, page_size)

    async def get_device_properties(self, iot_id: str) -> Any:
        """Fetch device properties, translating errors."""
        async with _translate_errors():
            return await self._api.getDeviceProperties(iot_id)

    async def set_device_properties(self, iot_id: str, items: dict[str, Any]) -> None:
        """Set device properties, translating errors."""
        async with _translate_errors():
            await self._api.setDeviceProperties(iot_id, items)

    async def clean_now(self, iot_id: str) -> None:
        """Trigger an immediate clean cycle."""
        async with _translate_errors():
            await self._api.cleanNow(iot_id)

    async def sand_leveling(self, iot_id: str) -> None:
        """Trigger an immediate sand-leveling cycle."""
        async with _translate_errors():
            await self._api.sandLeveling(iot_id)

    async def get_records(self, device_name: str) -> Any:
        """Fetch toilet records, translating errors."""
        async with _translate_errors():
            return await self._api.getRecords(device_name)

    async def get_statistics(self, device_name: str) -> Any:
        """Fetch statistics, translating errors."""
        async with _translate_errors():
            return await self._api.getStatistics(device_name)

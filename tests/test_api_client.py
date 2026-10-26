"""Tests for the NeakasaApiClient facade."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.neakasa.api import APIAuthError, APIConnectionError
from custom_components.neakasa.api_client import NeakasaApiClient, _translate_errors
from custom_components.neakasa.exceptions import (
    NeakasaApiClientAuthenticationError,
    NeakasaApiClientCommunicationError,
    NeakasaApiClientSessionExpiredError,
)


def _make_client() -> tuple[NeakasaApiClient, MagicMock]:
    api = MagicMock()
    api.connected = True
    return NeakasaApiClient(api), api


def test_connected_property() -> None:
    client, _api = _make_client()
    assert client.connected is True


async def test_connect_delegates() -> None:
    client, api = _make_client()
    api.connect = AsyncMock()
    await client.connect("u", "p")
    api.connect.assert_awaited_once_with("u", "p")


async def test_get_devices() -> None:
    client, api = _make_client()
    api.get_devices = AsyncMock(return_value=["d"])
    assert await client.get_devices() == ["d"]
    api.get_devices.assert_awaited_once_with(1, 20)


async def test_get_device_properties() -> None:
    client, api = _make_client()
    api.get_device_properties = AsyncMock(return_value={"x": 1})
    assert await client.get_device_properties("iot") == {"x": 1}
    api.get_device_properties.assert_awaited_once_with("iot")


async def test_set_device_properties() -> None:
    client, api = _make_client()
    api.set_device_properties = AsyncMock()
    await client.set_device_properties("iot", {"a": 1})
    api.set_device_properties.assert_awaited_once_with("iot", {"a": 1})


async def test_clean_now() -> None:
    client, api = _make_client()
    api.clean_now = AsyncMock()
    await client.clean_now("iot")
    api.clean_now.assert_awaited_once_with("iot")


async def test_sand_leveling() -> None:
    client, api = _make_client()
    api.sand_leveling = AsyncMock()
    await client.sand_leveling("iot")
    api.sand_leveling.assert_awaited_once_with("iot")


async def test_get_records() -> None:
    client, api = _make_client()
    api.get_records = AsyncMock(return_value={"r": []})
    assert await client.get_records("dev") == {"r": []}
    api.get_records.assert_awaited_once_with("dev")


async def test_get_statistics() -> None:
    client, api = _make_client()
    api.get_statistics = AsyncMock(return_value={"s": 1})
    assert await client.get_statistics("dev") == {"s": 1}
    api.get_statistics.assert_awaited_once_with("dev")


async def test_translate_success_passthrough() -> None:
    async with _translate_errors():
        assert True


async def test_translate_auth_to_session_expired() -> None:
    with pytest.raises(NeakasaApiClientSessionExpiredError):
        async with _translate_errors():
            raise APIAuthError("session token expired")


async def test_translate_auth_to_authentication() -> None:
    with pytest.raises(NeakasaApiClientAuthenticationError):
        async with _translate_errors():
            raise APIAuthError("invalid credentials")


async def test_translate_connection_auth_to_session_expired() -> None:
    with pytest.raises(NeakasaApiClientSessionExpiredError):
        async with _translate_errors():
            raise APIConnectionError("auth required")


async def test_translate_connection_to_communication() -> None:
    with pytest.raises(NeakasaApiClientCommunicationError):
        async with _translate_errors():
            raise APIConnectionError("network down")


async def test_translate_token_invalid_to_session_expired() -> None:
    """The account web API words a rejected token differently."""
    with pytest.raises(NeakasaApiClientSessionExpiredError):
        async with _translate_errors():
            raise APIConnectionError(
                "Error getting data: TokenInvalid\ufffatoken is abnormal"
            )

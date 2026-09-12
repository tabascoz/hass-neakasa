"""Fixtures for Neakasa tests."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from custom_components.neakasa.coordinator import (
    NeakasaDeviceSnapshot,
)
from custom_components.neakasa.exceptions import (
    NeakasaApiClientAuthenticationError,
    NeakasaApiClientCommunicationError,
    NeakasaApiClientSessionExpiredError,
)

# ---------------------------------------------------------------------------
# Mock the entire custom_components.neakasa module to avoid HA import issues
# ---------------------------------------------------------------------------

FAKE_DOMAIN = "neakasa"


def _coordinator_setup_side_effect(
    coordinator_mock: MagicMock,
) -> None:
    """Configure a mock coordinator to behave like the real one."""
    coordinator_mock.device_ids = ["iot-001"]
    coordinator_mock.device_snapshot.return_value = NeakasaDeviceSnapshot(
        iot_id="iot-001",
        device_name="T1 Plus",
        category_key="CatLitter",
        product_key="a1nNMMJkLqG",
        bin_full=False,
        clean_cfg={
            "active": True,
            "cleanInterval": 23,
            "workTime": 10,
            "delayTime": 5,
        },
        sand_level_state=2,
        sand_level_percent=65,
        bucket_status=0,
        room_of_bin=0,
        young_cat_mode=False,
        child_lock=False,
        auto_bury=True,
        auto_level=True,
        silent_mode=False,
        wifi_rssi=-55,
        auto_force_init=False,
        b_intrpt_range_det=True,
        stay_time=120,
        last_use=1730000000,
        cat_list=[
            {"name": "Whiskers", "id": "cat-1", "weight": 4500},
            {"name": "Mittens", "id": "cat-2", "weight": 3900},
        ],
        record_list=[],
    )


# ---------------------------------------------------------------------------
# Core fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _auto_enable_custom_integrations(
    enable_custom_integrations: None,
) -> None:
    """Auto-enable custom integrations in all tests."""


@pytest.fixture
def mock_aioclient() -> AsyncMock:
    """Return a mock aiohttp client session."""
    return AsyncMock()


@pytest.fixture
def mock_neakasa_api() -> Generator[MagicMock]:
    """Mock the NeakasaAPI class."""
    with patch("custom_components.neakasa.api.NeakasaAPI", autospec=True) as m:
        api = m.return_value
        api.connected = True
        api.get_devices.return_value = FAKE_DEVICES
        api.get_device_properties.return_value = FAKE_DEVICE_PROPERTIES
        api.set_device_properties = AsyncMock()
        api.clean_now = AsyncMock()
        api.sand_leveling = AsyncMock()
        api.get_records.return_value = FAKE_RECORDS
        api.connect = AsyncMock()
        yield m


@pytest.fixture
def mock_api_client(mock_neakasa_api: MagicMock) -> Generator[MagicMock]:
    """Mock the NeakasaApiClient class."""
    with patch("custom_components.neakasa.api_client.NeakasaApiClient") as m:
        client = m.return_value
        client.connected = True
        client.get_devices = AsyncMock(return_value=FAKE_DEVICES)
        client.get_device_properties = AsyncMock(return_value=FAKE_DEVICE_PROPERTIES)
        client.set_device_properties = AsyncMock()
        client.clean_now = AsyncMock()
        client.sand_leveling = AsyncMock()
        client.get_records = AsyncMock(return_value=FAKE_RECORDS)
        yield m


@pytest.fixture
def mock_get_shared_api(mock_api_client: MagicMock) -> Generator[AsyncMock]:
    """Mock get_shared_api to return a ready client."""
    with patch(
        "custom_components.neakasa.api_manager.get_shared_api",
        new_callable=AsyncMock,
    ) as m:
        m.return_value = mock_api_client()
        yield m


@pytest.fixture
def mock_coordinator(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_get_shared_api: MagicMock,
) -> Generator[MagicMock]:
    """Return a mock NeakasaCoordinator."""
    with patch(
        "custom_components.neakasa.coordinator.NeakasaCoordinator", autospec=True
    ) as m:
        coord = m.return_value
        _coordinator_setup_side_effect(coord)
        yield m


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MagicMock:
    """Return a mock config entry with valid credentials."""
    entry = MagicMock()
    entry.data = {
        CONF_USERNAME: "test@example.com",
        CONF_PASSWORD: "hunter2",
    }
    entry.options = {"scan_interval": 60, "stats_lookback_days": 7}
    entry.entry_id = "mock-entry-id"
    entry.unique_id = "account:test@example.com"
    entry.runtime_data = MagicMock()
    entry.title = "Neakasa (test@example.com)"
    return entry


# ---------------------------------------------------------------------------
# Fake API data
# ---------------------------------------------------------------------------

FAKE_DEVICES: list[dict[str, Any]] = [
    {
        "iotId": "iot-001",
        "deviceName": "T1 Plus",
        "categoryKey": "CatLitter",
        "productKey": "a1nNMMJkLqG",
        "productName": "T1 Plus",
        "status": "ONLINE",
    },
]

FAKE_DEVICE_PROPERTIES: dict[str, Any] = {
    "binFullWaitReset": {"value": 0},
    "cleanCfg": {
        "value": {
            "active": True,
            "cleanInterval": 23,
            "workTime": 10,
            "delayTime": 5,
        }
    },
    "youngCatMode": {"value": 0},
    "childLockOnOff": {"value": 0},
    "autoBury": {"value": 1},
    "autoLevel": {"value": 1},
    "silentMode": {"value": 0},
    "autoForceInit": {"value": 0},
    "bIntrptRangeDet": {"value": 1},
    "bucketStatus": {"value": 0},
    "room_of_bin": {"value": 0},
    "Sand": {"value": {"percent": 65, "level": 2}},
    "NetWorkStatus": {"value": {"WiFi_RSSI": -55}},
    "catLeft": {"value": {"stayTime": 120}, "time": 1730000000},
}

FAKE_RECORDS: dict[str, Any] = {
    "cat_list": [
        {"name": "Whiskers", "id": "cat-1", "weight": 4500},
        {"name": "Mittens", "id": "cat-2", "weight": 3900},
    ],
    "record_list": [],
}


# ---------------------------------------------------------------------------
# Error-causing overrides
# ---------------------------------------------------------------------------


@pytest.fixture
def make_auth_error_client(mock_api_client: MagicMock) -> MagicMock:
    """Make the mock API client raise an auth error on next call."""

    def _make() -> MagicMock:
        client = mock_api_client()
        client.get_devices.side_effect = NeakasaApiClientAuthenticationError("auth")
        return client

    return _make


@pytest.fixture
def make_comm_error_client(mock_api_client: MagicMock) -> MagicMock:
    """Make the mock API client raise a comm error on next call."""

    def _make() -> MagicMock:
        client = mock_api_client()
        client.get_devices.side_effect = NeakasaApiClientCommunicationError("comm")
        return client

    return _make


@pytest.fixture
def make_session_expired_client(mock_api_client: MagicMock) -> MagicMock:
    """Make the mock API client raise a session-expired error on next call."""

    def _make() -> MagicMock:
        client = mock_api_client()
        client.get_devices.side_effect = NeakasaApiClientSessionExpiredError("expired")
        return client

    return _make

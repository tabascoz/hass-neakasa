"""Tests for diagnostics support."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.diagnostics import REDACTED
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from custom_components.neakasa.diagnostics import (
    TO_REDACT,
    async_get_config_entry_diagnostics,
)


def test_to_redact_covers_identity_and_device_ids() -> None:
    """Test that every key carrying the account identity is redacted."""
    assert CONF_USERNAME in TO_REDACT
    assert CONF_PASSWORD in TO_REDACT
    assert "device_ids" in TO_REDACT
    assert "title" in TO_REDACT


def _make_entry() -> MagicMock:
    entry = MagicMock()
    entry.data = {CONF_USERNAME: "user@example.com", CONF_PASSWORD: "hunter2"}
    entry.title = "Neakasa (user@example.com)"
    entry.version = 2
    entry.domain = "neakasa"
    entry.options = {"scan_interval": 60}
    coordinator = MagicMock()
    coordinator.username = "user@example.com"
    coordinator.device_ids = ["iot-001"]
    coordinator.data = {}
    coordinator.async_get_device_schema = AsyncMock(
        return_value={"devices": {}, "products": {}}
    )
    entry.runtime_data.coordinator = coordinator
    return entry


async def test_async_get_config_entry_diagnostics() -> None:
    """Test that the account identity and device ids never reach diagnostics."""
    entry = _make_entry()
    result = await async_get_config_entry_diagnostics(None, entry)

    assert result["entry"]["title"] == REDACTED
    assert result["entry"]["version"] == 2
    assert result["entry"]["domain"] == "neakasa"
    assert result["entry"]["data"] == {CONF_USERNAME: REDACTED, CONF_PASSWORD: REDACTED}
    assert result["entry"]["options"] == {"scan_interval": 60}
    assert result["coordinator"]["username"] == REDACTED
    assert result["coordinator"]["device_ids"] == REDACTED
    assert result["coordinator"]["data_device_count"] == 0
    assert result["schema"] == {"devices": {}, "products": {}}


async def test_async_get_config_entry_diagnostics_no_data() -> None:
    """Test the device count when the coordinator has never polled."""
    entry = _make_entry()
    entry.runtime_data.coordinator.data = None
    result = await async_get_config_entry_diagnostics(None, entry)
    assert result["coordinator"]["data_device_count"] == 0

    entry.runtime_data.coordinator.data = {"iot-001": object()}
    result = await async_get_config_entry_diagnostics(None, entry)
    assert result["coordinator"]["data_device_count"] == 1

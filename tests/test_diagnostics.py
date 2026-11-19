"""Tests for diagnostics support."""

from __future__ import annotations

import json
from functools import partial
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.diagnostics import REDACTED
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from custom_components.neakasa.coordinator import NeakasaCoordinator
from custom_components.neakasa.diagnostics import (
    TO_REDACT,
    async_get_config_entry_diagnostics,
)
from custom_components.neakasa.log_redact import device_label

# The shape a real iotId has on the wire: 24 characters of the cloud's alphabet.
REAL_IOT_ID = "4TQDtRLglcQJ5goDNlug000000"


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
    coordinator.device_ids = [REAL_IOT_ID]
    coordinator.data = {}
    coordinator.async_get_device_schema = AsyncMock(return_value={"devices": {}})
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
    assert result["schema"] == {"devices": {}}


async def test_async_get_config_entry_diagnostics_no_data() -> None:
    """Test the device count when the coordinator has never polled."""
    entry = _make_entry()
    entry.runtime_data.coordinator.data = None
    result = await async_get_config_entry_diagnostics(None, entry)
    assert result["coordinator"]["data_device_count"] == 0

    entry.runtime_data.coordinator.data = {REAL_IOT_ID: object()}
    result = await async_get_config_entry_diagnostics(None, entry)
    assert result["coordinator"]["data_device_count"] == 1


def _build_the_real_schema(coordinator: MagicMock) -> AsyncMock:
    """
    Let *coordinator* build its schema the way the shipped coordinator does.

    Left to the mock this test would only read back a dict it chose itself, which
    says nothing about the keys the real code writes for a machine. The client is
    returned so the caller can see which cloud calls a download actually pays for.
    """
    client = AsyncMock()
    coordinator._get_client = AsyncMock(return_value=client)
    coordinator._get_properties = AsyncMock(
        return_value={
            "foodLvl": {"value": 2},
            "defFdCfg": {"value": {"food": 5, "water": 10, "mixMin": 1}},
        }
    )
    coordinator._pending_feed = {REAL_IOT_ID: {"food": 5, "water": 10}}
    coordinator._last_feed = {
        REAL_IOT_ID: {"args": {"food": 5, "water": 10}, "stored_defaults": False}
    }
    coordinator.feed_keep_as_new_defaults = MagicMock(return_value=False)
    coordinator.async_get_device_schema = partial(
        NeakasaCoordinator.async_get_device_schema, coordinator
    )
    return client


async def test_diagnostics_download_never_carries_a_raw_iot_id() -> None:
    """
    A shared file names a machine by its label, and by nothing that identifies it.

    `async_redact_data` replaces the value behind a key it recognises and copies
    every key out as it was, so the guard has to read the serialised download
    rather than trust the redaction list: what leaked here was a key, not a value.
    """
    entry = _make_entry()
    entry.runtime_data.coordinator.data = {
        REAL_IOT_ID: SimpleNamespace(
            category_key="petFeeder",
            product_key="a1ccEqBcaUD",
            default_food_g=5,
            default_water_ratio=2,
        )
    }
    client = _build_the_real_schema(entry.runtime_data.coordinator)

    result = await async_get_config_entry_diagnostics(None, entry)
    download = json.dumps(result)

    assert REAL_IOT_ID not in download
    assert "user@example.com" not in download
    assert "hunter2" not in download

    # The label is the word the journal uses, so file and log still line up, and
    # the schema keeps everything a reader needs to see about the machine.
    assert device_label(REAL_IOT_ID) in download
    device = result["schema"]["devices"][device_label(REAL_IOT_ID)]
    assert device["category_key"] == "petFeeder"
    assert device["product_key"] == "a1ccEqBcaUD"
    assert device["property_keys"] == ["defFdCfg", "foodLvl"]
    assert device["feed"]["last_feed"]["args"] == {"food": 5, "water": 10}

    # And the download no longer pays for a product call that cannot describe
    # a Neakasa machine, so it has no products block to leave empty either.
    assert "products" not in result["schema"]
    client.get_product_list.assert_not_called()

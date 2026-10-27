"""Tests for the Neakasa options flow."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.neakasa.const import DOMAIN


async def test_options_flow_show_form(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        unique_id="account:user@example.com",
        data={},
        options={},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    schema = result["data_schema"].schema
    assert "scan_interval" in schema
    assert "stats_lookback_days" in schema
    assert "debug_probe" in schema
    assert "feed_keep_as_new_defaults" in schema
    assert "account_session_window_minutes" not in schema
    assert "session_regain_policy" not in schema


async def test_options_flow_uses_existing_options(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        unique_id="account:user@example.com",
        data={},
        options={
            "scan_interval": 120,
            "stats_lookback_days": 14,
            "feed_keep_as_new_defaults": False,
            "account_session_window_minutes": 45,
            "session_regain_policy": "never",
            "debug_invoke_identifier": "",
            "debug_invoke_args_json": "{}",
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "scan_interval": 150,
            "stats_lookback_days": 21,
            "feed_keep_as_new_defaults": True,
            "debug_probe": "invoke_custom",
            "debug_invoke_identifier": "feedNow",
            "debug_invoke_args_json": '{"bStartFeed":1}',
        },
    )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"] == {
        "scan_interval": 150,
        "stats_lookback_days": 21,
        "feed_keep_as_new_defaults": True,
        "debug_probe": "invoke_custom",
        "debug_invoke_identifier": "feedNow",
        "debug_invoke_args_json": '{"bStartFeed":1}',
    }

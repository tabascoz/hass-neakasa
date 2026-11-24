"""Tests for the Neakasa options flow."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.neakasa.const import DOMAIN, OPTION_KEYS


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
    assert "feed_keep_as_new_defaults" in schema
    # Nothing ever read a lookback window: the record request asks for the seven
    # days api.py computes for itself, so the form stops promising one.
    assert "stats_lookback_days" not in schema
    assert "account_session_window_minutes" not in schema
    assert "session_regain_policy" not in schema
    # The temporary write harness is gone: a device write must never be one
    # settings save away again, so these keys stay out of the form.
    assert "debug_probe" not in schema
    assert "debug_invoke_identifier" not in schema
    assert "debug_invoke_args_json" not in schema

    # The form and the config-entry migration read one list of keys. This is what
    # keeps them from drifting again the way the retired keys above once did.
    offered = {key.schema if hasattr(key, "schema") else key for key in schema}
    assert offered == OPTION_KEYS


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
    # The debug keys this entry still carries are ones a pre-removal install
    # saved, and so is the lookback days a form offered before anyone read it:
    # the form must not offer them, and saving must drop them.
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "scan_interval": 150,
            "feed_keep_as_new_defaults": True,
        },
    )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"] == {
        "scan_interval": 150,
        "feed_keep_as_new_defaults": True,
    }

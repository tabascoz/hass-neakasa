"""Options flow for Neakasa."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlowResult, OptionsFlow
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from custom_components.neakasa.coordinator import (
    ACCOUNT_SESSION_WINDOW_DEFAULT_MINUTES,
    DEFAULT_SESSION_REGAIN_POLICY,
    SESSION_REGAIN_POLICIES,
)


class NeakasaOptionsFlow(OptionsFlow):
    """Handle options for Neakasa integration."""

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current_scan = self.config_entry.options.get("scan_interval", 60)
        current_lookback = self.config_entry.options.get("stats_lookback_days", 7)
        current_probe = self.config_entry.options.get("debug_probe", "none")
        current_identifier = self.config_entry.options.get(
            "debug_invoke_identifier", ""
        )
        current_args = self.config_entry.options.get("debug_invoke_args_json", "{}")
        current_keep_defaults = self.config_entry.options.get(
            "feed_keep_as_new_defaults", False
        )
        current_window = self.config_entry.options.get(
            "account_session_window_minutes",
            ACCOUNT_SESSION_WINDOW_DEFAULT_MINUTES,
        )
        current_policy = self.config_entry.options.get(
            "session_regain_policy", DEFAULT_SESSION_REGAIN_POLICY
        )

        schema = vol.Schema(
            {
                vol.Required(
                    "scan_interval",
                    default=current_scan,
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=10,
                        max=300,
                        step=5,
                        unit_of_measurement="seconds",
                        mode=NumberSelectorMode.BOX,
                    ),
                ),
                vol.Required(
                    "stats_lookback_days",
                    default=current_lookback,
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=1,
                        max=30,
                        step=1,
                        unit_of_measurement="days",
                        mode=NumberSelectorMode.BOX,
                    ),
                ),
                vol.Required(
                    "feed_keep_as_new_defaults",
                    default=current_keep_defaults,
                ): bool,
                vol.Required(
                    "account_session_window_minutes",
                    default=current_window,
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=5,
                        max=720,
                        step=5,
                        unit_of_measurement="minutes",
                        mode=NumberSelectorMode.BOX,
                    ),
                ),
                vol.Required(
                    "session_regain_policy",
                    default=current_policy,
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=list(SESSION_REGAIN_POLICIES),
                        mode=SelectSelectorMode.DROPDOWN,
                    ),
                ),
                vol.Required(
                    "debug_probe",
                    default=current_probe,
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            "none",
                            "set_fresh_mgr_on",
                            "set_fresh_mgr_off",
                            "set_deep_clean_on",
                            "set_deep_clean_off",
                            "invoke_custom",
                        ],
                        mode=SelectSelectorMode.DROPDOWN,
                    ),
                ),
                vol.Optional(
                    "debug_invoke_identifier", default=current_identifier
                ): str,
                vol.Optional("debug_invoke_args_json", default=current_args): str,
            },
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
        )

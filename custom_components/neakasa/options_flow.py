"""Options flow for Neakasa."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import OptionsFlow, ConfigEntry, ConfigFlowResult
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .const import DOMAIN, _LOGGER


class NeakasaOptionsFlow(OptionsFlow):
    """Handle options for Neakasa integration."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current_scan = self.config_entry.options.get("scan_interval", 60)
        current_lookback = self.config_entry.options.get("stats_lookback_days", 7)

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
            },
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
        )
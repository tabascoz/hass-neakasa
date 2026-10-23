"""Diagnostics support for neakasa."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import NeakasaConfigEntry

# `title` embeds the account login: "Neakasa (<username>)"
TO_REDACT: frozenset[str] = frozenset(
    {CONF_PASSWORD, CONF_USERNAME, "device_ids", "title"}
)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,  # noqa: ARG001
    entry: NeakasaConfigEntry,
) -> dict[str, object]:
    """Return diagnostics for a config entry with the account identity redacted."""
    coordinator = entry.runtime_data.coordinator
    return async_redact_data(
        {
            "entry": {
                "title": entry.title,
                "version": entry.version,
                "domain": entry.domain,
                "data": dict(entry.data),
                "options": dict(entry.options),
            },
            "coordinator": {
                "username": coordinator.username,
                "device_ids": coordinator.device_ids,
                "data_device_count": len(coordinator.data) if coordinator.data else 0,
            },
            "schema": await coordinator.async_get_device_schema(),
        },
        TO_REDACT,
    )

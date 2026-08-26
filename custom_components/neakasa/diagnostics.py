"""Diagnostics support for neakasa."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

if TYPE_CHECKING:
    from collections.abc import Mapping

    from homeassistant.core import HomeAssistant

    from .data import NeakasaConfigEntry

TO_REDACT: frozenset[str] = frozenset({CONF_PASSWORD, CONF_USERNAME})


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,  # noqa: ARG001
    entry: NeakasaConfigEntry,
) -> dict[str, object]:
    """Return diagnostics for a config entry."""
    redacted_data = cast(
        "Mapping[str, str]",
        async_redact_data(dict(entry.data), set(TO_REDACT)),
    )
    coordinator = entry.runtime_data.coordinator
    return {
        "entry": {
            "title": entry.title,
            "version": entry.version,
            "domain": entry.domain,
            "data": redacted_data,
            "options": dict(entry.options),
        },
        "device": {
            "iot_id": coordinator.deviceid,
            "name": coordinator.devicename,
            "connected": coordinator.data is not None,
        },
    }
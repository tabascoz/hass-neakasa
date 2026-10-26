"""Shared state-write guard: unchanged scans do not write entity state."""

from __future__ import annotations

from typing import Any

from .const import _LOGGER

_UNCHANGED: Any = object()


def write_state_if_changed(entity: Any, iot_id: str) -> None:
    """Write entity state, but only when the model for *iot_id* changed."""
    stamp = entity.coordinator.state_fingerprint(iot_id)
    if stamp is not None and stamp == getattr(entity, "_last_state_stamp", _UNCHANGED):
        return
    entity._last_state_stamp = stamp  # noqa: SLF001 - stored per entity instance
    _LOGGER.debug("Reported state for %s", getattr(entity, "entity_id", iot_id))
    entity.async_write_ha_state()

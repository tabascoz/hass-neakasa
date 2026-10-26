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


def account_records_refused(entity: Any) -> bool:
    """
    Whether the records this entity reads were refused by the account.

    An entity whose only source is the records uses this to say its value is
    as cached. The alternative - failing the whole update - would freeze the
    values read from the device in the same window, which are fresh.
    """
    return bool(entity.coordinator.records_refused)

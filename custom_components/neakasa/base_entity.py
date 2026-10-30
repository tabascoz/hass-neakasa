"""Shared state-write guard: unchanged scans do not write entity state."""

from __future__ import annotations

from typing import Any

from .const import _LOGGER
from .log_redact import device_label, redact_entity_id

_UNCHANGED: Any = object()


def _reported_name(entity: Any, iot_id: str) -> str:
    """Return the entity this line names, with the machine's word removed."""
    entity_id = getattr(entity, "entity_id", None)
    if not entity_id:
        return device_label(iot_id)
    device_info = getattr(entity, "device_info", None)
    name = device_info.get("name", "") if isinstance(device_info, dict) else ""
    return redact_entity_id(entity_id, iot_id, name)


def write_state_if_changed(entity: Any, iot_id: str) -> None:
    """Write entity state, but only when the model for *iot_id* changed."""
    stamp = entity.coordinator.state_fingerprint(iot_id)
    if stamp is not None and stamp == getattr(entity, "_last_state_stamp", _UNCHANGED):
        return
    entity._last_state_stamp = stamp  # noqa: SLF001 - stored per entity instance
    _LOGGER.debug("Reported state for %s", _reported_name(entity, iot_id))
    entity.async_write_ha_state()

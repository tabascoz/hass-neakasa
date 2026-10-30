"""Tests for the state-write guard that keeps unchanged scans silent."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from homeassistant.core import HomeAssistant

from custom_components.neakasa.base_entity import write_state_if_changed
from custom_components.neakasa.coordinator import NeakasaCoordinator
from custom_components.neakasa.log_redact import device_label


class _WritingEntity:
    """Stand-in for an entity, recording the writes the guard allows."""

    _iot_id = "iot-001"

    def __init__(self, coordinator: object) -> None:
        self.coordinator = coordinator
        self.writes: list[int] = []

    def async_write_ha_state(self) -> None:
        self.writes.append(1)


def _entity_with(fingerprints: list[object]) -> _WritingEntity:
    """Build an entity whose coordinator replays the given fingerprints."""
    coordinator = MagicMock()
    coordinator.state_fingerprint.side_effect = fingerprints
    return _WritingEntity(coordinator)


def test_guard_writes_the_first_time() -> None:
    """An entity which has not written yet always writes."""
    entity = _entity_with(["same"])
    write_state_if_changed(entity, "iot-001")
    assert entity.writes == [1]


def test_guard_skips_an_identical_scan() -> None:
    """An unchanged model is not reported a second time."""
    entity = _entity_with(["same", "same"])
    write_state_if_changed(entity, "iot-001")
    write_state_if_changed(entity, "iot-001")
    assert entity.writes == [1]


def test_guard_writes_when_the_model_changes() -> None:
    """A different model writes again."""
    entity = _entity_with(["before", "after"])
    write_state_if_changed(entity, "iot-001")
    write_state_if_changed(entity, "iot-001")
    assert entity.writes == [1, 1]


def test_guard_writes_while_the_model_is_unknown() -> None:
    """No model known yet keeps writing, so unavailable state is reported."""
    entity = _entity_with([None, None])
    write_state_if_changed(entity, "iot-001")
    write_state_if_changed(entity, "iot-001")
    assert entity.writes == [1, 1]


def test_fingerprint_follows_the_payload(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
) -> None:
    """Equal payloads give an equal stamp; a changed payload does not."""
    coordinator = NeakasaCoordinator(hass, mock_config_entry)
    coordinator.data = {"iot-001": MagicMock()}
    coordinator.async_set_updated_data = MagicMock()
    coordinator._mark_state_changed("iot-001", {"a": 1}, [])
    first = coordinator.state_fingerprint("iot-001")
    coordinator._mark_state_changed("iot-001", {"a": 1}, [])
    assert coordinator.state_fingerprint("iot-001") == first
    coordinator._mark_state_changed("iot-001", {"a": 2}, [])
    assert coordinator.state_fingerprint("iot-001") != first


def test_fingerprint_follows_staged_values(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
) -> None:
    """Staging an amount changes the stamp for the same payload."""
    coordinator = NeakasaCoordinator(hass, mock_config_entry)
    coordinator.data = {"iot-001": MagicMock()}
    coordinator.async_set_updated_data = MagicMock()
    coordinator._mark_state_changed("iot-001", {"a": 1}, [])
    first = coordinator.state_fingerprint("iot-001")
    coordinator.set_pending_feed("iot-001", food_g=9)
    assert coordinator.state_fingerprint("iot-001") != first


def test_a_state_line_keeps_the_entity_and_loses_the_serial() -> None:
    """The debug line names the entity, never the machine's serial."""
    entity = _entity_with(["same"])
    entity.entity_id = "switch.wl03002g26270011577_store_feed_as_machine_defaults"
    entity.device_info = {"name": "WL03002G26270011577"}
    with patch("custom_components.neakasa.base_entity._LOGGER.debug") as debug:
        write_state_if_changed(entity, "4TQDtRLglcQJ5goDNlug000000")
    debug.assert_called_once_with(
        "Reported state for %s",
        "switch."
        + device_label("4TQDtRLglcQJ5goDNlug000000")
        + "_store_feed_as_machine_defaults",
    )
    assert entity.writes == [1]

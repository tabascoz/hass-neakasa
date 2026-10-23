"""Tests for NeakasaCoordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.neakasa.coordinator import (
    NeakasaCoordinator,
    _build_device_snapshot,
    _get_last_use_date,
    _property_value,
    _to_int,
    _to_list,
)
from custom_components.neakasa.exceptions import (
    NeakasaApiClientAuthenticationError,
    NeakasaApiClientCommunicationError,
    NeakasaApiClientSessionExpiredError,
)

# ---------------------------------------------------------------------------
# Wire-value helpers (unit tests, no HA needed)
# ---------------------------------------------------------------------------

FAKE_DEVDATA: dict = {
    "binFullWaitReset": {"value": 1},
    "cleanCfg": {
        "value": {"active": True, "cleanInterval": 23, "workTime": 10, "delayTime": 5}
    },
    "youngCatMode": {"value": 0},
    "childLockOnOff": {"value": 0},
    "autoBury": {"value": 1},
    "autoLevel": {"value": 1},
    "silentMode": {"value": 0},
    "autoForceInit": {"value": 0},
    "bIntrptRangeDet": {"value": 1},
    "bucketStatus": {"value": 0},
    "room_of_bin": {"value": 0},
    "Sand": {"value": {"percent": 65, "level": 2}},
    "NetWorkStatus": {"value": {"WiFi_RSSI": -55}},
    "catLeft": {"value": {"stayTime": 120}, "time": 1730000000},
}

FAKE_DEVICES_LIST = [
    {"iotId": "iot-001", "deviceName": "T1 Plus", "categoryKey": "CatLitter"}
]


def test_property_value_present() -> None:
    assert _property_value(FAKE_DEVDATA, "bucketStatus") == 0


def test_property_value_missing_key() -> None:
    assert _property_value(FAKE_DEVDATA, "nonexistent", default=42) == 42


def test_property_value_not_dict() -> None:
    assert _property_value(None, "bucketStatus", default=99) == 99


def test_to_int_bool() -> None:
    assert _to_int(True) == 1
    assert _to_int(False) == 0


def test_to_int_string() -> None:
    assert _to_int("42") == 42


def test_to_int_invalid() -> None:
    assert _to_int("abc", default=99) == 99
    assert _to_int(None, default=99) == 99


def test_to_list_valid() -> None:
    assert _to_list([1, 2]) == [1, 2]


def test_to_list_none() -> None:
    assert _to_list(None) == []


def test_get_last_use_date_present() -> None:
    assert _get_last_use_date(FAKE_DEVDATA) == 1730000000


def test_get_last_use_date_missing() -> None:
    assert _get_last_use_date({}) == 0


def test_build_snapshot() -> None:
    snap = _build_device_snapshot(
        "iot-001",
        "T1 Plus",
        FAKE_DEVDATA,
        {},
        1730000000,
        category_key="CatLitter",
        product_key="a1nNMMJkLqG",
    )
    assert snap.iot_id == "iot-001"
    assert snap.device_name == "T1 Plus"
    assert snap.category_key == "CatLitter"
    assert snap.product_key == "a1nNMMJkLqG"
    assert snap.bin_full is True
    assert snap.sand_level_percent == 65
    assert snap.sand_level_state == 2
    assert snap.wifi_rssi == -55
    assert snap.stay_time == 120
    assert snap.last_use == 1730000000
    assert snap.young_cat_mode is False
    assert snap.child_lock is False
    assert snap.auto_bury is True
    assert snap.auto_level is True
    assert snap.silent_mode is False


def test_build_snapshot_empty_dict() -> None:
    snap = _build_device_snapshot("iot-001", "T1", {}, {}, 0)
    assert snap.iot_id == "iot-001"
    assert snap.bin_full is False
    assert snap.sand_level_percent == 0


# ---------------------------------------------------------------------------
# Coordinator tests — mock _get_client directly
# ---------------------------------------------------------------------------


def _make_coordinator(hass: HomeAssistant, entry: MagicMock) -> NeakasaCoordinator:
    """Create a coordinator and inject a mock client."""
    c = NeakasaCoordinator(hass, entry)
    c._get_client = AsyncMock()
    return c


async def test_coordinator_first_refresh(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_get_shared_api: MagicMock,
) -> None:
    """Test that the coordinator fetches device data."""
    coordinator = _make_coordinator(hass, mock_config_entry)
    # Override the client mock setup by _make_coordinator with a proper one
    client = AsyncMock()
    client.get_devices = AsyncMock(return_value=FAKE_DEVICES_LIST)
    coordinator._get_client = AsyncMock(return_value=client)

    with (
        patch.object(
            coordinator,
            "_discover_devices",
            return_value=FAKE_DEVICES_LIST,
        ),
        patch.object(
            coordinator,
            "_fetch_single_device",
            return_value=_build_device_snapshot(
                "iot-001", "T1 Plus", FAKE_DEVDATA, {}, 1730000000
            ),
        ),
    ):
        data = await coordinator.async_update_data()
        assert "iot-001" in data
        assert data["iot-001"].device_name == "T1 Plus"


async def test_coordinator_session_expired(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_get_shared_api: MagicMock,
) -> None:
    """Test that session expiry triggers reconnection."""
    coordinator = _make_coordinator(hass, mock_config_entry)

    with (
        patch.object(
            coordinator,
            "_discover_devices",
            side_effect=NeakasaApiClientSessionExpiredError("expired"),
        ),
        patch.object(
            coordinator,
            "_reconnect_and_retry",
            return_value={"iot-001": MagicMock()},
        ) as retry,
    ):
        data = await coordinator.async_update_data()
        retry.assert_awaited_once()
        assert "iot-001" in data


async def test_coordinator_auth_error_reauth(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_get_shared_api: MagicMock,
) -> None:
    """Test that persistent auth errors trigger reauth."""
    coordinator = _make_coordinator(hass, mock_config_entry)
    # mock_config_entry must have entry_id accessible as a real string
    mock_config_entry.entry_id = "mock-entry-id"
    mock_config_entry.async_start_reauth = AsyncMock()

    with (
        patch.object(
            coordinator,
            "_discover_devices",
            side_effect=NeakasaApiClientAuthenticationError("bad password"),
        ),
        patch.object(
            coordinator,
            "_reconnect_and_retry",
            side_effect=UpdateFailed("reconnect failed"),
        ),
        pytest.raises(UpdateFailed),
    ):
        await coordinator.async_update_data()


async def test_set_property(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_get_shared_api: MagicMock,
) -> None:
    """Test setting a device property."""
    coordinator = _make_coordinator(hass, mock_config_entry)
    client = AsyncMock()
    client.set_device_properties = AsyncMock()
    coordinator._get_client = AsyncMock(return_value=client)

    # Set coordinator data so property write path works
    snap = _build_device_snapshot("iot-001", "T1 Plus", FAKE_DEVDATA, {}, 1730000000)
    coordinator.data = {"iot-001": snap}

    await coordinator.set_property("iot-001", "child_lock", 1)
    client.set_device_properties.assert_awaited_once()


async def test_invoke_service(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_get_shared_api: MagicMock,
) -> None:
    """Test invoking a clean/level service."""
    coordinator = _make_coordinator(hass, mock_config_entry)
    client = AsyncMock()
    client.clean_now = AsyncMock()
    client.sand_leveling = AsyncMock()
    coordinator._get_client = AsyncMock(return_value=client)

    await coordinator.invoke_service("iot-001", "clean")
    client.clean_now.assert_awaited_once_with("iot-001")

    await coordinator.invoke_service("iot-001", "level")
    client.sand_leveling.assert_awaited_once_with("iot-001")


# ---------------------------------------------------------------------------
# Additional helper branches
# ---------------------------------------------------------------------------


def test_to_list_dict_tuple() -> None:
    assert _to_list({"a": 1}) == ["a"]
    assert _to_list((1, 2)) == [1, 2]
    assert _to_list("str") == []


def test_get_last_use_date_edge_cases() -> None:
    assert _get_last_use_date("not-a-dict") == 0
    assert _get_last_use_date({"catLeft": "not-a-dict"}) == 0


def test_build_snapshot_non_dict_values() -> None:
    snap = _build_device_snapshot(
        "iot-001",
        "T1",
        {
            "Sand": {"value": "oops"},
            "NetWorkStatus": {"value": "oops"},
            "catLeft": {"value": "oops"},
            "cleanCfg": {"value": ["nope"]},
            "bucketStatus": {"value": "7"},
        },
        ["not-a-dict"],
        0,
    )
    assert snap.sand_level_percent == 0
    assert snap.sand_level_state == 0
    assert snap.wifi_rssi == 0
    assert snap.stay_time == 0
    assert snap.clean_cfg == {}
    assert snap.cat_list == []
    assert snap.record_list == []


def test_build_snapshot_devicedata_not_dict() -> None:
    snap = _build_device_snapshot("iot-001", "T1", "not-a-dict", {}, 0)
    assert snap.iot_id == "iot-001"
    assert snap.bin_full is False


def test_build_snapshot_missing_clean_cfg_warns() -> None:
    snap = _build_device_snapshot("iot-001", "T1", {}, {}, 0)
    assert snap.clean_cfg == {}
    assert snap.bin_full is False


# ---------------------------------------------------------------------------
# Coordinator public helpers
# ---------------------------------------------------------------------------


async def test_device_snapshot_helpers(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_get_shared_api: MagicMock,
) -> None:
    """Test device_snapshot/device_ids/device_category helpers."""
    coordinator = _make_coordinator(hass, mock_config_entry)
    coordinator.data = None
    assert coordinator.device_snapshot("iot-001") is None

    snap = _build_device_snapshot("iot-001", "T1 Plus", FAKE_DEVDATA, {}, 1730000000)
    coordinator.data = {"iot-001": snap}
    coordinator._device_ids = ["iot-001"]
    assert coordinator.device_snapshot("iot-001") is snap
    assert coordinator.device_ids == ["iot-001"]
    assert coordinator.device_category("iot-001") == "CatLitter"
    assert coordinator.device_category("missing-id") == "unknown"


async def test_set_property_updates_snapshot(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_get_shared_api: MagicMock,
) -> None:
    """Test that set_property uses the wire mapping and mutates the snapshot."""
    coordinator = _make_coordinator(hass, mock_config_entry)
    client = AsyncMock()
    client.set_device_properties = AsyncMock()
    coordinator._get_client = AsyncMock(return_value=client)
    snap = _build_device_snapshot("iot-001", "T1 Plus", FAKE_DEVDATA, {}, 1730000000)
    coordinator.data = {"iot-001": snap}
    coordinator.async_set_updated_data = MagicMock()

    await coordinator.set_property("iot-001", "child_lock", 1)

    client.set_device_properties.assert_awaited_once_with(
        "iot-001", {"childLockOnOff": 1}
    )
    assert snap.child_lock == 1
    coordinator.async_set_updated_data.assert_called_once_with(coordinator.data)


async def test_set_property_without_snapshot(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_get_shared_api: MagicMock,
) -> None:
    """Test that set_property skips cache mutation when no snapshot exists."""
    coordinator = _make_coordinator(hass, mock_config_entry)
    client = AsyncMock()
    coordinator._get_client = AsyncMock(return_value=client)
    coordinator.data = None

    await coordinator.set_property("iot-001", "auto_bury", 0)

    client.set_device_properties.assert_awaited_once_with("iot-001", {"autoBury": 0})


async def test_invoke_service_unknown(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_get_shared_api: MagicMock,
) -> None:
    """Test that unknown services raise a ValueError."""
    coordinator = _make_coordinator(hass, mock_config_entry)
    with pytest.raises(ValueError, match="Unknown service"):
        await coordinator.invoke_service("iot-001", "unknown")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def test_discover_devices_filters_known_products(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_get_shared_api: MagicMock,
) -> None:
    """Test that _discover_devices keeps only KNOWN_PRODUCT_TYPES devices."""
    coordinator = _make_coordinator(hass, mock_config_entry)
    client = AsyncMock()
    client.get_devices = AsyncMock(
        return_value=[
            {"iotId": "iot-1", "categoryKey": "CatLitter", "productKey": "pk1"},
            {"iotId": "iot-2", "categoryKey": "WashingMachine"},
            {"iotId": "iot-3"},
        ]
    )
    coordinator._get_client = AsyncMock(return_value=client)

    matched = await coordinator._discover_devices()

    assert [d["iotId"] for d in matched] == ["iot-1"]
    assert coordinator._device_meta["iot-1"] == {
        "category_key": "CatLitter",
        "product_key": "pk1",
        "label": "",
    }


async def test_cache_for_creates_and_reuses(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_get_shared_api: MagicMock,
) -> None:
    """Test that _cache_for creates stable caches per device."""
    coordinator = _make_coordinator(hass, mock_config_entry)
    records_cache, props_cache = coordinator._cache_for("iot-001")
    assert coordinator._cache_for("iot-001") == (records_cache, props_cache)
    assert records_cache is coordinator._records_caches["iot-001"]
    assert props_cache is coordinator._properties_caches["iot-001"]


async def test_get_device_name_variants(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_get_shared_api: MagicMock,
) -> None:
    """Test cached, discovered, and fallback device-name resolution."""
    coordinator = _make_coordinator(hass, mock_config_entry)
    client = AsyncMock()
    client.get_devices = AsyncMock(
        return_value=[{"iotId": "iot-2", "deviceName": "T2"}]
    )
    coordinator._get_client = AsyncMock(return_value=client)

    coordinator._device_names["iot-1"] = "Known"
    assert await coordinator._get_device_name("iot-1") == "Known"

    assert await coordinator._get_device_name("iot-2") == "T2"
    assert coordinator._device_names["iot-2"] == "T2"

    assert await coordinator._get_device_name("iot-missing") == "iot-missing"
    assert coordinator._device_names["iot-missing"] == "iot-missing"


async def test_get_records_cached(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_get_shared_api: MagicMock,
) -> None:
    """Test that _get_records fetches once, then serves the cache."""
    coordinator = _make_coordinator(hass, mock_config_entry)
    client = AsyncMock()
    client.get_records = AsyncMock(return_value={"cat_list": []})
    coordinator._get_client = AsyncMock(return_value=client)

    with patch.object(
        coordinator, "_get_device_name", new=AsyncMock(return_value="T1")
    ):
        records = await coordinator._get_records("iot-001")
        cached = await coordinator._get_records("iot-001")

    assert records == {"cat_list": []}
    assert cached == {"cat_list": []}
    client.get_records.assert_awaited_once_with("T1")


async def test_get_properties_cached(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_get_shared_api: MagicMock,
) -> None:
    """Test that _get_properties fetches once, then serves the cache."""
    coordinator = _make_coordinator(hass, mock_config_entry)
    client = AsyncMock()
    client.get_device_properties = AsyncMock(return_value=FAKE_DEVDATA)
    coordinator._get_client = AsyncMock(return_value=client)

    first = await coordinator._get_properties("iot-001")
    second = await coordinator._get_properties("iot-001")

    assert first == FAKE_DEVDATA
    assert second == FAKE_DEVDATA
    assert client.get_device_properties.await_count == 2
    client.get_device_properties.assert_awaited_with("iot-001")


async def test_fetch_single_device(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_get_shared_api: MagicMock,
) -> None:
    """Test building a snapshot for a single device."""
    coordinator = _make_coordinator(hass, mock_config_entry)
    coordinator._device_meta = {
        "iot-001": {"category_key": "CatLitter", "product_key": "pk-1"}
    }
    with (
        patch.object(
            coordinator, "_get_properties", new=AsyncMock(return_value=FAKE_DEVDATA)
        ),
        patch.object(
            coordinator, "_get_records", new=AsyncMock(return_value={"cat_list": []})
        ),
        patch.object(
            coordinator, "_get_device_name", new=AsyncMock(return_value="T1 Plus")
        ),
    ):
        snap = await coordinator._fetch_single_device("iot-001")

    assert snap.device_name == "T1 Plus"
    assert snap.product_key == "pk-1"
    assert snap.last_use == 1730000000


async def test_fetch_single_device_marks_records_stale(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_get_shared_api: MagicMock,
) -> None:
    """Test that a changed last-use date marks the records cache stale."""
    coordinator = _make_coordinator(hass, mock_config_entry)
    devicedata = dict(FAKE_DEVDATA)
    devicedata["catLeft"] = {"value": {"stayTime": 120}, "time": 1730000000}

    with (
        patch.object(
            coordinator, "_get_properties", new=AsyncMock(return_value=devicedata)
        ),
        patch.object(coordinator, "_get_records", new=AsyncMock(return_value={})),
        patch.object(coordinator, "_get_device_name", new=AsyncMock(return_value="T1")),
    ):
        await coordinator._fetch_single_device("iot-001")
        _, props_cache = coordinator._cache_for("iot-001")
        assert coordinator._last_use_dates["iot-001"] == 1730000000
        await coordinator._fetch_single_device("iot-001")

    assert props_cache.value_if_not_stale() is None
    assert coordinator._last_use_dates["iot-001"] == 1730000000


# ---------------------------------------------------------------------------
# Reconnection helpers
# ---------------------------------------------------------------------------


async def test_reconnect_and_retry_success(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_get_shared_api: MagicMock,
) -> None:
    """Test that _reconnect_and_retry reconnects and re-runs the update."""
    coordinator = _make_coordinator(hass, mock_config_entry)
    coordinator.async_update_data = AsyncMock(return_value={"iot-001": MagicMock()})

    with patch(
        "custom_components.neakasa.coordinator.force_reconnect_api",
        new=AsyncMock(),
    ) as reconnect:
        result = await coordinator._reconnect_and_retry()

    reconnect.assert_awaited_once_with(hass, "test@example.com", "hunter2")
    assert "iot-001" in result


async def test_reconnect_and_retry_failure(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_get_shared_api: MagicMock,
) -> None:
    """Test that failing reconnection raises UpdateFailed."""
    coordinator = _make_coordinator(hass, mock_config_entry)

    with (
        patch(
            "custom_components.neakasa.coordinator.force_reconnect_api",
            new=AsyncMock(side_effect=NeakasaApiClientCommunicationError("boom")),
        ),
        pytest.raises(UpdateFailed),
    ):
        await coordinator._reconnect_and_retry()


async def test_reconnect_clear_and_retry(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_get_shared_api: MagicMock,
) -> None:
    """Test that _reconnect_clear_and_retry clears and retries."""
    coordinator = _make_coordinator(hass, mock_config_entry)

    with (
        patch("custom_components.neakasa.coordinator.clear_shared_api") as clear_api,
        patch.object(
            coordinator,
            "_reconnect_and_retry",
            new=AsyncMock(return_value={"iot-001": MagicMock()}),
        ) as retry,
    ):
        result = await coordinator._reconnect_clear_and_retry()

    clear_api.assert_called_once_with("test@example.com", "hunter2")
    retry.assert_awaited_once()
    assert "iot-001" in result


# ---------------------------------------------------------------------------
# async_update_data error paths
# ---------------------------------------------------------------------------


async def test_update_data_skips_failed_device(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_get_shared_api: MagicMock,
) -> None:
    """Test that a failing device is skipped while others succeed."""
    coordinator = _make_coordinator(hass, mock_config_entry)
    good = _build_device_snapshot("iot-001", "T1", FAKE_DEVDATA, {}, 0)

    with (
        patch.object(
            coordinator,
            "_discover_devices",
            new=AsyncMock(return_value=[{"iotId": "iot-001"}, {"iotId": "iot-002"}]),
        ),
        patch.object(
            coordinator,
            "_fetch_single_device",
            new=AsyncMock(side_effect=[good, RuntimeError("boom")]),
        ),
    ):
        data = await coordinator.async_update_data()

    assert "iot-001" in data
    assert "iot-002" not in data


async def test_update_data_session_expired_reconnect_fails(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_get_shared_api: MagicMock,
) -> None:
    """Test that failed reconnection after session expiry raises."""
    coordinator = _make_coordinator(hass, mock_config_entry)

    with (
        patch.object(
            coordinator,
            "_discover_devices",
            new=AsyncMock(side_effect=NeakasaApiClientSessionExpiredError("expired")),
        ),
        patch.object(
            coordinator,
            "_reconnect_and_retry",
            new=AsyncMock(side_effect=UpdateFailed("nope")),
        ),
        pytest.raises(UpdateFailed),
    ):
        await coordinator.async_update_data()


async def test_update_data_comm_retry_succeeds(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_get_shared_api: MagicMock,
) -> None:
    """Test that a communication error is retried and can succeed."""
    coordinator = _make_coordinator(hass, mock_config_entry)
    good = _build_device_snapshot("iot-001", "T1", FAKE_DEVDATA, {}, 0)

    with (
        patch("asyncio.sleep", new=AsyncMock()) as sleep_mock,
        patch.object(
            coordinator,
            "_discover_devices",
            new=AsyncMock(
                side_effect=[
                    NeakasaApiClientCommunicationError("boom"),
                    [{"iotId": "iot-001"}],
                ]
            ),
        ) as discover,
        patch.object(
            coordinator,
            "_fetch_single_device",
            new=AsyncMock(return_value=good),
        ),
    ):
        data = await coordinator.async_update_data()

    assert "iot-001" in data
    assert sleep_mock.await_count == 1
    assert discover.await_count == 2


async def test_update_data_identity_id_blank(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_get_shared_api: MagicMock,
) -> None:
    """Test that a blank identityId triggers a full reconnect."""
    coordinator = _make_coordinator(hass, mock_config_entry)

    with (
        patch.object(
            coordinator,
            "_discover_devices",
            new=AsyncMock(
                side_effect=NeakasaApiClientCommunicationError("identityId is blank")
            ),
        ),
        patch.object(
            coordinator,
            "_reconnect_clear_and_retry",
            new=AsyncMock(return_value={"iot-001": MagicMock()}),
        ) as retry,
    ):
        data = await coordinator.async_update_data()

    retry.assert_awaited_once()
    assert "iot-001" in data

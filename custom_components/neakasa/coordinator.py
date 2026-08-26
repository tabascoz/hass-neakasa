from __future__ import annotations
from dataclasses import dataclass, field
from datetime import timedelta
import logging
from typing import Optional, Any, Awaitable, Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_FRIENDLY_NAME,
    CONF_USERNAME,
    CONF_PASSWORD,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from datetime import datetime

from .api_client import NeakasaApiClient
from .exceptions import (
    NeakasaApiClientAuthenticationError,
    NeakasaApiClientCommunicationError,
    NeakasaApiClientError,
    NeakasaApiClientSessionExpiredError,
)
from .value_cacher import ValueCacher
from .const import DOMAIN, _LOGGER

_clean_cfg_warning_logged = False

@dataclass
class NeakasaAPIData:
    """Class to hold api data."""

    binFullWaitReset: bool
    cleanCfg: dict[str, Any]
    sandLevelState: int
    sandLevelPercent: int
    bucketStatus: int
    room_of_bin: int
    youngCatMode: bool
    childLockOnOff: bool
    autoBury: bool
    autoLevel: bool
    silentMode: bool
    wifiRssi: int
    autoForceInit: bool
    bIntrptRangeDet: bool
    stayTime: int
    lastUse: int
    cat_list: list[object] = field(default_factory=list)
    record_list: list[object] = field(default_factory=list)


def _property_value(devicedata: Any, key: str, default: Any = None) -> Any:
    """Return ``devicedata[key]['value']`` or *default* when the property is absent.

    The Aliyun IoT gateway wraps every property as ``{"time": ..., "value": ...}``.
    Some firmware variants / device models do not publish every property (for example
    ``cleanCfg``), so this must never raise ``KeyError``.
    """
    if not isinstance(devicedata, dict):
        return default
    entry = devicedata.get(key)
    if not isinstance(entry, dict):
        return default
    return entry.get('value', default)


def _to_int(value: Any, default: int = 0) -> int:
    """Coerce a wire value to ``int``, returning *default* if that is impossible."""
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_list(value: Any) -> list[object]:
    """Coerce a wire value to a list, returning an empty list when unusable."""
    if isinstance(value, list):
        return value
    if value is None:
        return []
    if isinstance(value, (dict, tuple)):
        return list(value)
    return []


def _get_last_use_date(devicedata: Any) -> Any:
    """Return the ``catLeft`` timestamp used to invalidate the records cache."""
    if not isinstance(devicedata, dict):
        return 0
    cat_left = devicedata.get('catLeft')
    if not isinstance(cat_left, dict):
        return 0
    return cat_left.get('time', 0)


def _build_api_data(devicedata: Any, records: Any, new_last_use_date: Any) -> NeakasaAPIData:
    """Build :class:`NeakasaAPIData` without crashing on missing properties."""
    if not isinstance(devicedata, dict):
        devicedata = {}
    if not isinstance(records, dict):
        records = {}

    sand = _property_value(devicedata, 'Sand', {})
    if not isinstance(sand, dict):
        sand = {}
    network = _property_value(devicedata, 'NetWorkStatus', {})
    if not isinstance(network, dict):
        network = {}
    cat_left_value = _property_value(devicedata, 'catLeft', {})
    if not isinstance(cat_left_value, dict):
        cat_left_value = {}
    clean_cfg = _property_value(devicedata, 'cleanCfg', {})
    if not isinstance(clean_cfg, dict):
        clean_cfg = {}

    expected_keys = (
        'binFullWaitReset', 'cleanCfg', 'youngCatMode', 'childLockOnOff',
        'autoBury', 'autoLevel', 'silentMode', 'autoForceInit',
        'bIntrptRangeDet', 'Sand', 'NetWorkStatus', 'bucketStatus',
        'room_of_bin', 'catLeft',
    )
    missing_keys = [key for key in expected_keys if key not in devicedata]
    if missing_keys:
        _LOGGER.debug(
            "Neakasa device properties missing keys %s (available: %s)",
            missing_keys, list(devicedata.keys()),
        )

    global _clean_cfg_warning_logged
    if 'cleanCfg' in missing_keys and not _clean_cfg_warning_logged:
        _clean_cfg_warning_logged = True
        _LOGGER.warning(
            "Neakasa device did not report the 'cleanCfg' property; "
            "the auto-clean switch will be unavailable. Available properties: %s",
            list(devicedata.keys()),
        )

    return NeakasaAPIData(
        binFullWaitReset=_property_value(devicedata, 'binFullWaitReset', 0) == 1,  # -> Abfalleimer voll
        cleanCfg=clean_cfg,
        youngCatMode=_property_value(devicedata, 'youngCatMode', 0) == 1,  # -> Kätzchen Modus
        childLockOnOff=_property_value(devicedata, 'childLockOnOff', 0) == 1,  # -> Kindersicherung
        autoBury=_property_value(devicedata, 'autoBury', 0) == 1,  # -> automatische Abdeckung
        autoLevel=_property_value(devicedata, 'autoLevel', 0) == 1,  # -> automatische Nivellierung
        silentMode=_property_value(devicedata, 'silentMode', 0) == 1,  # -> Stiller Modus
        autoForceInit=_property_value(devicedata, 'autoForceInit', 0) == 1,  # -> automatische Wiederherstellung
        bIntrptRangeDet=_property_value(devicedata, 'bIntrptRangeDet', 0) == 1,  # -> Unaufhaltsamer Kreislauf
        sandLevelPercent=_to_int(sand.get('percent', 0)),  # -> Katzenstreu Prozent
        wifiRssi=_to_int(network.get('WiFi_RSSI', 0)),  # -> WLAN RSSI
        bucketStatus=_to_int(_property_value(devicedata, 'bucketStatus', 0)),  # -> Aktueller Status
        room_of_bin=_to_int(_property_value(devicedata, 'room_of_bin', 0)),  # -> Abfalleimer
        sandLevelState=_to_int(sand.get('level', 0)),  # -> Katzenstreu
        stayTime=_to_int(cat_left_value.get('stayTime', 0)),
        lastUse=new_last_use_date,
        cat_list=_to_list(records.get('cat_list')),
        record_list=_to_list(records.get('record_list')),
    )


class NeakasaCoordinator(DataUpdateCoordinator):
    """My coordinator."""

    data: NeakasaAPIData

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize coordinator."""

        # Set variables from values entered in config flow setup
        self.deviceid = config_entry.data[CONF_DEVICE_ID]
        self.devicename = config_entry.data[CONF_FRIENDLY_NAME]
        self.username = config_entry.data[CONF_USERNAME]
        self.password = config_entry.data[CONF_PASSWORD]

        self._deviceName = None
        self.lastUseDate = None

        self._recordsCache = ValueCacher(refresh_after=timedelta(minutes=30), discard_after=timedelta(hours=4))
        self._devicePropertiesCache = ValueCacher(refresh_after=timedelta(seconds=0), discard_after=timedelta(minutes=30))

        # Initialise DataUpdateCoordinator
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} ({config_entry.unique_id})",
            # Method to call on every update interval.
            update_method=self.async_update_data,
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(seconds=60),
        )

        # API will be obtained from the shared manager when needed
        self.api = None
        

    async def setProperty(self, key: str, value: Any):
        client = await self._get_client()
        await client.set_device_properties(self.deviceid, {key: value})
        #update data
        setattr(self.data, key, value)
        self.async_set_updated_data(self.data)

    async def invokeService(self, service: str):
        client = await self._get_client()
        match service:
            case 'clean':
                return await client.clean_now(self.deviceid)
            case 'level':
                return await client.sand_leveling(self.deviceid)
        raise Exception('cannot find service to invoke')

    async def _get_client(self) -> NeakasaApiClient:
        """Return the shared API client for this coordinator's credentials."""
        from . import get_shared_api
        return await get_shared_api(self.hass, self.username, self.password)

    async def _getDeviceName(self):
        if self._deviceName is not None:
            return self._deviceName

        """get deviceName by iotId"""
        client = await self._get_client()
        devices = await client.get_devices()
        devices = list(filter(lambda d: d['iotId'] == self.deviceid, devices))
        if len(devices) == 0:
            raise NeakasaApiClientCommunicationError("iotId not found in device list")
        deviceName = devices[0]['deviceName']
        self._deviceName = deviceName
        return deviceName

    async def _getRecords(self):
        async def fetch():
            deviceName = await self._getDeviceName()
            client = await self._get_client()
            return await client.get_records(deviceName)

        return await self._recordsCache.get_or_update(fetch)

    async def _getDeviceProperties(self):
        async def fetch():
            client = await self._get_client()
            return await client.get_device_properties(self.deviceid)

        return await self._devicePropertiesCache.get_or_update(fetch)

    async def async_update_data(self):
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            devicedata = await self._getDeviceProperties()
            newLastUseDate = _get_last_use_date(devicedata)

            if self.lastUseDate != newLastUseDate:
                self._recordsCache.mark_as_stale()

            self.lastUseDate = newLastUseDate

            records = await self._getRecords()
            return _build_api_data(devicedata, records, newLastUseDate)
        except NeakasaApiClientSessionExpiredError as err:
            _LOGGER.warning("Session expired for device %s, reconnecting silently: %s", self.devicename, err)
            try:
                from . import force_reconnect_api
                client = await force_reconnect_api(self.hass, self.username, self.password)
                _LOGGER.info("Successfully reconnected API for device %s", self.devicename)
                devicedata = await client.get_device_properties(self.deviceid)
                newLastUseDate = _get_last_use_date(devicedata)
                if self.lastUseDate != newLastUseDate:
                    self._recordsCache.mark_as_stale()
                self.lastUseDate = newLastUseDate
                records = await self._getRecords()
                return _build_api_data(devicedata, records, newLastUseDate)
            except Exception as reconnect_err:
                _LOGGER.error("Failed to reconnect after session expiry for device %s: %s", self.devicename, reconnect_err)
                raise UpdateFailed("Session expired and reconnection failed: %s" % err) from err
        except NeakasaApiClientAuthenticationError as err:
            _LOGGER.warning("Authentication error for device %s, attempting to reconnect: %s", self.devicename, err)
            try:
                from . import force_reconnect_api
                client = await force_reconnect_api(self.hass, self.username, self.password)
                _LOGGER.info("Successfully reconnected API for device %s", self.devicename)
                devicedata = await client.get_device_properties(self.deviceid)
                newLastUseDate = _get_last_use_date(devicedata)
                if self.lastUseDate != newLastUseDate:
                    self._recordsCache.mark_as_stale()
                self.lastUseDate = newLastUseDate
                records = await self._getRecords()
                return _build_api_data(devicedata, records, newLastUseDate)
            except Exception as reconnect_err:
                _LOGGER.error("Failed to reconnect API for device %s: %s", self.devicename, reconnect_err)
                raise UpdateFailed("Authentication failed and reconnection failed: %s" % err) from err
        except NeakasaApiClientCommunicationError as err:
            if "identityId is blank" in str(err):
                _LOGGER.debug("IdentityId error for device %s, attempting automatic reconnection", self.devicename)
                try:
                    from . import clear_shared_api, force_reconnect_api
                    clear_shared_api(self.username, self.password)
                    client = await force_reconnect_api(self.hass, self.username, self.password)
                    _LOGGER.debug("Successfully reconnected API for device %s", self.devicename)
                    devicedata = await client.get_device_properties(self.deviceid)
                    newLastUseDate = _get_last_use_date(devicedata)
                    if self.lastUseDate != newLastUseDate:
                        self._recordsCache.mark_as_stale()
                    self.lastUseDate = newLastUseDate
                    records = await self._getRecords()
                    return _build_api_data(devicedata, records, newLastUseDate)
                except Exception as reconnect_err:
                    _LOGGER.error("Failed to reconnect after identityId error for device %s: %s", self.devicename, reconnect_err)
                    raise UpdateFailed("IdentityId error and reconnection failed: %s" % err) from err
            _LOGGER.error("API connection error for device %s: %s", self.devicename, err)
            raise UpdateFailed("Communication error: %s" % err) from err

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

from .api import NeakasaAPI, APIAuthError, APIConnectionError
from .value_cacher import ValueCacher
from .const import DOMAIN, _LOGGER

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
        from . import get_shared_api
        api = await get_shared_api(self.hass, self.username, self.password)
        await api.setDeviceProperties(self.deviceid, {key: value})
        #update data
        setattr(self.data, key, value)
        self.async_set_updated_data(self.data)

    async def invokeService(self, service: str):
        from . import get_shared_api
        api = await get_shared_api(self.hass, self.username, self.password)
        match service:
            case 'clean':
                return await api.cleanNow(self.deviceid)
            case 'level':
                return await api.sandLeveling(self.deviceid)
        raise Exception('cannot find service to invoke')

    async def _getDeviceName(self):
        if self._deviceName is not None:
            return self._deviceName

        """get deviceName by iotId"""
        from . import get_shared_api
        api = await get_shared_api(self.hass, self.username, self.password)
        devices = await api.getDevices()
        devices = list(filter(lambda devices: devices['iotId'] == self.deviceid, devices))
        if(len(devices) == 0):
            raise APIConnectionError("iotId not found in device list")
        deviceName = devices[0]['deviceName']
        self._deviceName = deviceName
        return deviceName

    async def _getRecords(self):
        async def fetch():
            deviceName = await self._getDeviceName()
            from . import get_shared_api
            api = await get_shared_api(self.hass, self.username, self.password)
            return await api.getRecords(deviceName)

        return await self._recordsCache.get_or_update(fetch)

    async def _getDeviceProperties(self):
        async def fetch():
            from . import get_shared_api
            api = await get_shared_api(self.hass, self.username, self.password)
            return await api.getDeviceProperties(self.deviceid)

        return await self._devicePropertiesCache.get_or_update(fetch)

    async def async_update_data(self):
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            devicedata = await self._getDeviceProperties()
            
            newLastUseDate = devicedata['catLeft']['time']

            if self.lastUseDate != newLastUseDate:
                self._recordsCache.mark_as_stale()

            self.lastUseDate = newLastUseDate
            
            records = await self._getRecords()

            try:
                return NeakasaAPIData(
                    binFullWaitReset=devicedata['binFullWaitReset']['value'] == 1, #-> Abfalleimer voll
                    cleanCfg=devicedata['cleanCfg']['value'],
                    youngCatMode=devicedata['youngCatMode']['value'] == 1, #-> Kätzchen Modus
                    childLockOnOff=devicedata['childLockOnOff']['value'] == 1, #-> Kindersicherung
                    autoBury=devicedata['autoBury']['value'] == 1, #-> automatische Abdeckung
                    autoLevel=devicedata['autoLevel']['value'] == 1, #-> automatische Nivellierung
                    silentMode=devicedata['silentMode']['value'] == 1, #-> Stiller Modus
                    autoForceInit=devicedata['autoForceInit']['value'] == 1, #-> automatische Wiederherstellung
                    bIntrptRangeDet=devicedata['bIntrptRangeDet']['value'] == 1, #-> Unaufhaltsamer Kreislauf
                    sandLevelPercent=devicedata['Sand']['value']['percent'], #-> Katzenstreu Prozent
                    wifiRssi=devicedata['NetWorkStatus']['value']['WiFi_RSSI'], #-> WLAN RSSI
                    bucketStatus=devicedata['bucketStatus']['value'], #-> Aktueller Status [0=Leerlauf,2=Reinigung,3=Nivellierung]
                    room_of_bin=devicedata['room_of_bin']['value'], #-> Abfalleimer [2=nicht in Position,0=Normal]
                    sandLevelState=devicedata['Sand']['value']['level'], #-> Katzenstreu [0=Unzureichend,1=Mäßig,2=Ausreichend]
                    stayTime=devicedata['catLeft']['value'].get('stayTime', 0),
                    lastUse=newLastUseDate,

                    cat_list=records['cat_list'],
                    record_list=records['record_list']
                )
            except Exception as err:
                _LOGGER.error(err)
                # This will show entities as unavailable by raising UpdateFailed exception
                raise UpdateFailed(f"Got no data from api, please try to restart your litter box.") from err
        except APIAuthError as err:
            _LOGGER.warning(f"Authentication error for device {self.devicename}, attempting to reconnect: {err}")
            try:
                # Force reconnection of the API
                from . import force_reconnect_api
                api = await force_reconnect_api(self.hass, self.username, self.password)
                _LOGGER.info(f"Successfully reconnected API for device {self.devicename}")
                # Retry the data fetch after reconnection
                devicedata = await api.getDeviceProperties(self.deviceid)
                # Continue with the rest of the data processing...
                newLastUseDate = devicedata['catLeft']['time']
                if self.lastUseDate != newLastUseDate:
                    self._recordsCache.mark_as_stale()
                self.lastUseDate = newLastUseDate
                records = await self._getRecords()
                
                return NeakasaAPIData(
                    binFullWaitReset=devicedata['binFullWaitReset']['value'] == 1,
                    cleanCfg=devicedata['cleanCfg']['value'],
                    youngCatMode=devicedata['youngCatMode']['value'] == 1,
                    childLockOnOff=devicedata['childLockOnOff']['value'] == 1,
                    autoBury=devicedata['autoBury']['value'] == 1,
                    autoLevel=devicedata['autoLevel']['value'] == 1,
                    silentMode=devicedata['silentMode']['value'] == 1,
                    autoForceInit=devicedata['autoForceInit']['value'] == 1,
                    bIntrptRangeDet=devicedata['bIntrptRangeDet']['value'] == 1,
                    sandLevelPercent=devicedata['Sand']['value']['percent'],
                    wifiRssi=devicedata['NetWorkStatus']['value']['WiFi_RSSI'],
                    bucketStatus=devicedata['bucketStatus']['value'],
                    room_of_bin=devicedata['room_of_bin']['value'],
                    sandLevelState=devicedata['Sand']['value']['level'],
                    stayTime=devicedata['catLeft']['value'].get('stayTime', 0),
                    lastUse=newLastUseDate,
                    cat_list=records['cat_list'],
                    record_list=records['record_list']
                )
            except Exception as reconnect_err:
                _LOGGER.error(f"Failed to reconnect API for device {self.devicename}: {reconnect_err}")
                raise UpdateFailed(f"Authentication failed and reconnection failed: {err}") from err
        except APIConnectionError as err:
            # Check if this is an identityId error, which indicates authentication issues
            if "identityId is blank" in str(err):
                _LOGGER.debug(f"IdentityId error for device {self.devicename}, attempting automatic reconnection")
                try:
                    # Clear the shared API to force a fresh connection
                    from . import clear_shared_api, force_reconnect_api
                    clear_shared_api(self.username, self.password)
                    api = await force_reconnect_api(self.hass, self.username, self.password)
                    _LOGGER.debug(f"Successfully reconnected API for device {self.devicename}")
                    # Retry the data fetch after reconnection
                    devicedata = await api.getDeviceProperties(self.deviceid)
                    # Continue with the rest of the data processing...
                    newLastUseDate = devicedata['catLeft']['time']
                    if self.lastUseDate != newLastUseDate:
                        self._recordsCache.mark_as_stale()
                    self.lastUseDate = newLastUseDate
                    records = await self._getRecords()
                    
                    return NeakasaAPIData(
                        binFullWaitReset=devicedata['binFullWaitReset']['value'] == 1,
                        cleanCfg=devicedata['cleanCfg']['value'],
                        youngCatMode=devicedata['youngCatMode']['value'] == 1,
                        childLockOnOff=devicedata['childLockOnOff']['value'] == 1,
                        autoBury=devicedata['autoBury']['value'] == 1,
                        autoLevel=devicedata['autoLevel']['value'] == 1,
                        silentMode=devicedata['silentMode']['value'] == 1,
                        autoForceInit=devicedata['autoForceInit']['value'] == 1,
                        bIntrptRangeDet=devicedata['bIntrptRangeDet']['value'] == 1,
                        sandLevelPercent=devicedata['Sand']['value']['percent'],
                        wifiRssi=devicedata['NetWorkStatus']['value']['WiFi_RSSI'],
                        bucketStatus=devicedata['bucketStatus']['value'],
                        room_of_bin=devicedata['room_of_bin']['value'],
                        sandLevelState=devicedata['Sand']['value']['level'],
                        stayTime=devicedata['catLeft']['value'].get('stayTime', 0),
                        lastUse=newLastUseDate,
                        cat_list=records['cat_list'],
                        record_list=records['record_list']
                    )
                except Exception as reconnect_err:
                    _LOGGER.error(f"Failed to reconnect API after identityId error for device {self.devicename}: {reconnect_err}")
                    raise UpdateFailed(f"IdentityId error and reconnection failed: {err}") from err
            else:
                _LOGGER.error(f"API connection error for device {self.devicename}: {err}")
                raise UpdateFailed(err) from err

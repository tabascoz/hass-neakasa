"""Neakasa cloud API — async-native, zero Aliyun SDK dependencies."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from aiohttp import ClientError

from .api_encryption import APIEncryption
from .const import _LOGGER
from .iot_gateway import AliyunIoTClient, IoTConfig, IoTResponse

if TYPE_CHECKING:
    from aiohttp import ClientSession


class NeakasaAPI:
    """Async client for Neakasa's cloud API over Aliyun IoT Gateway."""

    def __init__(
        self,
        session: ClientSession,
        app_key: str = "32715650",
        app_secret: str = "698ee0ef531c3df2ddded87563643860",
        language: str = "en-US",
    ) -> None:
        self._app_key = app_key
        self._app_secret = app_secret
        self._language = language
        self._session = session
        self._encryption = APIEncryption()
        self.connected: bool = False

    async def connect(
        self, username: str, password: str, *, first_run: bool = True
    ) -> None:
        """Authenticate and populate internal tokens."""
        if not self.connected:
            await self._load_base_url_by_account(username)
            await self._load_auth_tokens(username, password)
            await self._load_region_data()
            vid = await self._get_vid()
            self._sid = await self._get_sid_by_vid(vid)
        try:
            self._iot_token = await self._get_iot_token_by_sid(self._sid)
            self.connected = True
        except APIAuthError:
            if first_run:
                await self.connect(username, password, first_run=False)
            else:
                raise

    # ------------------------------------------------------------------
    # Internal helpers (no Aliyun SDK — pure aiohttp + manual HMAC)
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_iot_response(resp: IoTResponse, pathname: str) -> dict[str, Any]:
        """Parse an IoT gateway response, raising with context on failure."""
        body_text: str | None = None
        try:
            body_text = resp.body.decode("utf-8")
            result: dict[str, Any] = json.loads(body_text)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            if resp.status_code != 200:
                raise APIConnectionError(
                    f"IoT gateway returned HTTP {resp.status_code} on "
                    f"{pathname} with non-JSON body"
                ) from exc
            raise APIConnectionError(
                f"Invalid JSON from {pathname}: {resp.body[:200]!r}"
            ) from exc
        return result

    async def _load_base_url_by_account(self, username: str) -> None:
        try:
            timestamp = str(int(time.time()))
            signature = base64.b64encode(
                hmac.new(
                    self._app_secret.encode(),
                    (self._app_key + timestamp).encode(),
                    hashlib.sha256,
                ).digest()
            ).decode("utf-8")

            _LOGGER.debug("Fetching base URL from global.genhigh.com")

            async with self._session.get(
                url="https://global.genhigh.com/global/baseurl/account",
                params={"account": hashlib.md5(username.encode()).hexdigest()},
                headers={
                    "Request-Id": signature,
                    "Appid": self._app_key,
                    "Timestamp": timestamp,
                    "Sign": signature,
                },
            ) as response:
                _LOGGER.debug(
                    "Base URL response - Status: %s, Content-Type: %s",
                    response.status,
                    response.content_type or "EMPTY",
                )

                if response.status != 200:
                    text = await response.text()
                    _LOGGER.error(
                        "Base URL failed with status %s: %s",
                        response.status,
                        text[:400],
                    )
                    raise APIConnectionError("Error connecting to api.")

                try:
                    response_json = await response.json(content_type=None)
                except Exception as e:
                    text = await response.text()
                    _LOGGER.error(
                        "Failed to parse base URL JSON: %s. Body: %s", e, text[:400]
                    )
                    raise APIConnectionError("Error connecting to api.") from e

                if response_json["code"] != 0:
                    raise APIAuthError("Error connecting to api. Invalid username.")
                self.baseurl = response_json["data"]["web"]
        except ClientError:
            raise APIConnectionError("Error connecting to api.")

    async def _load_auth_tokens(self, username: str, password: str) -> None:
        try:
            timestamp = str(int(time.time()))
            signature = base64.b64encode(
                hmac.new(
                    self._app_secret.encode(),
                    (self._app_key + timestamp).encode(),
                    hashlib.sha256,
                ).digest()
            ).decode("utf-8")

            async with self._session.post(
                url=self.baseurl + "/login/user",
                json={
                    "product_id": "a123nCqsrQm3vEbt",
                    "system": 1,
                    "system_version": "iOS18.5",
                    "system_number": "iPhone17,1",
                    "app_version": "2.3.6",
                    "account": username,
                    "type": 3,
                    "password": hashlib.md5(
                        hashlib.md5(password.encode()).hexdigest().encode()
                    ).hexdigest(),
                },
                headers={
                    "Request-Id": signature,
                    "Appid": self._app_key,
                    "Timestamp": timestamp,
                    "Sign": signature,
                },
            ) as response:
                _LOGGER.debug(
                    "Login response - Status: %s, Content-Type: %s",
                    response.status,
                    response.content_type or "EMPTY",
                )

                if response.status != 200:
                    text = await response.text()
                    _LOGGER.error(
                        "Login failed with status %s: %s",
                        response.status,
                        text[:500],
                    )
                    raise APIConnectionError("Error connecting to api.")

                try:
                    response_json = await response.json(content_type=None)
                except Exception as e:
                    text = await response.text()
                    _LOGGER.error(
                        "Failed to parse login JSON: %s. Body: %s", e, text[:500]
                    )
                    raise APIConnectionError("Error connecting to api.") from e

                if response_json["code"] != 0:
                    raise APIAuthError(
                        "Error connecting to api. Invalid username or password."
                    )
                self._ali_authentication_token = response_json["data"]["user_info"][
                    "ali_authentication_token"
                ]
                await self._encryption.decodeLoginToken(
                    response_json["data"]["login_token"]
                )
        except ClientError:
            raise APIConnectionError("Error connecting to api.")

    async def _load_region_data(self) -> None:
        """Load regional API Gateway endpoints (IoT → do_request path)."""
        cfg = IoTConfig(
            app_key=self._app_key,
            app_secret=self._app_secret,
            domain="cn-shanghai.api-iot.aliyuncs.com",
        )
        client = AliyunIoTClient(cfg, self._session)
        body = {
            "id": AliyunIoTClient.generate_nonce(),
            "version": "1.0",
            "request": {
                "apiVer": "1.0.2",
                "language": self._language,
            },
            "params": {
                "authCode": self._ali_authentication_token,
                "type": "THIRD_AUTHCODE",
            },
        }
        resp = await client.do_request("/living/account/region/get", body)
        data = self._parse_iot_response(resp, "/living/account/region/get")
        if data["code"] != 200:
            raise APIConnectionError("Error loading region data." + data["message"])
        self.oaApiGatewayEndpoint = data["data"]["oaApiGatewayEndpoint"]
        self.apiGatewayEndpoint = data["data"]["apiGatewayEndpoint"]

    async def _get_vid(self) -> str:
        """Obtain vid via the OA gateway (IoT → do_request_raw path)."""
        cfg = IoTConfig(
            app_key=self._app_key,
            app_secret=self._app_secret,
            domain=self.oaApiGatewayEndpoint,
        )
        client = AliyunIoTClient(cfg, self._session)
        params = {
            "request": {
                "context": {"appKey": self._app_key},
                "config": {"version": 0, "lastModify": 0},
                "device": {},
            }
        }
        resp = await client.do_request_raw("/api/prd/connect.json", None, params)
        data = self._parse_iot_response(resp, "/api/prd/connect.json")
        if data["success"] != "true":
            raise APIConnectionError("Error getting vid.")
        if data["data"]["successful"] != "true":
            raise APIConnectionError("Error getting vid: " + data["data"]["message"])
        return data["data"]["vid"]

    async def _get_sid_by_vid(self, vid: str) -> str:
        """Exchange vid for a session sid (IoT → do_request_raw path)."""
        cfg = IoTConfig(
            app_key=self._app_key,
            app_secret=self._app_secret,
            domain=self.oaApiGatewayEndpoint,
        )
        client = AliyunIoTClient(cfg, self._session)
        params = {
            "loginByOauthRequest": {
                "authCode": self._ali_authentication_token,
                "oauthPlateform": 23,
                "oauthAppKey": self._app_key,
                "riskControlInfo": {},
            }
        }
        resp = await client.do_request_raw(
            "/api/prd/loginbyoauth.json", {"Vid": vid}, params
        )
        data = self._parse_iot_response(resp, "/api/prd/loginbyoauth.json")
        if data["success"] != "true":
            raise APIAuthError("Error getting sid: " + data["errorMsg"])
        if data["data"]["successful"] != "true":
            raise APIAuthError("Error getting sid: " + data["data"]["message"])
        return data["data"]["data"]["loginSuccessResult"]["sid"]

    async def _get_iot_token_by_sid(self, sid: str) -> str:
        """Exchange sid for an IoT token (IoT → do_request path)."""
        cfg = IoTConfig(
            app_key=self._app_key,
            app_secret=self._app_secret,
            domain=self.apiGatewayEndpoint,
        )
        client = AliyunIoTClient(cfg, self._session)
        body = {
            "id": AliyunIoTClient.generate_nonce(),
            "version": "1.0",
            "request": {
                "apiVer": "1.0.4",
                "language": self._language,
            },
            "params": {
                "request": {
                    "authCode": sid,
                    "accountType": "OA_SESSION",
                    "appKey": self._app_key,
                }
            },
        }
        resp = await client.do_request("/account/createSessionByAuthCode", body)
        data = self._parse_iot_response(resp, "/account/createSessionByAuthCode")
        if data["code"] != 200:
            self.connected = False
            raise APIAuthError("Error getting iot token: " + data["message"])
        return data["data"]["iotToken"]

    # ------------------------------------------------------------------
    # IoT Gateway operations (all go through do_request)
    # ------------------------------------------------------------------

    async def _iot_request(
        self, api_ver: str, pathname: str, params: dict[str, Any]
    ) -> Any:
        """Internal helper: build + send + parse an IoT Gateway request."""
        if not self.connected:
            raise APIConnectionError("api not connected")
        cfg = IoTConfig(
            app_key=self._app_key,
            app_secret=self._app_secret,
            domain=self.apiGatewayEndpoint,
        )
        client = AliyunIoTClient(cfg, self._session)
        body: dict[str, Any] = {
            "id": AliyunIoTClient.generate_nonce(),
            "version": "1.0",
            "request": {
                "apiVer": api_ver,
                "language": self._language,
                "iotToken": self._iot_token,
            },
            "params": params,
        }
        resp = await client.do_request(pathname, body)
        data = self._parse_iot_response(resp, pathname)
        if data["code"] != 200:
            error_msg = data.get("message", "unknown error")
            # Check for specific authentication errors
            if "identityId is blank" in error_msg:
                _LOGGER.debug("IdentityId error detected, marking API as disconnected")
                self.connected = False
            # Diagnostic: log the full cloud response so we can distinguish
            # between token-expiry, rate-limiting, and other auth failures.
            _LOGGER.info(
                "IoT cloud error — path=%s code=%s message=%r data_keys=%s",
                pathname,
                data["code"],
                error_msg,
                list(data.keys()),
            )
            raise APIConnectionError(f"Error in {pathname}: {error_msg}")
        return data["data"]

    async def get_product_list(self) -> Any:
        """Fetch the product list for the account."""
        return await self._iot_request(
            "1.1.7",
            "/thing/productInfo/getByAppKey",
            {"productStatusEnv": "release"},
        )

    async def get_devices(self, page_no: int = 1, page_size: int = 20) -> Any:
        """Fetch bound devices from the account."""
        result = await self._iot_request(
            "1.0.8",
            "/uc/listBindingByAccount",
            {
                "pageSize": page_size,
                "thingType": "DEVICE",
                "nodeType": "DEVICE",
                "pageNo": page_no,
            },
        )
        return result["data"]

    async def get_device_properties(self, iot_id: str) -> Any:
        """Fetch live device properties from Aliyun IoT."""
        _LOGGER.debug("Getting device properties for iotId: %s", iot_id)
        _LOGGER.debug(
            "API connected: %s, iotToken present: %s",
            self.connected,
            bool(self._iot_token),
        )
        return await self._iot_request(
            "1.0.4",
            "/thing/properties/get",
            {"iotId": iot_id},
        )

    async def set_device_properties(self, iot_id: str, items: dict[str, Any]) -> None:
        """Write device properties via Aliyun IoT."""
        await self._iot_request(
            "1.0.4",
            "/thing/properties/set",
            {"items": items, "iotId": iot_id},
        )

    async def _invoke_service(
        self, iot_id: str, identifier: str, args: dict[str, Any]
    ) -> None:
        """Invoke a device service (clean, level, etc)."""
        await self._iot_request(
            "1.0.5",
            "/thing/service/invoke",
            {"args": args, "identifier": identifier, "iotId": iot_id},
        )

    async def clean_now(self, iot_id: str) -> None:
        """Trigger immediate cleaning."""
        await self._invoke_service(iot_id, "cleanNow", {"bStartClean": 1})

    async def sand_leveling(self, iot_id: str) -> None:
        """Trigger sand leveling."""
        await self._invoke_service(iot_id, "sandLeveling", {"bStartLeveling": 1})

    # ------------------------------------------------------------------
    # Neakasa web API (pure aiohttp — no Aliyun SDK)
    # ------------------------------------------------------------------

    async def _signed_get(self, url: str, params: dict[str, Any]) -> Any:
        """Internal: signed GET to the Neakasa web API."""
        try:
            timestamp = int(time.time())
            signature = base64.b64encode(
                hmac.new(
                    self._app_secret.encode(),
                    (self._app_key + str(timestamp)).encode(),
                    hashlib.sha256,
                ).digest()
            ).decode("utf-8")
            async with self._session.get(
                url=url,
                params=params,
                headers={
                    "Request-Id": signature,
                    "Token": str(await self._encryption.getToken()),
                    "Uid": self._encryption.uid,
                    "Accept-Language": "en",
                },
            ) as response:
                data = await response.json()
                if data["code"] != 0:
                    raise APIConnectionError("Error getting data: " + data["message"])
                return data["data"]
        except ClientError:
            raise APIConnectionError("Error connecting to api.")

    def _seven_days_ago(self, now_ts: int) -> int:
        return int(
            (datetime.fromtimestamp(now_ts, tz=UTC) - timedelta(days=7)).timestamp()
        )

    async def get_statistics(self, device_name: str) -> Any:
        """Fetch usage statistics for the last 7 days."""
        timestamp = int(time.time())
        return await self._signed_get(
            self.baseurl + "/catbox/toilet/statistics",
            {
                "user_id": self._encryption.userid,
                "device_name": device_name,
                "bind_status": 2,
                "start_time": self._seven_days_ago(timestamp),
                "end_time": timestamp,
            },
        )

    async def get_records(self, device_name: str) -> Any:
        """Fetch usage records for the last 7 days."""
        timestamp = int(time.time())
        return await self._signed_get(
            self.baseurl + "/catbox/record",
            {
                "user_id": self._encryption.userid,
                "device_name": device_name,
                "bind_status": 2,
                "start_time": self._seven_days_ago(timestamp),
                "end_time": timestamp,
            },
        )


class APIAuthError(Exception):
    """Exception class for auth error."""


class APIConnectionError(Exception):
    """Exception class for connection error."""

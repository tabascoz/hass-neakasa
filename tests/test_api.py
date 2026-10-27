"""Tests for the NeakasaAPI cloud client."""

from __future__ import annotations

from typing import Self
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import ClientError

from custom_components.neakasa.api import (
    APIAuthError,
    APIConnectionError,
    NeakasaAPI,
    _describe_fields,
)
from custom_components.neakasa.iot_gateway import IoTResponse


class _FakeJSONResponse:
    """Minimal aiohttp response used for the direct web HTTP calls."""

    def __init__(
        self,
        *,
        status: int = 200,
        json_data: dict | None = None,
        text_data: str = "",
        json_error: Exception | None = None,
    ) -> None:
        self.status = status
        self._json_data = json_data
        self._text = text_data
        self._json_error = json_error
        self.content_type = "application/json" if json_data else ""

    async def json(self, content_type: str | None = None) -> dict:  # noqa: ARG002
        if self._json_error is not None:
            raise self._json_error
        return self._json_data or {}

    async def text(self) -> str:
        return self._text

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False


def _make_api() -> NeakasaAPI:
    return NeakasaAPI(MagicMock())


def _set_encryption(api: NeakasaAPI) -> MagicMock:
    encryption = MagicMock()
    encryption.getToken = AsyncMock(return_value="enc-token")
    encryption.uid = "uid-1"
    encryption.userid = "user-1"
    api._encryption = encryption
    return encryption


@pytest.fixture
def mock_iot_client() -> MagicMock:
    """Patch AliyunIoTClient with async do_request/do_request_raw."""
    with patch("custom_components.neakasa.api.AliyunIoTClient") as iot_cls:
        instance = iot_cls.return_value
        instance.do_request = AsyncMock(
            return_value=IoTResponse(status_code=200, body=b"{}")
        )
        instance.do_request_raw = AsyncMock(
            return_value=IoTResponse(status_code=200, body=b"{}")
        )
        yield iot_cls


# ---------------------------------------------------------------------------
# _parse_iot_response
# ---------------------------------------------------------------------------


def test_parse_iot_response_valid() -> None:
    resp = IoTResponse(status_code=200, body=b'{"code":200,"data":{}}')
    assert NeakasaAPI._parse_iot_response(resp, "/path")["code"] == 200


def test_parse_iot_response_non_json_http_error() -> None:
    resp = IoTResponse(status_code=500, body=b"<html>error</html>")
    with pytest.raises(APIConnectionError):
        NeakasaAPI._parse_iot_response(resp, "/path")


def test_parse_iot_response_invalid_json() -> None:
    resp = IoTResponse(status_code=200, body=b"not json")
    with pytest.raises(APIConnectionError):
        NeakasaAPI._parse_iot_response(resp, "/path")


# ---------------------------------------------------------------------------
# connect
# ---------------------------------------------------------------------------


async def test_connect_happy_path() -> None:
    api = _make_api()
    with (
        patch.object(api, "_load_base_url_by_account", new=AsyncMock()) as base,
        patch.object(api, "_load_auth_tokens", new=AsyncMock()) as auth,
        patch.object(api, "_load_region_data", new=AsyncMock()) as region,
        patch.object(api, "_get_vid", new=AsyncMock(return_value="vid-1")),
        patch.object(api, "_get_sid_by_vid", new=AsyncMock(return_value="sid-1")),
        patch.object(
            api,
            "_get_iot_token_by_sid",
            new=AsyncMock(return_value="tok-1"),
        ) as token,
    ):
        await api.connect("user@example.com", "password")
    assert api.connected is True
    assert api._iot_token == "tok-1"
    base.assert_awaited_once_with("user@example.com")
    auth.assert_awaited_once_with("user@example.com", "password")
    region.assert_awaited_once()
    token.assert_awaited_once()


async def test_connect_already_connected() -> None:
    api = _make_api()
    api.connected = True
    api._sid = "old-sid"
    with (
        patch.object(api, "_load_base_url_by_account", new=AsyncMock()) as base,
        patch.object(
            api,
            "_get_iot_token_by_sid",
            new=AsyncMock(return_value="tok"),
        ) as token,
    ):
        await api.connect("user@example.com", "password")
    base.assert_not_awaited()
    token.assert_awaited_once_with("old-sid")


async def test_connect_auth_error_retries_once() -> None:
    api = _make_api()
    calls: list[str] = []

    async def failing_token(sid: str) -> str:
        calls.append(sid)
        if len(calls) == 1:
            raise APIAuthError("expired")
        return "tok-ok"

    with (
        patch.object(api, "_load_base_url_by_account", new=AsyncMock()),
        patch.object(api, "_load_auth_tokens", new=AsyncMock()),
        patch.object(api, "_load_region_data", new=AsyncMock()),
        patch.object(api, "_get_vid", new=AsyncMock(return_value="vid-1")),
        patch.object(api, "_get_sid_by_vid", new=AsyncMock(return_value="sid-1")),
        patch.object(api, "_get_iot_token_by_sid", new=failing_token),
    ):
        await api.connect("user@example.com", "password")
    assert api.connected is True
    assert len(calls) == 2


async def test_connect_auth_error_second_attempt_raises() -> None:
    api = _make_api()

    async def failing_token(sid: str) -> str:
        raise APIAuthError("expired")

    async def run_flow() -> None:
        with (
            patch.object(api, "_load_base_url_by_account", new=AsyncMock()),
            patch.object(api, "_load_auth_tokens", new=AsyncMock()),
            patch.object(api, "_load_region_data", new=AsyncMock()),
            patch.object(api, "_get_vid", new=AsyncMock(return_value="vid-1")),
            patch.object(api, "_get_sid_by_vid", new=AsyncMock(return_value="sid-1")),
            patch.object(api, "_get_iot_token_by_sid", new=failing_token),
        ):
            await api.connect("user@example.com", "password")

    with pytest.raises(APIAuthError):
        await run_flow()
    assert api.connected is False


# ---------------------------------------------------------------------------
# _load_base_url_by_account
# ---------------------------------------------------------------------------


async def test_load_base_url_happy() -> None:
    api = _make_api()
    api._session.get = MagicMock(
        return_value=_FakeJSONResponse(
            json_data={"code": 0, "data": {"web": "https://web.example.com"}}
        )
    )
    await api._load_base_url_by_account("user@example.com")
    assert api.baseurl == "https://web.example.com"


async def test_load_base_url_http_error() -> None:
    api = _make_api()
    api._session.get = MagicMock(
        return_value=_FakeJSONResponse(status=500, text_data="boom")
    )
    with pytest.raises(APIConnectionError):
        await api._load_base_url_by_account("user@example.com")


async def test_load_base_url_invalid_json() -> None:
    api = _make_api()
    api._session.get = MagicMock(
        return_value=_FakeJSONResponse(
            json_error=ValueError("bad json"), text_data="nope"
        )
    )
    with pytest.raises(APIConnectionError):
        await api._load_base_url_by_account("user@example.com")


async def test_load_base_url_wrong_code() -> None:
    api = _make_api()
    api._session.get = MagicMock(
        return_value=_FakeJSONResponse(json_data={"code": 500, "data": {}})
    )
    with pytest.raises(APIAuthError):
        await api._load_base_url_by_account("user@example.com")


async def test_load_base_url_client_error() -> None:
    api = _make_api()
    api._session.get = MagicMock(side_effect=ClientError("boom"))
    with pytest.raises(APIConnectionError):
        await api._load_base_url_by_account("user@example.com")


# ---------------------------------------------------------------------------
# _load_auth_tokens
# ---------------------------------------------------------------------------


def _login_payload() -> dict:
    return {
        "code": 0,
        "data": {
            "user_info": {"ali_authentication_token": "ali-token"},
            "login_token": "encrypted-login-token",
        },
    }


def test_field_names_reach_the_journal_without_the_values() -> None:
    """The instrument names the fields the cloud sent, never their contents."""
    assert _describe_fields(_login_payload()) == (
        "code data data.login_token data.user_info "
        "data.user_info.ali_authentication_token"
    )
    assert "ali-token" not in _describe_fields(_login_payload())
    assert "encrypted-login-token" not in _describe_fields(_login_payload())


async def test_the_login_answer_is_named_by_its_fields() -> None:
    """A sign-in publishes the shape of the answer it got back."""
    api = _make_api()
    api.baseurl = "https://web.example.com"
    api._encryption = MagicMock()
    api._encryption.decodeLoginToken = AsyncMock()
    api._session.post = MagicMock(
        return_value=_FakeJSONResponse(json_data=_login_payload())
    )
    with patch("custom_components.neakasa.api._LOGGER") as log:
        await api._load_auth_tokens("user@example.com", "password")
        log.info.assert_any_call("Login fields: %s", _describe_fields(_login_payload()))


async def test_load_auth_tokens_happy() -> None:
    api = _make_api()
    api.baseurl = "https://web.example.com"
    api._encryption = MagicMock()
    api._encryption.decodeLoginToken = AsyncMock()
    api._session.post = MagicMock(
        return_value=_FakeJSONResponse(json_data=_login_payload())
    )
    await api._load_auth_tokens("user@example.com", "password")
    assert api._ali_authentication_token == "ali-token"
    api._encryption.decodeLoginToken.assert_awaited_once_with("encrypted-login-token")


async def test_load_auth_tokens_http_error() -> None:
    api = _make_api()
    api.baseurl = "https://web.example.com"
    api._session.post = MagicMock(
        return_value=_FakeJSONResponse(status=500, text_data="boom")
    )
    with pytest.raises(APIConnectionError):
        await api._load_auth_tokens("user@example.com", "password")


async def test_load_auth_tokens_invalid_json() -> None:
    api = _make_api()
    api.baseurl = "https://web.example.com"
    api._session.post = MagicMock(
        return_value=_FakeJSONResponse(
            json_error=ValueError("bad json"), text_data="nope"
        )
    )
    with pytest.raises(APIConnectionError):
        await api._load_auth_tokens("user@example.com", "password")


async def test_load_auth_tokens_wrong_code() -> None:
    api = _make_api()
    api.baseurl = "https://web.example.com"
    payload = _login_payload()
    payload["code"] = 1
    api._session.post = MagicMock(return_value=_FakeJSONResponse(json_data=payload))
    with pytest.raises(APIAuthError):
        await api._load_auth_tokens("user@example.com", "password")


async def test_load_auth_tokens_client_error() -> None:
    api = _make_api()
    api.baseurl = "https://web.example.com"
    api._session.post = MagicMock(side_effect=ClientError("boom"))
    with pytest.raises(APIConnectionError):
        await api._load_auth_tokens("user@example.com", "password")


# ---------------------------------------------------------------------------
# Region / VID / SID / token exchanges (AliyunIoTClient paths)
# ---------------------------------------------------------------------------


async def test_load_region_data_happy(mock_iot_client) -> None:
    api = _make_api()
    api._ali_authentication_token = "ali-token"
    with patch.object(
        api,
        "_parse_iot_response",
        return_value={
            "code": 200,
            "data": {
                "oaApiGatewayEndpoint": "oa.example.com",
                "apiGatewayEndpoint": "api.example.com",
            },
        },
    ):
        await api._load_region_data()
    mock_iot_client.return_value.do_request.assert_awaited_once()
    assert api.oaApiGatewayEndpoint == "oa.example.com"
    assert api.apiGatewayEndpoint == "api.example.com"


async def test_load_region_data_error(mock_iot_client) -> None:
    api = _make_api()
    api._ali_authentication_token = "ali-token"
    with (
        patch.object(
            api, "_parse_iot_response", return_value={"code": 500, "message": "bad"}
        ),
        pytest.raises(APIConnectionError),
    ):
        await api._load_region_data()


async def test_get_vid_happy(mock_iot_client) -> None:
    api = _make_api()
    api.oaApiGatewayEndpoint = "oa.example.com"
    with patch.object(
        api,
        "_parse_iot_response",
        return_value={
            "success": "true",
            "data": {"successful": "true", "vid": "vid-xyz"},
        },
    ):
        assert await api._get_vid() == "vid-xyz"
    mock_iot_client.return_value.do_request_raw.assert_awaited_once()


async def test_get_vid_success_not_true(mock_iot_client) -> None:
    api = _make_api()
    api.oaApiGatewayEndpoint = "oa.example.com"
    with (
        patch.object(
            api, "_parse_iot_response", return_value={"success": "false", "data": {}}
        ),
        pytest.raises(APIConnectionError),
    ):
        await api._get_vid()


async def test_get_vid_successful_not_true(mock_iot_client) -> None:
    api = _make_api()
    api.oaApiGatewayEndpoint = "oa.example.com"
    with (
        patch.object(
            api,
            "_parse_iot_response",
            return_value={
                "success": "true",
                "data": {"successful": "false", "message": "bad"},
            },
        ),
        pytest.raises(APIConnectionError),
    ):
        await api._get_vid()


async def test_get_sid_by_vid_happy(mock_iot_client) -> None:
    api = _make_api()
    api.oaApiGatewayEndpoint = "oa.example.com"
    api._ali_authentication_token = "ali-token"
    with patch.object(
        api,
        "_parse_iot_response",
        return_value={
            "success": "true",
            "data": {
                "successful": "true",
                "data": {"loginSuccessResult": {"sid": "sid-1"}},
            },
        },
    ):
        assert await api._get_sid_by_vid("vid-1") == "sid-1"
    overrides = mock_iot_client.return_value.do_request_raw.await_args.args[1]
    assert overrides == {"Vid": "vid-1"}


async def test_get_sid_by_vid_error(mock_iot_client) -> None:
    api = _make_api()
    api.oaApiGatewayEndpoint = "oa.example.com"
    api._ali_authentication_token = "ali-token"
    with (
        patch.object(
            api,
            "_parse_iot_response",
            return_value={"success": "false", "errorMsg": "bad"},
        ),
        pytest.raises(APIAuthError),
    ):
        await api._get_sid_by_vid("vid-1")


async def test_get_sid_by_vid_successful_error(mock_iot_client) -> None:
    api = _make_api()
    api.oaApiGatewayEndpoint = "oa.example.com"
    api._ali_authentication_token = "ali-token"
    with (
        patch.object(
            api,
            "_parse_iot_response",
            return_value={
                "success": "true",
                "data": {"successful": "false", "message": "bad"},
            },
        ),
        pytest.raises(APIAuthError),
    ):
        await api._get_sid_by_vid("vid-1")


async def test_get_iot_token_by_sid_happy(mock_iot_client) -> None:
    api = _make_api()
    api.apiGatewayEndpoint = "api.example.com"
    with patch.object(
        api,
        "_parse_iot_response",
        return_value={"code": 200, "data": {"iotToken": "iot-tok"}},
    ):
        assert await api._get_iot_token_by_sid("sid-1") == "iot-tok"
    mock_iot_client.return_value.do_request.assert_awaited_once()


async def test_get_iot_token_by_sid_error(mock_iot_client) -> None:
    api = _make_api()
    api.apiGatewayEndpoint = "api.example.com"
    with (
        patch.object(
            api,
            "_parse_iot_response",
            return_value={"code": 500, "message": "bad"},
        ),
        pytest.raises(APIAuthError),
    ):
        await api._get_iot_token_by_sid("sid-1")
    assert api.connected is False


# ---------------------------------------------------------------------------
# IoT request operations
# ---------------------------------------------------------------------------


async def test_iot_request_not_connected() -> None:
    api = _make_api()
    api.connected = False
    with pytest.raises(APIConnectionError):
        await api._iot_request("1.0.4", "/thing/properties/get", {})


async def test_iot_request_happy(mock_iot_client) -> None:
    api = _make_api()
    api.connected = True
    api._iot_token = "my-iot-token"
    api.apiGatewayEndpoint = "api.example.com"
    with patch.object(
        api,
        "_parse_iot_response",
        return_value={"code": 200, "data": {"x": 1}},
    ):
        result = await api._iot_request(
            "1.0.4", "/thing/properties/get", {"iotId": "iot-001"}
        )
    assert result == {"x": 1}
    body = mock_iot_client.return_value.do_request.await_args.args[1]
    assert body["request"]["iotToken"] == "my-iot-token"
    assert body["params"] == {"iotId": "iot-001"}


async def test_iot_request_identity_id_blank(mock_iot_client) -> None:
    api = _make_api()
    api.connected = True
    api._iot_token = "tok"
    api.apiGatewayEndpoint = "api.example.com"
    with (
        patch.object(
            api,
            "_parse_iot_response",
            return_value={"code": 500, "message": "identityId is blank"},
        ),
        pytest.raises(APIConnectionError),
    ):
        await api._iot_request("1.0.4", "/thing/properties/get", {})
    assert api.connected is False


async def test_iot_request_generic_error(mock_iot_client) -> None:
    api = _make_api()
    api.connected = True
    api._iot_token = "tok"
    api.apiGatewayEndpoint = "api.example.com"
    with (
        patch.object(
            api,
            "_parse_iot_response",
            return_value={"code": 500, "message": "rate limited"},
        ),
        pytest.raises(APIConnectionError, match="rate limited"),
    ):
        await api._iot_request("1.0.4", "/thing/properties/get", {})


async def test_iot_request_identity_refresh_recovers(mock_iot_client) -> None:
    api = _make_api()
    api.connected = True
    api._sid = "sid-1"
    api._iot_token = "aged-token"
    api.apiGatewayEndpoint = "api.example.com"
    with (
        patch.object(
            api,
            "_parse_iot_response",
            side_effect=[
                {"code": 500, "message": "identityId is blank"},
                {"code": 200, "data": {"ok": 1}},
            ],
        ),
        patch.object(
            api, "_get_iot_token_by_sid", new=AsyncMock(return_value="fresh-token")
        ) as refresh,
    ):
        result = await api._iot_request("1.0.5", "/thing/service/invoke", {})
    assert result == {"ok": 1}
    refresh.assert_awaited_once_with("sid-1")
    assert api._iot_token == "fresh-token"
    assert api.connected is True


async def test_get_product_list() -> None:
    api = _make_api()
    with patch.object(
        api, "_iot_request", new=AsyncMock(return_value={"data": []})
    ) as req:
        assert await api.get_product_list() == {"data": []}
    req.assert_awaited_once_with(
        "1.1.7", "/thing/productInfo/getByAppKey", {"productStatusEnv": "release"}
    )


async def test_get_devices() -> None:
    api = _make_api()
    with patch.object(
        api,
        "_iot_request",
        new=AsyncMock(return_value={"data": [{"iotId": "iot-001"}]}),
    ) as req:
        result = await api.get_devices(2, 50)
    assert result == [{"iotId": "iot-001"}]
    req.assert_awaited_once_with(
        "1.0.8",
        "/uc/listBindingByAccount",
        {
            "pageSize": 50,
            "thingType": "DEVICE",
            "nodeType": "DEVICE",
            "pageNo": 2,
        },
    )


async def test_get_device_properties() -> None:
    api = _make_api()
    api._iot_token = "tok"
    with patch.object(
        api, "_iot_request", new=AsyncMock(return_value={"value": 1})
    ) as req:
        assert await api.get_device_properties("iot-001") == {"value": 1}
    req.assert_awaited_once_with("1.0.4", "/thing/properties/get", {"iotId": "iot-001"})


async def test_set_device_properties() -> None:
    api = _make_api()
    with patch.object(api, "_iot_request", new=AsyncMock()) as req:
        await api.set_device_properties("iot-001", {"autoBury": 1})
    req.assert_awaited_once_with(
        "1.0.4",
        "/thing/properties/set",
        {"items": {"autoBury": 1}, "iotId": "iot-001"},
    )


async def test_invoke_service() -> None:
    api = _make_api()
    with patch.object(api, "_iot_request", new=AsyncMock()) as req:
        await api._invoke_service("iot-001", "cleanNow", {"bStartClean": 1})
    req.assert_awaited_once_with(
        "1.0.5",
        "/thing/service/invoke",
        {
            "args": {"bStartClean": 1},
            "identifier": "cleanNow",
            "iotId": "iot-001",
        },
    )


async def test_clean_now() -> None:
    api = _make_api()
    with patch.object(api, "_invoke_service", new=AsyncMock()) as executor:
        await api.clean_now("iot-001")
    executor.assert_awaited_once_with("iot-001", "cleanNow", {"bStartClean": 1})


async def test_sand_leveling() -> None:
    api = _make_api()
    with patch.object(api, "_invoke_service", new=AsyncMock()) as executor:
        await api.sand_leveling("iot-001")
    executor.assert_awaited_once_with("iot-001", "sandLeveling", {"bStartLeveling": 1})


# ---------------------------------------------------------------------------
# Signed web API calls
# ---------------------------------------------------------------------------


async def test_signed_get_happy() -> None:
    api = _make_api()
    _set_encryption(api)
    session = api._session
    session.get = MagicMock(
        return_value=_FakeJSONResponse(json_data={"code": 0, "data": {"x": 1}})
    )
    result = await api._signed_get("https://web.example.com/thing", {"a": 1})
    assert result == {"x": 1}
    headers = session.get.call_args.kwargs["headers"]
    assert headers["Token"] == "enc-token"
    assert headers["Uid"] == "uid-1"


async def test_signed_get_error_code() -> None:
    api = _make_api()
    _set_encryption(api)
    api._session.get = MagicMock(
        return_value=_FakeJSONResponse(json_data={"code": 1, "message": "bad"})
    )
    with pytest.raises(APIConnectionError):
        await api._signed_get("https://web.example.com/thing", {})


async def test_signed_get_client_error() -> None:
    api = _make_api()
    _set_encryption(api)
    api._session.get = MagicMock(side_effect=ClientError("boom"))
    with pytest.raises(APIConnectionError):
        await api._signed_get("https://web.example.com/thing", {})


def test_seven_days_ago() -> None:
    api = _make_api()
    assert api._seven_days_ago(1730000000) == 1730000000 - 7 * 86400


async def test_get_statistics() -> None:
    api = _make_api()
    api.baseurl = "https://web.example.com"
    _set_encryption(api)
    with patch.object(api, "_signed_get", new=AsyncMock(return_value={})) as signed:
        await api.get_statistics("dev-1")
    args = signed.await_args.args
    assert args[0] == "https://web.example.com/catbox/toilet/statistics"
    params = args[1]
    assert params["user_id"] == "user-1"
    assert params["device_name"] == "dev-1"
    assert params["end_time"] > params["start_time"]


async def test_get_records() -> None:
    api = _make_api()
    api.baseurl = "https://web.example.com"
    _set_encryption(api)
    with patch.object(api, "_signed_get", new=AsyncMock(return_value={})) as signed:
        await api.get_records("dev-1")
    args = signed.await_args.args
    assert args[0] == "https://web.example.com/catbox/record"
    assert args[1]["device_name"] == "dev-1"

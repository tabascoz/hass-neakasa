"""Tests for the async Aliyun IoT Gateway client."""

from __future__ import annotations

from base64 import b64decode
from typing import Self
from unittest.mock import MagicMock

from custom_components.neakasa.const import CLIENT_TIMEOUT
from custom_components.neakasa.iot_gateway import (
    AliyunIoTClient,
    IoTCommonParams,
    IoTConfig,
    IoTResponse,
)


class _Response:
    """Minimal aiohttp-like async context manager."""

    def __init__(
        self,
        status: int = 200,
        body: bytes = b"{}",
        reason: str = "OK",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status = status
        self._body = body
        self.reason = reason
        self.headers = headers or {}

    async def read(self) -> bytes:
        return self._body

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False


def test_generate_nonce() -> None:
    first = AliyunIoTClient.generate_nonce()
    second = AliyunIoTClient.generate_nonce()
    assert len(first) == 32
    assert first != second


def test_date_header() -> None:
    assert AliyunIoTClient._date_header().endswith("GMT")


def test_sign() -> None:
    cfg = IoTConfig(app_key="k", app_secret="s", domain="example.com")
    client = AliyunIoTClient(cfg, MagicMock())
    signature = client._sign(
        "POST",
        "application/json",
        "content-md5",
        "application/octet-stream",
        "date-value",
        "x-ca-key:k",
        "/path",
    )
    assert isinstance(signature, str)
    assert b64decode(signature)


def test_iot_config_defaults() -> None:
    cfg = IoTConfig(app_key="k", app_secret="s", domain="d")
    assert cfg.protocol == "HTTPS"


def test_iot_common_params_defaults() -> None:
    params = IoTCommonParams(api_ver="1.0")
    assert params.api_ver == "1.0"
    assert params.language == "en-US"
    assert params.iot_token == ""


def _fake_session(status: int = 200, body: bytes = b"{}") -> MagicMock:
    session = MagicMock()
    session.post = MagicMock(return_value=_Response(status=status, body=body))
    return session


async def test_do_request() -> None:
    session = _fake_session()
    cfg = IoTConfig(app_key="k", app_secret="s", domain="iot.example.com")
    client = AliyunIoTClient(cfg, session)
    result = await client.do_request("/thing/properties/get", {"a": 1})

    assert isinstance(result, IoTResponse)
    assert result.status_code == 200
    assert result.body == b"{}"

    session.post.assert_called_once()
    url = session.post.call_args.args[0]
    assert url == "https://iot.example.com/thing/properties/get"
    headers = session.post.call_args.kwargs["headers"]
    assert headers["host"] == "iot.example.com"
    assert headers["x-ca-signature"]
    assert (
        headers["x-ca-signature-headers"] == "x-ca-key,x-ca-nonce,x-ca-signaturemethod"
    )
    assert session.post.call_args.kwargs["timeout"] is CLIENT_TIMEOUT


async def test_do_request_non_200() -> None:
    session = _fake_session(status=500, body=b"error")
    cfg = IoTConfig(app_key="k", app_secret="s", domain="iot.example.com")
    client = AliyunIoTClient(cfg, session)
    result = await client.do_request("/thing/properties/get", {"a": 1})
    assert result.status_code == 500


async def test_do_request_raw() -> None:
    session = _fake_session()
    cfg = IoTConfig(app_key="k", app_secret="s", domain="oa.example.com")
    client = AliyunIoTClient(cfg, session)
    params = {
        "request": {"context": {"appKey": "k"}, "config": {}, "device": {}},
        "nested": {"list": [1, 2]},
    }
    result = await client.do_request_raw("/api/prd/connect.json", None, params)

    assert result.status_code == 200
    url = session.post.call_args.args[0]
    assert url == "https://oa.example.com/api/prd/connect.json"
    headers = session.post.call_args.kwargs["headers"]
    assert headers["content-type"] == "application/x-www-form-urlencoded"
    assert headers["x-ca-signature"]
    body = session.post.call_args.kwargs["data"]
    assert session.post.call_args.kwargs["timeout"] is CLIENT_TIMEOUT
    assert body


async def test_do_request_raw_with_overrides() -> None:
    session = _fake_session()
    cfg = IoTConfig(app_key="k", app_secret="s", domain="oa.example.com")
    client = AliyunIoTClient(cfg, session)
    params = {"loginByOauthRequest": {"authCode": "abc"}}
    result = await client.do_request_raw(
        "/api/prd/loginbyoauth.json", {"Vid": "vid-1"}, params
    )
    assert result.status_code == 200
    headers = session.post.call_args.kwargs["headers"]
    assert headers["Vid"] == "vid-1"

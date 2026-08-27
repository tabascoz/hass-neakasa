"""
Async Aliyun IoT Gateway client.

Replaces ``alibabacloud_iot_api_gateway`` + ``Tea`` SDK.
All HTTP goes through an ``aiohttp.ClientSession`` (HA-managed),
so there is no need for ``async_add_executor_job``.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
import urllib.parse
import uuid
from dataclasses import dataclass, field
from email.utils import formatdate
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from aiohttp import ClientSession

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Wire dataclasses (mirror the Aliyun SDK models)
# ---------------------------------------------------------------------------


@dataclass
class IoTConfig:
    """Credentials and endpoint for the Aliyun IoT API Gateway."""

    app_key: str
    app_secret: str
    domain: str
    protocol: str = "HTTPS"


@dataclass
class IoTCommonParams:
    """Common request parameters embedded in every IoT API call."""

    api_ver: str
    language: str = "en-US"
    iot_token: str = ""


@dataclass
class IoTResponse:
    """Mirrors ``TeaResponse`` so callers need zero changes."""

    status_code: int
    status_message: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""


# ---------------------------------------------------------------------------
# Async client
# ---------------------------------------------------------------------------


class AliyunIoTClient:
    """
    Async replacement for the Aliyun SDK ``Client`` + ``TeaCore.do_action``.

    Uses ``aiohttp`` for HTTP so every call is truly async — no thread-
    pool executor needed.
    """

    def __init__(self, config: IoTConfig, session: ClientSession) -> None:
        """Create a new client bound to one Aliyun IoT Gateway domain."""
        self._cfg = config
        self._session = session

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def generate_nonce() -> str:
        """
        Cryptographically random UUID hex.

        Replaces ``UtilClient.get_nonce``.
        """
        return uuid.uuid4().hex

    @staticmethod
    def _date_header() -> str:
        """
        RFC 7231 IMF-fixdate.

        Replaces ``UtilClient.get_date_utcstring``.
        """
        return formatdate(timeval=None, localtime=False, usegmt=True)

    def _sign(
        self,
        method: str,
        accept: str,
        content_md5: str,
        content_type: str,
        date_val: str,
        xca_headers: str,
        path_and_query: str,
    ) -> str:
        """
        HMAC-SHA256 → Base64 signature.

        Replaces ``APIGatewayUtilClient.get_signature``.
        """
        string = (
            f"{method}\n"
            f"{accept}\n"
            f"{content_md5}\n"
            f"{content_type}\n"
            f"{date_val}\n"
            f"{xca_headers}\n"
            f"{path_and_query}"
        )
        digest = hmac.new(
            self._cfg.app_secret.encode("utf-8"),
            string.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return base64.b64encode(digest).decode("utf-8")

    # -- JSON body path (replaces ``Client.do_request``) -------------------

    async def do_request(self, pathname: str, body: dict[str, Any]) -> IoTResponse:
        """
        POST with ``application/octet-stream`` + HMAC signing.

        *body* is the serialised ``IoTApiRequest`` dict, e.g.::

            {"id":"…","version":"1.0","params":{…},"request":{…}}
        """
        nonce = self.generate_nonce()
        date_val = self._date_header()
        json_body = json.dumps(body, separators=(",", ":"))
        content_md5 = base64.b64encode(
            hashlib.md5(json_body.encode()).digest()
        ).decode()

        # Build x-ca headers — these drive both the signature string and the
        # ``x-ca-signature-headers`` hint that the Aliyun gateway requires.
        x_ca: dict[str, str] = {
            "x-ca-key": self._cfg.app_key,
            "x-ca-nonce": nonce,
            "x-ca-signaturemethod": "HmacSHA256",
        }
        sorted_keys = sorted(x_ca)
        x_ca_header_str = "\n".join(f"{k}:{x_ca[k]}" for k in sorted_keys)
        x_ca_sign_headers = ",".join(sorted_keys)

        signature = self._sign(
            method="POST",
            accept="application/json",
            content_md5=content_md5,
            content_type="application/octet-stream",
            date_val=date_val,
            xca_headers=x_ca_header_str,
            path_and_query=pathname,
        )

        headers = {
            "host": self._cfg.domain,
            "date": date_val,
            "accept": "application/json",
            "content-type": "application/octet-stream",
            "content-md5": content_md5,
            "x-ca-signature": signature,
            "x-ca-signature-headers": x_ca_sign_headers,
        }
        headers.update(x_ca)

        url = f"https://{self._cfg.domain}{pathname}"
        async with self._session.post(url, headers=headers, data=json_body) as resp:
            body_bytes = await resp.read()
            if resp.status != 200:
                _LOGGER.debug(
                    "IoT gateway HTTP %s on %s: %s",
                    resp.status,
                    pathname,
                    body_bytes[:500],
                )
            return IoTResponse(
                status_code=resp.status,
                status_message=resp.reason or "",
                headers=dict(resp.headers),
                body=body_bytes,
            )

    # -- Form-encoded path (replaces ``Client.do_request_raw``) ------------

    async def do_request_raw(
        self,
        pathname: str,
        headers_overrides: dict[str, str] | None,
        params: dict[str, Any],
    ) -> IoTResponse:
        """
        POST with ``application/x-www-form-urlencoded`` + HMAC signing.

        *headers_overrides* can carry extra headers (e.g. ``Vid``).
        """
        nonce = self.generate_nonce()
        timestamp = str(int(time.time()))
        date_val = self._date_header()

        # Build query string from params
        body_items = [
            f"{k}={urllib.parse.quote_plus(json.dumps(v))}" for k, v in params.items()
        ]
        form_body = "&".join(body_items)

        base_headers: dict[str, str] = {
            "host": self._cfg.domain,
            "date": date_val,
            "x-ca-nonce": nonce,
            "x-ca-key": self._cfg.app_key,
            "x-ca-signature-method": "HmacSHA256",
            "x-ca-signature-Headers": (
                "x-ca-nonce,x-ca-timestamp,x-ca-key,x-ca-signature-method"
            ),
            "x-ca-timestamp": timestamp,
            "accept": "application/json",
            "content-type": "application/x-www-form-urlencoded",
        }

        if headers_overrides:
            base_headers.update(headers_overrides)

        # Compute signature — same algorithm as original do_request_raw
        sig_body_items = [f"{k}={json.dumps(v)}" for k, v in params.items()]
        path_and_query = pathname + "?" + "&".join(sig_body_items)

        raw_sig = (
            "POST",
            base_headers["accept"],
            base_headers["content-type"],
            base_headers["date"],
            f"x-ca-key:{base_headers['x-ca-key']}",
            f"x-ca-nonce:{nonce}",
            f"x-ca-signature-method:{base_headers['x-ca-signature-method']}",
            f"x-ca-timestamp:{timestamp}",
            path_and_query,
        )
        string_to_sign = "{}\n{}\n\n{}\n{}\n{}\n{}\n{}\n{}\n{}".format(*raw_sig)

        sig = base64.b64encode(
            hmac.new(
                self._cfg.app_secret.encode("utf-8"),
                string_to_sign.encode("utf-8"),
                hashlib.sha256,
            ).digest()
        ).decode("utf-8")

        base_headers["x-ca-signature"] = sig

        url = f"https://{self._cfg.domain}{pathname}"
        async with self._session.post(
            url, headers=base_headers, data=form_body
        ) as resp:
            return IoTResponse(
                status_code=resp.status,
                status_message=resp.reason or "",
                headers=dict(resp.headers),
                body=await resp.read(),
            )

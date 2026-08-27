"""Exception classes for the neakasa API client."""

from __future__ import annotations

from .api_client_authentication_error import NeakasaApiClientAuthenticationError
from .api_client_communication_error import NeakasaApiClientCommunicationError
from .api_client_device_busy_error import NeakasaApiClientDeviceBusyError
from .api_client_error import NeakasaApiClientError
from .api_client_session_expired_error import NeakasaApiClientSessionExpiredError

__all__ = [
    "NeakasaApiClientAuthenticationError",
    "NeakasaApiClientCommunicationError",
    "NeakasaApiClientDeviceBusyError",
    "NeakasaApiClientError",
    "NeakasaApiClientSessionExpiredError",
]

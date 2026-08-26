"""Exception classes for the neakasa API client."""

from __future__ import annotations

from .api_client_authentication_error import NeakasaApiClientAuthenticationError
from .api_client_communication_error import NeakasaApiClientCommunicationError
from .api_client_error import NeakasaApiClientError

__all__ = [
    "NeakasaApiClientAuthenticationError",
    "NeakasaApiClientCommunicationError",
    "NeakasaApiClientError",
]
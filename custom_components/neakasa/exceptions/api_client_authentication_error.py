"""Authentication error raised by the API client."""

from __future__ import annotations

from .api_client_error import NeakasaApiClientError


class NeakasaApiClientAuthenticationError(NeakasaApiClientError):
    """Exception to indicate an authentication error."""

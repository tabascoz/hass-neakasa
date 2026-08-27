"""Device-busy error raised by the API client."""

from __future__ import annotations

from .api_client_error import NeakasaApiClientError


class NeakasaApiClientDeviceBusyError(NeakasaApiClientError):
    """
    The device is mid-cycle and rejected a request (cloud code 29003).

    Subclasses :class:`NeakasaApiClientError` so callers that don't care
    about the distinction still catch it; the coordinator special-cases
    it to keep the last snapshot instead of marking entities unavailable.
    """

"""Session-expired error raised by the API client."""

from __future__ import annotations

from .api_client_authentication_error import NeakasaApiClientAuthenticationError


class NeakasaApiClientSessionExpiredError(NeakasaApiClientAuthenticationError):
    """
    The cloud dropped this client's session.

    Distinct from a credential failure: the cloud invalidates the session
    whenever the account signs in elsewhere while the stored credentials
    stay valid. Subclasses :class:`NeakasaApiClientAuthenticationError` so
    callers that don't care about the distinction still catch it; the
    coordinator special-cases it to sign in again instead of asking the
    user to reauthenticate.
    """
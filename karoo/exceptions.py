"""Domain-specific exceptions raised by python-karooconnect."""

from __future__ import annotations

from typing import Any


class KarooConnectError(Exception):
    """Base exception for all python-karooconnect errors."""


class KarooConfigurationError(KarooConnectError):
    """Raised when local client configuration is missing or invalid."""


class KarooConnectionError(KarooConnectError):
    """Raised for network-level request failures."""


class KarooHTTPError(KarooConnectError):
    """Raised for non-successful API responses."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        response: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class KarooAuthenticationError(KarooHTTPError):
    """Raised when the API rejects or lacks authentication."""


class KarooTooManyRequestsError(KarooHTTPError):
    """Raised when the API rate-limits the client."""


class KarooRequestError(KarooHTTPError):
    """Raised for API errors other than auth or rate limiting."""

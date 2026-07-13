"""Python client for Karoo / SRAM account activity APIs."""

from .auth import KarooTokens, load_tokens, save_tokens
from .client import Karoo, KarooClient
from .exceptions import (
    KarooAuthenticationError,
    KarooConfigurationError,
    KarooConnectError,
    KarooConnectionError,
    KarooHTTPError,
    KarooRequestError,
    KarooTooManyRequestsError,
)

__version__ = "0.1.0"

__all__ = [
    "Karoo",
    "KarooAuthenticationError",
    "KarooClient",
    "KarooConfigurationError",
    "KarooConnectError",
    "KarooConnectionError",
    "KarooHTTPError",
    "KarooRequestError",
    "KarooTokens",
    "KarooTooManyRequestsError",
    "load_tokens",
    "save_tokens",
]

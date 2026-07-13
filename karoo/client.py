"""HTTP client and activity API wrapper for Karoo / SRAM accounts."""

from __future__ import annotations

import json as json_module
import logging
import random
import time
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol
from urllib.parse import quote

import requests
from requests import Response

from .auth import KarooTokens, load_tokens, save_tokens
from .exceptions import (
    KarooAuthenticationError,
    KarooConfigurationError,
    KarooConnectionError,
    KarooRequestError,
    KarooTooManyRequestsError,
)

if TYPE_CHECKING:
    from datetime import datetime

DEFAULT_BASE_URL = "https://dashboard.hammerhead.io"
DEFAULT_API_PREFIX = "/v1"
DEFAULT_TIMEOUT = 30.0
USER_AGENT = "python-karooconnect/0.1.0"

logger = logging.getLogger(__name__)


class SessionLike(Protocol):
    """Minimal requests-compatible session protocol."""

    def request(self, method: str, url: str, **kwargs: Any) -> Any:
        """Send an HTTP request."""


class KarooClient:
    """Low-level bearer-token HTTP client for the Karoo dashboard API."""

    def __init__(
        self,
        *,
        access_token: str | None = None,
        refresh_token: str | None = None,
        tokens: KarooTokens | None = None,
        tokenstore: str | Path | None = None,
        base_url: str = DEFAULT_BASE_URL,
        api_prefix: str = DEFAULT_API_PREFIX,
        session: SessionLike | None = None,
        retry_attempts: int = 2,
        retry_min_wait: float = 0.5,
        retry_max_wait: float = 4.0,
        timeout: float | tuple[float, float] = DEFAULT_TIMEOUT,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_prefix = _normalize_prefix(api_prefix)
        self.session = session or requests.Session()
        self.retry_attempts = max(0, retry_attempts)
        self.retry_min_wait = retry_min_wait
        self.retry_max_wait = retry_max_wait
        self.timeout = timeout
        self.tokenstore = Path(tokenstore).expanduser() if tokenstore else None
        self.tokens: KarooTokens | None

        if tokens is not None:
            self.tokens = tokens
        elif access_token is not None:
            self.tokens = KarooTokens(
                access_token=access_token,
                refresh_token=refresh_token,
            )
        elif self.tokenstore is not None:
            self.tokens = load_tokens(self.tokenstore)
        else:
            self.tokens = None

    @property
    def is_authenticated(self) -> bool:
        """Return True when an access token is loaded."""
        return bool(self.tokens and self.tokens.access_token)

    def set_tokens(self, tokens: KarooTokens) -> None:
        """Replace the in-memory token set."""
        self.tokens = tokens

    def load_tokens(self, path: str | Path | None = None) -> KarooTokens:
        """Load tokens from a configured or explicit token file."""
        token_path = self._token_path(path)
        self.tokens = load_tokens(token_path)
        return self.tokens

    def save_tokens(self, path: str | Path | None = None) -> None:
        """Persist the current token set."""
        if self.tokens is None:
            raise KarooAuthenticationError("No tokens are loaded")
        save_tokens(self._token_path(path), self.tokens)

    def refresh_token(self) -> KarooTokens:
        """Refresh the access token.

        SRAM browser OAuth support is intentionally outside the initial
        token-supplied MVP. This method is present so the public surface has a
        stable place for the future refresh exchange.
        """
        raise NotImplementedError(
            "SRAM OAuth refresh is not implemented yet; supply a fresh token"
        )

    def request(
        self,
        method: str,
        path: str,
        *,
        authenticated: bool = True,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        json: Any | None = None,
        data: Any | None = None,
        files: Any | None = None,
        stream: bool = False,
        raw: bool = False,
        expected_status: int | tuple[int, ...] | None = None,
        timeout: float | tuple[float, float] | None = None,
    ) -> Any:
        """Send an API request and return parsed JSON, raw bytes, or None."""
        url = self._url_for(path)
        request_headers = self._headers(authenticated=authenticated, extra=headers)
        expected_statuses = _expected_statuses(expected_status)

        for attempt in range(self.retry_attempts + 1):
            try:
                response = self.session.request(
                    method.upper(),
                    url,
                    params=params,
                    headers=request_headers,
                    json=json,
                    data=data,
                    files=files,
                    stream=stream,
                    timeout=self.timeout if timeout is None else timeout,
                )
            except (requests.ConnectionError, requests.Timeout) as exc:
                if attempt < self.retry_attempts:
                    self._sleep_before_retry(attempt, method, path, exc)
                    continue
                raise KarooConnectionError(
                    f"Network error during {method} {path}"
                ) from exc
            except requests.RequestException as exc:
                raise KarooConnectionError(
                    f"Request failed during {method} {path}"
                ) from exc

            if response.status_code >= 500 and attempt < self.retry_attempts:
                self._sleep_before_retry(attempt, method, path, None, response)
                continue

            return self._parse_response(
                response,
                expected_statuses=expected_statuses,
                raw=raw,
            )

        raise KarooConnectionError(f"Request failed during {method} {path}")

    def _token_path(self, path: str | Path | None) -> Path:
        token_path = Path(path).expanduser() if path is not None else self.tokenstore
        if token_path is None:
            raise KarooConfigurationError("No tokenstore path configured")
        return token_path

    def _url_for(self, path: str) -> str:
        normalized_path = path if path.startswith("/") else f"/{path}"
        if self.api_prefix and not (
            normalized_path == self.api_prefix
            or normalized_path.startswith(f"{self.api_prefix}/")
        ):
            normalized_path = f"{self.api_prefix}{normalized_path}"
        return f"{self.base_url}{normalized_path}"

    def _headers(
        self,
        *,
        authenticated: bool,
        extra: Mapping[str, str] | None,
    ) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        }
        if authenticated:
            headers["Authorization"] = self._authorization_header()
        if extra is not None:
            headers.update(extra)
        return headers

    def _authorization_header(self) -> str:
        if self.tokens is None or not self.tokens.access_token:
            raise KarooAuthenticationError("No access token is loaded")
        if self.tokens.is_expired():
            raise KarooAuthenticationError("Access token is expired")
        return f"{self.tokens.token_type} {self.tokens.access_token}"

    def _parse_response(
        self,
        response: Response,
        *,
        expected_statuses: set[int] | None,
        raw: bool,
    ) -> Any:
        if expected_statuses is not None:
            if response.status_code not in expected_statuses:
                self._raise_response_error(response)
        elif response.status_code >= 400:
            self._raise_response_error(response)

        if response.status_code == 204:
            return None
        if raw:
            return response.content
        if not response.content:
            return None

        content_type = response.headers.get("Content-Type", "").lower()
        if "application/json" in content_type:
            return response.json()
        return response.content

    def _raise_response_error(self, response: Response) -> None:
        message = _response_error_message(response)
        if response.status_code in {401, 403}:
            raise KarooAuthenticationError(
                message,
                status_code=response.status_code,
                response=response,
            )
        if response.status_code == 429:
            raise KarooTooManyRequestsError(
                message,
                status_code=response.status_code,
                response=response,
            )
        raise KarooRequestError(
            message,
            status_code=response.status_code,
            response=response,
        )

    def _sleep_before_retry(
        self,
        attempt: int,
        method: str,
        path: str,
        exc: BaseException | None,
        response: Response | None = None,
    ) -> None:
        delay = _backoff_delay(
            attempt,
            min_wait=self.retry_min_wait,
            max_wait=self.retry_max_wait,
        )
        status = response.status_code if response is not None else None
        logger.warning(
            "Karoo API %s %s attempt %s/%s failed (status=%s): %s",
            method.upper(),
            path,
            attempt + 1,
            self.retry_attempts + 1,
            status,
            exc or response.text if response is not None else exc,
        )
        time.sleep(delay)


class Karoo:
    """High-level Karoo activity API wrapper."""

    def __init__(
        self,
        *,
        access_token: str | None = None,
        refresh_token: str | None = None,
        user_id: str | int | None = None,
        tokenstore: str | Path | None = None,
        client: KarooClient | None = None,
        base_url: str = DEFAULT_BASE_URL,
    ) -> None:
        self.client = client or KarooClient(
            access_token=access_token,
            refresh_token=refresh_token,
            tokenstore=tokenstore,
            base_url=base_url,
        )

        token_user_id = self.client.tokens.user_id if self.client.tokens else None
        resolved_user_id = user_id if user_id is not None else token_user_id
        self.user_id = str(resolved_user_id) if resolved_user_id is not None else None
        if self.client.tokens is not None and self.client.tokens.user_id is None:
            self.client.tokens.user_id = self.user_id

    @classmethod
    def from_token_file(
        cls,
        path: str | Path,
        *,
        user_id: str | int | None = None,
        base_url: str = DEFAULT_BASE_URL,
    ) -> Karoo:
        """Create an API wrapper from a token JSON file."""
        return cls(tokenstore=path, user_id=user_id, base_url=base_url)

    @property
    def is_authenticated(self) -> bool:
        """Return True when the underlying client has an access token."""
        return self.client.is_authenticated

    def authorize(
        self,
        access_token: str,
        *,
        refresh_token: str | None = None,
        user_id: str | int | None = None,
        expires_at: datetime | None = None,
        scope: str | None = None,
    ) -> KarooTokens:
        """Set externally obtained SRAM tokens on this client."""
        tokens = KarooTokens(
            access_token=access_token,
            refresh_token=refresh_token,
            user_id=str(user_id) if user_id is not None else self.user_id,
            expires_at=expires_at,
            scope=scope,
        )
        self.client.set_tokens(tokens)
        if tokens.user_id is not None:
            self.user_id = tokens.user_id
        return tokens

    def login(self) -> None:
        """Raise until browser OAuth is implemented."""
        raise NotImplementedError(
            "Browser OAuth login is not implemented yet; use authorize() "
            "or pass access_token/tokenstore"
        )

    def refresh_token(self) -> KarooTokens:
        """Refresh the access token through the low-level client."""
        return self.client.refresh_token()

    def save_tokens(self, path: str | Path | None = None) -> None:
        """Persist current tokens through the low-level client."""
        self.client.save_tokens(path)

    def load_tokens(self, path: str | Path | None = None) -> KarooTokens:
        """Load tokens and update the wrapper user id if present."""
        tokens = self.client.load_tokens(path)
        if tokens.user_id is not None:
            self.user_id = tokens.user_id
        return tokens

    def get_activities(
        self,
        *,
        page: int = 1,
        per_page: int = 50,
        search: str = "",
        order_by: str = "",
        ascending: bool = False,
    ) -> Any:
        """List activities for the configured user."""
        _validate_positive_int(page, "page")
        _validate_positive_int(per_page, "per_page")

        params: dict[str, Any] = {
            "page": page,
            "perPage": per_page,
            "ascending": str(ascending).lower(),
        }
        if search:
            params["search"] = search
        if order_by:
            params["orderBy"] = order_by

        return self.client.request(
            "GET",
            f"/users/{self._quoted_user_id()}/activities",
            params=params,
        )

    def get_activity_details(self, activity_id: str | int) -> Any:
        """Return detail data for one activity."""
        return self.client.request(
            "GET",
            f"/users/{self._quoted_user_id()}/activities/"
            f"{_quote_required(activity_id, 'activity_id')}/details",
        )

    def download_activity_fit(self, activity_id: str | int) -> bytes:
        """Download one activity as a FIT file."""
        return self.client.request(
            "GET",
            f"/users/{self._quoted_user_id()}/activities/"
            f"{_quote_required(activity_id, 'activity_id')}/file",
            params={"format": "fit"},
            headers={"Accept": "application/octet-stream"},
            raw=True,
        )

    def import_activity_fit(self, path: str | Path) -> Any:
        """Import a local FIT file into the user's activity list."""
        fit_path = Path(path).expanduser()
        if not fit_path.is_file():
            raise FileNotFoundError(f"FIT file not found: {fit_path}")

        with fit_path.open("rb") as fit_file:
            files = {
                "file": (
                    fit_path.name,
                    fit_file,
                    "application/octet-stream",
                )
            }
            return self.client.request(
                "POST",
                f"/users/{self._quoted_user_id()}/activities/import/file",
                files=files,
            )

    def update_activity(self, activity_id: str | int, **fields: Any) -> Any:
        """Patch fields on one activity."""
        if not fields:
            raise ValueError("At least one activity field is required")
        return self.client.request(
            "PATCH",
            f"/users/{self._quoted_user_id()}/activities/"
            f"{_quote_required(activity_id, 'activity_id')}",
            json=fields,
        )

    def delete_activity(self, activity_id: str | int) -> Any:
        """Delete one activity."""
        return self.client.request(
            "DELETE",
            f"/users/{self._quoted_user_id()}/activities/"
            f"{_quote_required(activity_id, 'activity_id')}",
            expected_status=(200, 202, 204),
        )

    def upload_activity_to_partner(self, activity_id: str | int, partner: str) -> Any:
        """Upload one activity to a linked partner account."""
        return self.client.request(
            "POST",
            f"/users/{self._quoted_user_id()}/activities/"
            f"{_quote_required(activity_id, 'activity_id')}/upload",
            params={"uploadTo": _require_non_empty(partner, "partner")},
        )

    def _quoted_user_id(self) -> str:
        if self.user_id is None:
            raise KarooConfigurationError("user_id is required for activity endpoints")
        return quote(_require_non_empty(self.user_id, "user_id"), safe="")


def _normalize_prefix(prefix: str) -> str:
    if not prefix:
        return ""
    return f"/{prefix.strip('/')}"


def _expected_statuses(
    expected_status: int | tuple[int, ...] | None,
) -> set[int] | None:
    if expected_status is None:
        return None
    if isinstance(expected_status, int):
        return {expected_status}
    return set(expected_status)


def _response_error_message(response: Response) -> str:
    detail = response.text.strip()
    try:
        payload = response.json()
    except ValueError:
        payload = None

    if isinstance(payload, Mapping):
        error_detail = payload.get("message") or payload.get("error_description")
        error_detail = error_detail or payload.get("error")
        if error_detail:
            detail = str(error_detail)
        elif payload:
            detail = json_module.dumps(payload, sort_keys=True)

    reason = getattr(response, "reason", "")
    fallback = reason or "Unexpected response"
    url = getattr(response, "url", "")
    url_context = f" for {url}" if url else ""
    return f"Karoo API error {response.status_code}{url_context}: {detail or fallback}"


def _backoff_delay(attempt: int, *, min_wait: float, max_wait: float) -> float:
    base = min(max_wait, min_wait * (2**attempt))
    return base * (0.5 + random.random() * 0.5)


def _validate_positive_int(value: int, name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{name} must be an integer")
    if value <= 0:
        raise ValueError(f"{name} must be positive")


def _quote_required(value: str | int, name: str) -> str:
    return quote(_require_non_empty(value, name), safe="")


def _require_non_empty(value: str | int, name: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{name} must be non-empty")
    return text

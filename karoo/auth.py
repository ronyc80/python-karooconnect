"""Token helpers for the token-supplied Karoo auth MVP."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .exceptions import KarooConfigurationError

UTC = timezone.utc


@dataclass(slots=True)
class KarooTokens:
    """Bearer token set for SRAM-backed Karoo APIs."""

    access_token: str
    refresh_token: str | None = None
    user_id: str | None = None
    token_type: str = "Bearer"  # noqa: S105 - OAuth token type, not a secret.
    expires_at: datetime | None = None
    scope: str | None = None

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> KarooTokens:
        """Build tokens from JSON-style data.

        Both snake_case and the camelCase names commonly found in OAuth
        payloads are accepted.
        """
        access_token = data.get("access_token") or data.get("accessToken")
        if not isinstance(access_token, str) or not access_token:
            raise KarooConfigurationError("Token data must include access_token")

        refresh_token = data.get("refresh_token") or data.get("refreshToken")
        raw_user_id = data.get("user_id")
        if raw_user_id is None:
            raw_user_id = data.get("userId")

        token_type = data.get("token_type") or data.get("tokenType") or "Bearer"
        if not isinstance(token_type, str) or not token_type:
            raise KarooConfigurationError("token_type must be a non-empty string")

        expires_at = _expires_at_from_mapping(data)
        scope = data.get("scope")

        return cls(
            access_token=access_token,
            refresh_token=str(refresh_token) if refresh_token is not None else None,
            user_id=str(raw_user_id) if raw_user_id is not None else None,
            token_type=token_type,
            expires_at=expires_at,
            scope=str(scope) if scope is not None else None,
        )

    def to_mapping(self) -> dict[str, str]:
        """Return a JSON-serializable token mapping."""
        data = {
            "access_token": self.access_token,
            "token_type": self.token_type,
        }
        if self.refresh_token is not None:
            data["refresh_token"] = self.refresh_token
        if self.user_id is not None:
            data["user_id"] = self.user_id
        if self.scope is not None:
            data["scope"] = self.scope
        if self.expires_at is not None:
            data["expires_at"] = _format_datetime(self.expires_at)
        return data

    def is_expired(self, *, skew_seconds: int = 60) -> bool:
        """Return True when the access token is expired or about to expire."""
        if self.expires_at is None:
            return False
        expires_at = _ensure_aware(self.expires_at)
        return expires_at <= datetime.now(UTC) + timedelta(seconds=skew_seconds)


def load_tokens(path: str | Path) -> KarooTokens:
    """Load tokens from a JSON file."""
    token_path = Path(path).expanduser()
    try:
        data = json.loads(token_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise KarooConfigurationError(f"Token file not found: {token_path}") from exc
    except json.JSONDecodeError as exc:
        raise KarooConfigurationError(f"Invalid token JSON: {token_path}") from exc

    if not isinstance(data, Mapping):
        raise KarooConfigurationError("Token file must contain a JSON object")
    return KarooTokens.from_mapping(data)


def save_tokens(path: str | Path, tokens: KarooTokens) -> None:
    """Persist tokens as JSON with owner-only file permissions."""
    token_path = Path(path).expanduser()
    token_path.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = token_path.with_name(f".{token_path.name}.tmp")
    payload = json.dumps(tokens.to_mapping(), indent=2, sort_keys=True)
    tmp_path.write_text(f"{payload}\n", encoding="utf-8")
    tmp_path.chmod(0o600)
    tmp_path.replace(token_path)
    token_path.chmod(0o600)


def _expires_at_from_mapping(data: Mapping[str, Any]) -> datetime | None:
    expires_at = data.get("expires_at") or data.get("expiresAt")
    if expires_at is not None:
        return _parse_datetime(expires_at)

    expires_in = data.get("expires_in") or data.get("expiresIn")
    if expires_in is None:
        return None

    try:
        seconds = int(expires_in)
    except (TypeError, ValueError) as exc:
        raise KarooConfigurationError("expires_in must be an integer") from exc
    return datetime.now(UTC) + timedelta(seconds=seconds)


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return _ensure_aware(value)
    if not isinstance(value, str) or not value:
        raise KarooConfigurationError("expires_at must be an ISO 8601 string")

    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise KarooConfigurationError("expires_at must be an ISO 8601 string") from exc
    return _ensure_aware(parsed)


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _format_datetime(value: datetime) -> str:
    return _ensure_aware(value).isoformat().replace("+00:00", "Z")

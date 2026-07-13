"""Unit tests for token parsing and persistence."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from karoo import Karoo, KarooConfigurationError, KarooTokens, load_tokens, save_tokens

UTC = timezone.utc


def test_token_round_trip_preserves_core_fields(tmp_path):
    expires_at = datetime(2026, 7, 13, 12, 30, tzinfo=UTC)
    tokens = KarooTokens(
        access_token="access",
        refresh_token="refresh",
        user_id="user-123",
        expires_at=expires_at,
        scope="openid profile",
    )
    token_path = tmp_path / "tokens.json"

    save_tokens(token_path, tokens)
    loaded = load_tokens(token_path)

    assert loaded.access_token == "access"
    assert loaded.refresh_token == "refresh"
    assert loaded.user_id == "user-123"
    assert loaded.scope == "openid profile"
    assert loaded.expires_at == expires_at


def test_save_tokens_uses_owner_only_permissions(tmp_path):
    token_path = tmp_path / "tokens.json"

    save_tokens(token_path, KarooTokens(access_token="access"))

    assert oct(token_path.stat().st_mode & 0o777) == "0o600"


def test_from_mapping_accepts_oauth_camel_case_fields():
    tokens = KarooTokens.from_mapping(
        {
            "accessToken": "access",
            "refreshToken": "refresh",
            "userId": 123,
            "tokenType": "Bearer",
            "expiresIn": 3600,
        }
    )

    assert tokens.access_token == "access"
    assert tokens.refresh_token == "refresh"
    assert tokens.user_id == "123"
    assert tokens.expires_at is not None
    assert not tokens.is_expired()


def test_expired_token_detection_uses_skew():
    tokens = KarooTokens(
        access_token="access",
        expires_at=datetime.now(UTC) + timedelta(seconds=30),
    )

    assert tokens.is_expired(skew_seconds=60)


def test_missing_access_token_is_configuration_error():
    with pytest.raises(KarooConfigurationError, match="access_token"):
        KarooTokens.from_mapping({"refresh_token": "refresh"})


def test_karoo_constructor_keeps_user_id_with_supplied_token():
    api = Karoo(access_token="access", user_id="user-123")

    assert api.client.tokens is not None
    assert api.client.tokens.user_id == "user-123"

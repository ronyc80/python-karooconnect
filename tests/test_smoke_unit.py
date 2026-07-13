"""Unit tests for the manual smoke runner helpers."""

from __future__ import annotations

from scripts.smoke_activities import _build_api, _load_env_file


def test_load_env_file_accepts_comments_export_and_quotes(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "# local smoke config",
                "export KAROO_ACCESS_TOKEN='access token'",
                'KAROO_USER_ID="user-123"',
                "KAROO_REFRESH_TOKEN=refresh",
            ]
        ),
        encoding="utf-8",
    )

    values = _load_env_file(env_path)

    assert values == {
        "KAROO_ACCESS_TOKEN": "access token",
        "KAROO_USER_ID": "user-123",
        "KAROO_REFRESH_TOKEN": "refresh",
    }


def test_build_api_uses_env_base_url_and_api_prefix():
    api = _build_api(
        "~/.karooconnect/tokens.json",
        {
            "KAROO_ACCESS_TOKEN": "access",
            "KAROO_USER_ID": "user-123",
            "KAROO_BASE_URL": "https://example.test",
            "KAROO_API_PREFIX": "/api/v1",
        },
    )

    assert api.user_id == "user-123"
    assert api.client.base_url == "https://example.test"
    assert api.client.api_prefix == "/api/v1"

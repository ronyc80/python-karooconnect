"""Unit tests for the manual smoke runner helpers."""

from __future__ import annotations

from scripts.smoke_activities import _load_env_file


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

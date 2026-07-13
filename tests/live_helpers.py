"""Helpers for gated live Karoo API tests."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from scripts.smoke_activities import _build_api, _load_env_file

if TYPE_CHECKING:
    from karoo import Karoo


def live_api() -> Karoo:
    """Return a configured live API client or skip the test."""
    if os.environ.get("KAROO_LIVE") != "1":
        pytest.skip("Set KAROO_LIVE=1 to run live Karoo API tests")

    env = _load_env_file(Path(".env"))
    api = _build_api("~/.karooconnect/tokens.json", env)
    if not api.is_authenticated:
        pytest.skip("KAROO_ACCESS_TOKEN is required for live Karoo API tests")
    if api.user_id is None:
        pytest.skip("KAROO_USER_ID is required for live Karoo API tests")
    return api

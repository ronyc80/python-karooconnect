"""Gated live tests for inferred Karoo/SRAM activity endpoints."""

from __future__ import annotations

from scripts.smoke_activities import _extract_activities, _extract_activity_id
from tests.live_helpers import live_api


def test_live_activity_list_details_and_fit_download():
    api = live_api()

    activities_payload = api.get_activities(page=1, per_page=1)
    activities = _extract_activities(activities_payload)

    assert activities

    activity_id = _extract_activity_id(activities[0])
    details = api.get_activity_details(activity_id)
    fit_bytes = api.download_activity_fit(activity_id)

    assert isinstance(details, dict)
    assert details
    assert fit_bytes
    assert len(fit_bytes) > 14

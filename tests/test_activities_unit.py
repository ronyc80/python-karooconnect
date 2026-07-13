"""Unit tests for high-level activity endpoints."""

from __future__ import annotations

import pytest
from conftest import DummyResponse, RecordingSession

from karoo import Karoo, KarooClient, KarooConfigurationError


def test_get_activities_builds_expected_query_params():
    session = RecordingSession([DummyResponse(payload={"items": []})])
    api = _api(session)

    result = api.get_activities(
        page=2,
        per_page=25,
        search="ride",
        order_by="startTime",
        ascending=True,
    )

    assert result == {"items": []}
    call = session.calls[0]
    assert call["method"] == "GET"
    assert call["url"] == (
        "https://dashboard.hammerhead.io/v1/users/user-123/activities"
    )
    assert call["kwargs"]["params"] == {
        "page": 2,
        "perPage": 25,
        "ascending": "true",
        "search": "ride",
        "orderBy": "startTime",
    }


def test_get_activity_details_builds_details_path():
    session = RecordingSession([DummyResponse(payload={"id": "activity-1"})])
    api = _api(session)

    result = api.get_activity_details("activity-1")

    assert result == {"id": "activity-1"}
    assert session.calls[0]["method"] == "GET"
    assert session.calls[0]["url"] == (
        "https://dashboard.hammerhead.io/v1/users/user-123/activities/"
        "activity-1/details"
    )


def test_download_activity_fit_returns_raw_bytes():
    session = RecordingSession(
        [
            DummyResponse(
                content=b"fit bytes",
                headers={"Content-Type": "application/octet-stream"},
            )
        ]
    )
    api = _api(session)

    result = api.download_activity_fit("activity-1")

    assert result == b"fit bytes"
    call = session.calls[0]
    assert call["method"] == "GET"
    assert call["url"].endswith("/activities/activity-1/file")
    assert call["kwargs"]["params"] == {"format": "fit"}
    assert call["kwargs"]["headers"]["Accept"] == "application/octet-stream"


def test_import_activity_fit_posts_file(tmp_path):
    fit_path = tmp_path / "ride.fit"
    fit_path.write_bytes(b"fit")
    session = RecordingSession([DummyResponse(payload={"id": "activity-1"})])
    api = _api(session)

    result = api.import_activity_fit(fit_path)

    assert result == {"id": "activity-1"}
    call = session.calls[0]
    assert call["method"] == "POST"
    assert call["url"].endswith("/activities/import/file")
    file_name, _file_obj, content_type = call["kwargs"]["files"]["file"]
    assert file_name == "ride.fit"
    assert content_type == "application/octet-stream"


def test_update_activity_patches_supplied_fields():
    session = RecordingSession([DummyResponse(payload={"id": "activity-1"})])
    api = _api(session)

    api.update_activity("activity-1", name="Morning ride")

    call = session.calls[0]
    assert call["method"] == "PATCH"
    assert call["url"].endswith("/activities/activity-1")
    assert call["kwargs"]["json"] == {"name": "Morning ride"}


def test_delete_activity_accepts_empty_response():
    session = RecordingSession([DummyResponse(status_code=204)])
    api = _api(session)

    result = api.delete_activity("activity-1")

    assert result is None
    call = session.calls[0]
    assert call["method"] == "DELETE"
    assert call["url"].endswith("/activities/activity-1")


def test_missing_user_id_rejects_activity_calls():
    session = RecordingSession()
    api = Karoo(
        client=KarooClient(
            access_token="access",
            session=session,
            retry_attempts=0,
        )
    )

    with pytest.raises(KarooConfigurationError, match="user_id"):
        api.get_activities()


@pytest.mark.parametrize("field", ["activity_id", "partner"])
def test_required_path_values_reject_empty_strings(field):
    session = RecordingSession()
    api = _api(session)

    with pytest.raises(ValueError, match=field):
        if field == "activity_id":
            api.get_activity_details("")
        else:
            api.upload_activity_to_partner("activity-1", "")


def _api(session: RecordingSession) -> Karoo:
    client = KarooClient(
        access_token="access",
        session=session,
        retry_attempts=0,
    )
    return Karoo(client=client, user_id="user-123")

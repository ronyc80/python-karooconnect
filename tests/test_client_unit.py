"""Unit tests for low-level request construction and error handling."""

from __future__ import annotations

import pytest
import requests
from conftest import DummyResponse, RecordingSession

from karoo import (
    KarooAuthenticationError,
    KarooClient,
    KarooConnectionError,
    KarooRequestError,
    KarooTooManyRequestsError,
)


def test_request_builds_prefixed_url_and_bearer_header():
    session = RecordingSession([DummyResponse(payload={"ok": True})])
    client = KarooClient(
        access_token="access",
        session=session,
        retry_attempts=0,
    )

    result = client.request("GET", "/users/user-123/activities")

    assert result == {"ok": True}
    call = session.calls[0]
    assert call["method"] == "GET"
    assert call["url"] == (
        "https://dashboard.hammerhead.io/v1/users/user-123/activities"
    )
    assert call["kwargs"]["headers"]["Authorization"] == "Bearer access"
    assert call["kwargs"]["headers"]["Accept"] == "application/json"


def test_request_does_not_double_prefix_v1_path():
    session = RecordingSession([DummyResponse(payload={"ok": True})])
    client = KarooClient(access_token="access", session=session, retry_attempts=0)

    client.request("GET", "/v1/users/user-123/activities")

    assert session.calls[0]["url"] == (
        "https://dashboard.hammerhead.io/v1/users/user-123/activities"
    )


def test_unauthenticated_request_omits_authorization_header():
    session = RecordingSession([DummyResponse(payload={"config": True})])
    client = KarooClient(session=session, retry_attempts=0)

    client.request("GET", "/status", authenticated=False)

    assert "Authorization" not in session.calls[0]["kwargs"]["headers"]


@pytest.mark.parametrize(
    ("status_code", "exception_type"),
    [
        (401, KarooAuthenticationError),
        (403, KarooAuthenticationError),
        (429, KarooTooManyRequestsError),
        (500, KarooRequestError),
    ],
)
def test_request_translates_http_errors(status_code, exception_type):
    session = RecordingSession(
        [
            DummyResponse(
                status_code=status_code,
                payload={"message": "nope"},
                url="https://dashboard.hammerhead.io/v1/nope",
            )
        ]
    )
    client = KarooClient(
        access_token="access",
        session=session,
        retry_attempts=0,
    )

    with pytest.raises(exception_type, match="nope") as exc_info:
        client.request("GET", "/users/user-123/activities")

    assert exc_info.value.status_code == status_code
    assert "https://dashboard.hammerhead.io/v1/nope" in str(exc_info.value)


def test_network_errors_raise_connection_error():
    class FailingSession:
        def request(self, method: str, url: str, **kwargs):
            raise requests.ConnectionError("boom")

    client = KarooClient(
        access_token="access",
        session=FailingSession(),
        retry_attempts=0,
    )

    with pytest.raises(KarooConnectionError, match="Network error"):
        client.request("GET", "/users/user-123/activities")

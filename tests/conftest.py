"""Test helpers for mock-based client tests."""

from __future__ import annotations

import json
from typing import Any


class DummyResponse:
    """Small response double with the requests.Response surface we need."""

    def __init__(
        self,
        *,
        status_code: int = 200,
        payload: Any | None = None,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
        text: str | None = None,
        reason: str = "",
    ) -> None:
        self.status_code = status_code
        self._payload = payload
        if content is None and payload is not None:
            content = json.dumps(payload).encode()
        self.content = content or b""
        self.headers = headers or {"Content-Type": "application/json"}
        self.text = text if text is not None else self.content.decode(errors="ignore")
        self.reason = reason

    def json(self) -> Any:
        if self._payload is not None:
            return self._payload
        return json.loads(self.content.decode())


class RecordingSession:
    """Requests session double that records calls and returns queued responses."""

    def __init__(self, responses: list[DummyResponse] | None = None) -> None:
        self.responses = responses or [DummyResponse(payload={})]
        self.calls: list[dict[str, Any]] = []

    def request(self, method: str, url: str, **kwargs: Any) -> DummyResponse:
        self.calls.append({"method": method, "url": url, "kwargs": kwargs})
        if not self.responses:
            raise AssertionError("No queued response for request")
        return self.responses.pop(0)

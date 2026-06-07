"""POST/GET /sessions: lifecycle, normalization, filtering."""

from __future__ import annotations

import re
import uuid
from datetime import datetime

import pytest

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


@pytest.mark.e2e
def test_create_session_returns_full_record(http, api_url: str, unique_tag: str) -> None:
    response = http.post(
        f"{api_url}/sessions",
        json={"minutes": 25, "tag": unique_tag},
    )
    assert response.status_code == 200
    body = response.json()

    assert UUID_RE.match(body["id"]), f"id is not a UUID: {body['id']!r}"
    # timestamp is ISO-8601 with timezone; fromisoformat parses both forms.
    datetime.fromisoformat(body["timestamp"])
    assert body["minutes"] == 25
    assert body["tag"] == unique_tag  # already lowercase, no whitespace


@pytest.mark.e2e
def test_create_session_normalizes_tag(http, api_url: str) -> None:
    # Build an upper/whitespace variant of a unique tag so it normalizes deterministically.
    raw_tag = uuid.uuid4().hex[:8]
    payload_tag = f"  {raw_tag.upper()}  "
    expected = raw_tag.lower()

    response = http.post(
        f"{api_url}/sessions",
        json={"minutes": 10, "tag": payload_tag},
    )
    assert response.status_code == 200
    assert response.json()["tag"] == expected


@pytest.mark.e2e
def test_list_sessions_includes_created(http, api_url: str, unique_tag: str) -> None:
    create = http.post(
        f"{api_url}/sessions",
        json={"minutes": 30, "tag": unique_tag},
    )
    assert create.status_code == 200
    created_id = create.json()["id"]

    listing = http.get(f"{api_url}/sessions")
    assert listing.status_code == 200
    sessions = listing.json()
    ids = [s["id"] for s in sessions]
    assert created_id in ids


@pytest.mark.e2e
def test_filter_sessions_by_tag(http, api_url: str, unique_tag: str) -> None:
    http.post(f"{api_url}/sessions", json={"minutes": 15, "tag": unique_tag})

    response = http.get(f"{api_url}/sessions", params={"tag": unique_tag})
    assert response.status_code == 200
    sessions = response.json()
    assert len(sessions) == 1
    assert sessions[0]["minutes"] == 15
    assert sessions[0]["tag"] == unique_tag


@pytest.mark.e2e
def test_filter_sessions_by_unknown_tag_returns_empty(http, api_url: str) -> None:
    nonexistent = f"never-{uuid.uuid4().hex}"
    response = http.get(f"{api_url}/sessions", params={"tag": nonexistent})
    assert response.status_code == 200
    assert response.json() == []

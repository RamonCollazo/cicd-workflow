"""POST /sessions: 422 on invalid payloads.

The API uses Pydantic with `extra="forbid"`, `minutes` constrained to
`1..1440`, and a tag validator that rejects empty/whitespace-only values.
"""

from __future__ import annotations

import pytest


@pytest.mark.e2e
@pytest.mark.parametrize("minutes", [0, -5])
def test_rejects_non_positive_minutes(http, api_url: str, minutes: int) -> None:
    response = http.post(
        f"{api_url}/sessions",
        json={"minutes": minutes, "tag": "irrelevant"},
    )
    assert response.status_code == 422


@pytest.mark.e2e
def test_rejects_minutes_above_max(http, api_url: str) -> None:
    response = http.post(
        f"{api_url}/sessions",
        json={"minutes": 1441, "tag": "irrelevant"},
    )
    assert response.status_code == 422


@pytest.mark.e2e
@pytest.mark.parametrize("tag", ["", "   "])
def test_rejects_empty_or_whitespace_tag(http, api_url: str, tag: str) -> None:
    response = http.post(
        f"{api_url}/sessions",
        json={"minutes": 10, "tag": tag},
    )
    assert response.status_code == 422


@pytest.mark.e2e
def test_rejects_extra_fields(http, api_url: str) -> None:
    response = http.post(
        f"{api_url}/sessions",
        json={"minutes": 10, "tag": "valid", "foo": "bar"},
    )
    assert response.status_code == 422

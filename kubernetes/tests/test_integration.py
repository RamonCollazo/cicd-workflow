"""End-to-end integration: web form submission persists through to the API.

These tests don't scrape HTML beyond the page-title assertion; the
substantive check is that posting the web form ultimately results in a
session being readable from the API by tag.
"""

from __future__ import annotations

import pytest


@pytest.mark.e2e
def test_index_page_loads(http, web_url: str) -> None:
    response = http.get(f"{web_url}/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("Content-Type", "")
    assert b"Study Tracker" in response.content


@pytest.mark.e2e
def test_add_session_via_web_persists_via_api(
    http,
    web_url: str,
    api_url: str,
    unique_tag: str,
) -> None:
    # POST the form. The web app responds with 302 -> /; allow_redirects
    # is on by default for requests, so we land on the index page (200).
    submit = http.post(
        f"{web_url}/add_session",
        data={"minutes": 42, "tag": unique_tag},
    )
    assert submit.status_code == 200, "expected 200 after redirect to /"

    # Now read it back via the API directly.
    response = http.get(f"{api_url}/sessions", params={"tag": unique_tag})
    assert response.status_code == 200
    sessions = response.json()

    assert len(sessions) == 1, f"expected exactly 1 session, got {sessions!r}"
    assert sessions[0]["minutes"] == 42
    assert sessions[0]["tag"] == unique_tag

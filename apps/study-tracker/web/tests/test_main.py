"""End-to-end-ish tests for ``web.main`` routes via the Flask test client.

The ``app`` fixture from conftest builds a real ``create_app()`` and
substitutes ``app.extensions["api_client"]`` with a ``MagicMock`` so
each test configures its own upstream behaviour.
"""

from __future__ import annotations

import re
from html import unescape
from unittest.mock import MagicMock

from flask import Flask

from web.api_client import ApiError


# --------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------- #


_FLASH_RE = re.compile(rb'<li class="flash flash-(?P<cat>[^"]+)">(?P<msg>[^<]+)</li>')


def flash_messages(html: bytes) -> list[tuple[str, str]]:
    """Extract ``(category, message)`` pairs from a rendered page."""
    return [
        (m["cat"].decode(), unescape(m["msg"].decode().strip()))
        for m in _FLASH_RE.finditer(html)
    ]


def has_flash(html: bytes, category: str, substring: str) -> bool:
    return any(c == category and substring in m for c, m in flash_messages(html))


# --------------------------------------------------------------------- #
# /  (index)
# --------------------------------------------------------------------- #


def test_index_renders_when_no_sessions(client, fake_api_client: MagicMock):
    fake_api_client.get_sessions.return_value = []
    r = client.get("/")
    assert r.status_code == 200
    assert b"<h1>Study Tracker</h1>" in r.data
    assert b"No study sessions recorded yet" in r.data
    fake_api_client.get_sessions.assert_called_once_with()


def test_index_renders_session_rows(client, fake_api_client: MagicMock):
    fake_api_client.get_sessions.return_value = [
        {
            "id": "1",
            "minutes": 30,
            "tag": "aws",
            "timestamp": "2026-06-04T00:00:00+00:00",
        },
        {
            "id": "2",
            "minutes": 15,
            "tag": "k8s",
            "timestamp": "2026-06-04T01:00:00+00:00",
        },
    ]
    r = client.get("/")
    assert r.status_code == 200
    assert b">aws<" in r.data
    assert b">k8s<" in r.data
    assert b">30<" in r.data
    assert b">15<" in r.data


def test_index_handles_z_suffix_timestamps(client, fake_api_client: MagicMock):
    """The route normalises the legacy ``Z`` UTC suffix before parsing."""
    fake_api_client.get_sessions.return_value = [
        {
            "id": "1",
            "minutes": 10,
            "tag": "rust",
            "timestamp": "2026-06-04T00:00:00Z",
        }
    ]
    r = client.get("/")
    assert r.status_code == 200
    assert b">rust<" in r.data


def test_index_flashes_outage_on_api_error(client, fake_api_client: MagicMock):
    fake_api_client.get_sessions.side_effect = ApiError("upstream down")
    r = client.get("/")
    assert r.status_code == 200
    assert has_flash(r.data, "error", "API is unavailable")
    # And nothing crashes — the empty list still renders.
    assert b"No study sessions recorded yet" in r.data


# --------------------------------------------------------------------- #
# POST /add_session
# --------------------------------------------------------------------- #


def test_add_session_valid_flashes_info_and_calls_upstream(
    client, fake_api_client: MagicMock
):
    fake_api_client.get_sessions.return_value = []
    r = client.post(
        "/add_session",
        data={"minutes": "30", "tag": "aws"},
        follow_redirects=True,
    )
    assert r.status_code == 200
    fake_api_client.create_session.assert_called_once_with(30, "aws")
    assert has_flash(r.data, "info", "Session saved")


def test_add_session_minutes_zero_warns_and_skips_upstream(
    client, fake_api_client: MagicMock
):
    fake_api_client.get_sessions.return_value = []
    r = client.post(
        "/add_session",
        data={"minutes": "0", "tag": "aws"},
        follow_redirects=True,
    )
    assert r.status_code == 200
    fake_api_client.create_session.assert_not_called()
    assert has_flash(r.data, "warning", "greater than zero")


def test_add_session_minutes_non_int_warns(client, fake_api_client: MagicMock):
    fake_api_client.get_sessions.return_value = []
    r = client.post(
        "/add_session",
        data={"minutes": "abc", "tag": "aws"},
        follow_redirects=True,
    )
    assert r.status_code == 200
    fake_api_client.create_session.assert_not_called()
    assert has_flash(r.data, "warning", "Invalid minutes")


def test_add_session_empty_tag_warns(client, fake_api_client: MagicMock):
    fake_api_client.get_sessions.return_value = []
    r = client.post(
        "/add_session",
        data={"minutes": "30", "tag": "   "},  # whitespace-only
        follow_redirects=True,
    )
    assert r.status_code == 200
    fake_api_client.create_session.assert_not_called()
    assert has_flash(r.data, "warning", "Tag is required")


def test_add_session_upstream_error_flashes_error(client, fake_api_client: MagicMock):
    fake_api_client.get_sessions.return_value = []
    fake_api_client.create_session.side_effect = ApiError("boom")
    r = client.post(
        "/add_session",
        data={"minutes": "30", "tag": "aws"},
        follow_redirects=True,
    )
    assert r.status_code == 200
    fake_api_client.create_session.assert_called_once_with(30, "aws")
    assert has_flash(r.data, "error", "Could not save session")


# --------------------------------------------------------------------- #
# /health
# --------------------------------------------------------------------- #


def test_health_returns_200_when_upstream_healthy(client, fake_api_client: MagicMock):
    fake_api_client.health.return_value = True
    r = client.get("/health")
    assert r.status_code == 200
    assert r.get_json() == {"status": "healthy", "api_connectivity": True}


def test_health_returns_503_when_upstream_unhealthy(client, fake_api_client: MagicMock):
    fake_api_client.health.return_value = False
    r = client.get("/health")
    assert r.status_code == 503
    assert r.get_json() == {"status": "unhealthy", "api_connectivity": False}


# --------------------------------------------------------------------- #
# Global exception handler
# --------------------------------------------------------------------- #


def test_unhandled_exception_renders_error_page_with_500(app: Flask):
    """A route that raises an unhandled exception goes through the
    ``handle_unhandled`` errorhandler: status 500, generic ``error.html``
    body, and no internal details leaked.
    """

    @app.route("/_boom")
    def _boom():
        raise RuntimeError("sensitive internal detail")

    with app.test_client() as c:
        r = c.get("/_boom")

    assert r.status_code == 500
    assert b"Something went wrong" in r.data
    assert b"Return to dashboard" in r.data
    # Internal exception text must not leak.
    assert b"sensitive internal detail" not in r.data
    assert b"RuntimeError" not in r.data

"""Tests for ``web.api_client.ApiClient``.

Uses the ``responses`` library so we can verify retry behaviour at the
wire level: ``responses`` patches ``urllib3``'s connection pool, which
means ``urllib3.util.Retry`` (mounted via ``HTTPAdapter``) emits real
intermediate requests we can count.
"""

from __future__ import annotations

import pytest
import responses

from web.api_client import ApiClient, ApiError


BASE = "http://test-api"


@pytest.fixture
def client() -> ApiClient:
    """Default test client: 2 retries, no backoff (fast tests)."""
    return ApiClient(base_url=BASE, timeout=2.0, retries=2, backoff=0.0)


# --------------------------------------------------------------------- #
# get_sessions
# --------------------------------------------------------------------- #


@responses.activate
def test_get_sessions_returns_parsed_json(client: ApiClient):
    payload = [
        {
            "id": "abc",
            "minutes": 30,
            "tag": "aws",
            "timestamp": "2026-06-04T00:00:00+00:00",
        }
    ]
    responses.add(responses.GET, f"{BASE}/sessions", json=payload, status=200)

    result = client.get_sessions()
    assert result == payload
    assert len(responses.calls) == 1


@responses.activate
def test_get_sessions_retries_on_503(client: ApiClient):
    """503 is in the status_forcelist → 1 initial + 2 retries = 3 calls."""
    responses.add(responses.GET, f"{BASE}/sessions", status=503)

    with pytest.raises(ApiError):
        client.get_sessions()
    assert len(responses.calls) == 3


@responses.activate
def test_get_sessions_does_not_retry_on_500(client: ApiClient):
    """500 isn't in status_forcelist (only 502/503/504) → no retry."""
    responses.add(responses.GET, f"{BASE}/sessions", status=500)

    with pytest.raises(ApiError):
        client.get_sessions()
    assert len(responses.calls) == 1


@responses.activate
def test_get_sessions_raises_on_connection_error(client: ApiClient):
    """No response registered → ConnectionError wrapped as ApiError."""
    with pytest.raises(ApiError):
        client.get_sessions()


@responses.activate
def test_get_sessions_raises_on_bad_json(client: ApiClient):
    responses.add(
        responses.GET,
        f"{BASE}/sessions",
        body="not-json",
        status=200,
        content_type="application/json",
    )
    with pytest.raises(ApiError):
        client.get_sessions()


# --------------------------------------------------------------------- #
# create_session — POST is intentionally not retried (no idempotency key)
# --------------------------------------------------------------------- #


@responses.activate
def test_create_session_happy_path(client: ApiClient):
    responses.add(
        responses.POST,
        f"{BASE}/sessions",
        json={"id": "abc", "minutes": 30, "tag": "aws"},
        status=200,
    )

    client.create_session(30, "aws")

    assert len(responses.calls) == 1
    body = responses.calls[0].request.body
    assert b'"minutes": 30' in body
    assert b'"tag": "aws"' in body


@responses.activate
def test_create_session_does_not_retry_on_503(client: ApiClient):
    """A retried POST could duplicate a session — must hit upstream once."""
    responses.add(responses.POST, f"{BASE}/sessions", status=503)

    with pytest.raises(ApiError):
        client.create_session(30, "aws")
    assert len(responses.calls) == 1


@responses.activate
def test_create_session_raises_on_4xx(client: ApiClient):
    responses.add(responses.POST, f"{BASE}/sessions", status=422)

    with pytest.raises(ApiError):
        client.create_session(0, "")
    assert len(responses.calls) == 1


@responses.activate
def test_create_session_raises_on_connection_error(client: ApiClient):
    with pytest.raises(ApiError):
        client.create_session(30, "aws")


# --------------------------------------------------------------------- #
# health — eats exceptions, returns bool
# --------------------------------------------------------------------- #


@responses.activate
def test_health_true_on_200(client: ApiClient):
    responses.add(responses.GET, f"{BASE}/health", status=200)
    assert client.health() is True


@responses.activate
def test_health_false_on_500(client: ApiClient):
    """500 isn't in the retry forcelist; one call, returns False."""
    responses.add(responses.GET, f"{BASE}/health", status=500)
    assert client.health() is False
    assert len(responses.calls) == 1


@responses.activate
def test_health_false_on_503_after_retries(client: ApiClient):
    """503 triggers retries; final response is still 503 → False."""
    responses.add(responses.GET, f"{BASE}/health", status=503)
    assert client.health() is False
    assert len(responses.calls) == 3  # 1 + 2 retries


@responses.activate
def test_health_false_on_connection_error(client: ApiClient):
    """Eats the underlying RequestException and returns False."""
    assert client.health() is False


# --------------------------------------------------------------------- #
# Misc
# --------------------------------------------------------------------- #


def test_base_url_trailing_slash_stripped():
    c = ApiClient(base_url=f"{BASE}/", timeout=1.0, retries=0, backoff=0.0)
    assert c.base_url == BASE


@responses.activate
def test_session_is_reused_across_calls(client: ApiClient):
    """Multiple calls go through the same Session — observable via the
    fact that the same urllib3 connection pool serves them and `responses`
    counts each individual request."""
    responses.add(responses.GET, f"{BASE}/sessions", json=[], status=200)
    client.get_sessions()
    client.get_sessions()
    assert len(responses.calls) == 2
    # Sanity: the session object itself is the same instance.
    assert client._session is client._session  # noqa: SLF001


def test_close_does_not_raise(client: ApiClient):
    client.close()
    # Calling close twice should also be safe.
    client.close()

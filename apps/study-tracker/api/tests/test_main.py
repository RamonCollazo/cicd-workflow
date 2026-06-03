"""End-to-end-ish tests for ``api.main`` via httpx ASGI transport.

The autouse ``isolated_data_dir`` fixture (conftest) gives every test a
fresh data dir. Because ``api.main`` binds ``settings`` and the FastAPI
app at import time, the title/version/CORS values reflect whatever was
in the env when the module was first imported — that's fine, those
aren't what we're testing here. What we exercise is request handling
end-to-end: routes, validation, the global exception handler.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from api.main import app
from api.models import StudySessionCreate
from api.storage import save_session


# --------------------------------------------------------------------- #
# Test client fixtures
# --------------------------------------------------------------------- #


@pytest_asyncio.fixture
async def client():
    """Default async client — app exceptions propagate to the framework's
    exception handler (i.e. our global one returns a 500)."""
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def strict_client():
    """Variant with ``raise_app_exceptions=True`` for tests that want to
    catch raw exceptions instead of HTTP responses (not used here, but
    handy for debugging)."""
    transport = ASGITransport(app=app, raise_app_exceptions=True)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# --------------------------------------------------------------------- #
# Root + health
# --------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_root(client: AsyncClient):
    r = await client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["message"].endswith("API")  # "<app_name> API"
    assert "version" in body


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "healthy"}


# --------------------------------------------------------------------- #
# POST /sessions
# --------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_create_session_returns_normalized_payload(client: AsyncClient):
    r = await client.post("/sessions", json={"minutes": 30, "tag": "AWS"})
    assert r.status_code == 200
    body = r.json()
    assert body["minutes"] == 30
    assert body["tag"] == "aws"  # normalized lowercase
    assert "id" in body
    assert "timestamp" in body


@pytest.mark.asyncio
async def test_create_session_rejects_invalid_minutes(client: AsyncClient):
    # minutes must be > 0
    r = await client.post("/sessions", json={"minutes": 0, "tag": "aws"})
    assert r.status_code == 422

    # minutes must be <= 1440 (24h)
    r = await client.post("/sessions", json={"minutes": 1441, "tag": "aws"})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_session_rejects_empty_tag(client: AsyncClient):
    r = await client.post("/sessions", json={"minutes": 10, "tag": ""})
    assert r.status_code == 422

    r = await client.post("/sessions", json={"minutes": 10, "tag": "   "})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_session_rejects_extra_fields(client: AsyncClient):
    """``StudySessionCreate`` has ``extra='forbid'``."""
    r = await client.post(
        "/sessions",
        json={"minutes": 10, "tag": "aws", "rogue": True},
    )
    assert r.status_code == 422


# --------------------------------------------------------------------- #
# GET /sessions
# --------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_read_sessions_empty(client: AsyncClient):
    r = await client.get("/sessions")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_read_sessions_returns_all(client: AsyncClient):
    save_session(StudySessionCreate(minutes=25, tag="kubernetes"))
    save_session(StudySessionCreate(minutes=50, tag="aws"))

    r = await client.get("/sessions")
    assert r.status_code == 200
    data = r.json()
    assert [item["tag"] for item in data] == ["kubernetes", "aws"]
    assert [item["minutes"] for item in data] == [25, 50]


@pytest.mark.asyncio
async def test_read_sessions_filtered_by_tag(client: AsyncClient):
    save_session(StudySessionCreate(minutes=25, tag="kubernetes"))
    save_session(StudySessionCreate(minutes=50, tag="aws"))
    save_session(StudySessionCreate(minutes=15, tag="Kubernetes"))  # normalized

    r = await client.get("/sessions", params={"tag": "kubernetes"})
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    assert all(item["tag"] == "kubernetes" for item in data)

    r = await client.get("/sessions", params={"tag": "aws"})
    assert r.status_code == 200
    assert len(r.json()) == 1

    r = await client.get("/sessions", params={"tag": "nonexistent"})
    assert r.status_code == 200
    assert r.json() == []


# --------------------------------------------------------------------- #
# GET /stats
# --------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_read_stats_empty(client: AsyncClient):
    r = await client.get("/stats")
    assert r.status_code == 200
    assert r.json() == {
        "total_time": 0,
        "time_by_tag": {},
        "total_sessions": 0,
        "sessions_by_tag": {},
    }


@pytest.mark.asyncio
async def test_read_stats_aggregates(client: AsyncClient):
    save_session(StudySessionCreate(minutes=25, tag="kubernetes"))
    save_session(StudySessionCreate(minutes=50, tag="aws"))
    save_session(StudySessionCreate(minutes=15, tag="kubernetes"))

    r = await client.get("/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["total_sessions"] == 3
    assert body["total_time"] == 90
    assert body["time_by_tag"] == {"kubernetes": 40, "aws": 50}
    assert body["sessions_by_tag"] == {"kubernetes": 2, "aws": 1}


# --------------------------------------------------------------------- #
# Global exception handler
# --------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_unhandled_exception_returns_generic_500(
    client: AsyncClient, monkeypatch
):
    """Storage failures bubble into the global handler, which returns a
    sanitized 500 (no internal error details in the body)."""

    def boom(*args, **kwargs):
        raise RuntimeError("internal storage failure with sensitive details")

    # Patch the symbol the route imports, not the storage module.
    monkeypatch.setattr("api.main.save_session", boom)

    r = await client.post("/sessions", json={"minutes": 10, "tag": "aws"})
    assert r.status_code == 500
    assert r.json() == {"detail": "Internal server error"}
    # Sanity: the secret detail is NOT leaked.
    assert "sensitive" not in r.text


@pytest.mark.asyncio
async def test_unhandled_exception_on_get_sessions(client: AsyncClient, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("read failure")

    monkeypatch.setattr("api.main.get_all_sessions", boom)

    r = await client.get("/sessions")
    assert r.status_code == 500
    assert r.json() == {"detail": "Internal server error"}


@pytest.mark.asyncio
async def test_unhandled_exception_on_stats(client: AsyncClient, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("stats failure")

    monkeypatch.setattr("api.main.get_statistics", boom)

    r = await client.get("/stats")
    assert r.status_code == 500
    assert r.json() == {"detail": "Internal server error"}

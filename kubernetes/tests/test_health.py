"""Health and root-endpoint checks for both api and web services."""

from __future__ import annotations

import pytest


@pytest.mark.e2e
def test_api_health_returns_healthy(http, api_url: str) -> None:
    response = http.get(f"{api_url}/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


@pytest.mark.e2e
def test_api_root_returns_metadata(http, api_url: str) -> None:
    response = http.get(f"{api_url}/")
    assert response.status_code == 200
    body = response.json()
    assert "message" in body
    assert "version" in body
    # API title comes from Settings.app_name; the response includes it in `message`.
    assert "Study Tracker" in body["message"]


@pytest.mark.e2e
def test_web_health_reports_api_connectivity(http, web_url: str) -> None:
    response = http.get(f"{web_url}/health")
    assert response.status_code == 200
    body = response.json()
    assert body == {"status": "healthy", "api_connectivity": True}

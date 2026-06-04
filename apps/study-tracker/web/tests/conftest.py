"""Pytest fixtures for the web frontend test suite.

The autouse ``_clear_settings_cache`` resets ``get_settings``'s
``lru_cache`` around every test so env-driven config never bleeds
across tests. The ``_stable_env`` fixture is opt-in (used by ``app``
and ``client``) so config-focused tests can manipulate env freely.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from flask import Flask

from web.api_client import ApiClient
from web.config import get_settings
from web.main import create_app


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    """Clear the ``get_settings`` cache around every test."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def _stable_env(monkeypatch):
    """Set safe defaults for tests that build a Flask app.

    Tests in ``test_config.py`` opt out of this fixture so they can
    exercise env-derived config in isolation.
    """
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("API_URL", "http://test-api")
    monkeypatch.setenv("API_TIMEOUT", "1")
    monkeypatch.setenv("API_RETRIES", "0")
    monkeypatch.setenv("API_RETRY_BACKOFF", "0")
    # Make sure cache reflects the stable env.
    get_settings.cache_clear()


@pytest.fixture
def fake_api_client() -> MagicMock:
    """A ``MagicMock`` conforming to the ``ApiClient`` public surface.

    Using ``spec=ApiClient`` ensures attribute typos in tests fail
    loudly instead of silently returning ``MagicMock`` instances.
    """
    return MagicMock(spec=ApiClient)


@pytest.fixture
def app(_stable_env, fake_api_client: MagicMock) -> Flask:
    """Fresh Flask app per test, with the upstream client substituted."""
    application = create_app()
    application.extensions["api_client"] = fake_api_client
    return application


@pytest.fixture
def client(app: Flask):
    """Flask test client backed by the per-test app."""
    return app.test_client()

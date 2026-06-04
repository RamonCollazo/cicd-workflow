"""Tests for ``web.config.Settings``."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from web.config import DEV_INSECURE_SECRET_KEY, get_settings


# All web env vars Settings reads. We strip them before each test so the
# defaults case is reproducible regardless of the developer's shell.
_WEB_ENV_VARS = (
    "APP_NAME",
    "API_URL",
    "API_TIMEOUT",
    "API_RETRIES",
    "API_RETRY_BACKOFF",
    "FRONTEND_HOST",
    "FRONTEND_PORT",
    "FLASK_DEBUG",
    "SECRET_KEY",
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Strip web env vars before each test in this module."""
    for var in _WEB_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# --------------------------------------------------------------------- #
# Defaults
# --------------------------------------------------------------------- #


def test_defaults_match_documented_values():
    s = get_settings()
    assert s.app_name == "Study Tracker"
    assert s.api_url == "http://localhost:3001"
    assert s.api_timeout == 5
    assert s.api_retries == 3
    assert s.api_retry_backoff == 0.3
    assert s.frontend_host == "0.0.0.0"
    assert s.frontend_port == 3000
    assert s.debug is False
    assert s.secret_key == DEV_INSECURE_SECRET_KEY


# --------------------------------------------------------------------- #
# Env overrides
# --------------------------------------------------------------------- #


def test_env_overrides_round_trip(monkeypatch):
    monkeypatch.setenv("APP_NAME", "Custom Tracker")
    monkeypatch.setenv("API_URL", "http://upstream:9999")
    monkeypatch.setenv("API_TIMEOUT", "10")
    monkeypatch.setenv("API_RETRIES", "5")
    monkeypatch.setenv("API_RETRY_BACKOFF", "1.5")
    monkeypatch.setenv("FRONTEND_HOST", "127.0.0.1")
    monkeypatch.setenv("FRONTEND_PORT", "8080")
    monkeypatch.setenv("SECRET_KEY", "real-secret")
    get_settings.cache_clear()

    s = get_settings()
    assert s.app_name == "Custom Tracker"
    assert s.api_url == "http://upstream:9999"
    assert s.api_timeout == 10
    assert s.api_retries == 5
    assert s.api_retry_backoff == 1.5
    assert s.frontend_host == "127.0.0.1"
    assert s.frontend_port == 8080
    assert s.secret_key == "real-secret"


def test_flask_debug_alias_populates_debug(monkeypatch):
    """The historical env var is FLASK_DEBUG, not DEBUG."""
    monkeypatch.setenv("FLASK_DEBUG", "true")
    get_settings.cache_clear()
    assert get_settings().debug is True


def test_debug_alias_accepts_falsy_strings(monkeypatch):
    monkeypatch.setenv("FLASK_DEBUG", "false")
    get_settings.cache_clear()
    assert get_settings().debug is False


# --------------------------------------------------------------------- #
# Validators
# --------------------------------------------------------------------- #


def test_api_timeout_must_be_positive(monkeypatch):
    monkeypatch.setenv("API_TIMEOUT", "0")
    get_settings.cache_clear()
    with pytest.raises(ValidationError):
        get_settings()


def test_api_timeout_upper_bound(monkeypatch):
    monkeypatch.setenv("API_TIMEOUT", "301")
    get_settings.cache_clear()
    with pytest.raises(ValidationError):
        get_settings()


def test_frontend_port_range(monkeypatch):
    monkeypatch.setenv("FRONTEND_PORT", "70000")
    get_settings.cache_clear()
    with pytest.raises(ValidationError):
        get_settings()


def test_api_retries_range(monkeypatch):
    monkeypatch.setenv("API_RETRIES", "11")
    get_settings.cache_clear()
    with pytest.raises(ValidationError):
        get_settings()


def test_api_retry_backoff_must_be_non_negative(monkeypatch):
    monkeypatch.setenv("API_RETRY_BACKOFF", "-0.1")
    get_settings.cache_clear()
    with pytest.raises(ValidationError):
        get_settings()


def test_api_retry_backoff_upper_bound(monkeypatch):
    monkeypatch.setenv("API_RETRY_BACKOFF", "10.5")
    get_settings.cache_clear()
    with pytest.raises(ValidationError):
        get_settings()


# --------------------------------------------------------------------- #
# Caching
# --------------------------------------------------------------------- #


def test_get_settings_is_cached():
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2

    get_settings.cache_clear()
    s3 = get_settings()
    assert s3 is not s1

"""Tests for ``api.config.Settings``."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from api.config import Settings, get_settings


# --------------------------------------------------------------------- #
# Defaults
# --------------------------------------------------------------------- #


def test_defaults(monkeypatch, tmp_path):
    """Default values match what api.main relies on at startup."""
    # The autouse isolated_data_dir fixture sets DATA_DIR to tmp_path,
    # so we expect data_dir to point there. Everything else uses code
    # defaults (no env overrides).
    for env_var in (
        "APP_NAME",
        "API_HOST",
        "API_PORT",
        "RELOAD",
        "CORS_ALLOW_ORIGINS",
        "CORS_ALLOW_METHODS",
        "CORS_ALLOW_HEADERS",
        "CORS_ALLOW_CREDENTIALS",
    ):
        monkeypatch.delenv(env_var, raising=False)
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.app_name == "Study Tracker"
    assert settings.api_host == "0.0.0.0"
    assert settings.api_port == 3001
    assert settings.reload is False
    assert settings.data_dir == tmp_path

    # CORS defaults
    assert settings.cors_allow_origins == ["*"]
    assert settings.cors_allow_methods == ["*"]
    assert settings.cors_allow_headers == ["*"]
    assert settings.cors_allow_credentials is False


# --------------------------------------------------------------------- #
# Env var loading
# --------------------------------------------------------------------- #


def test_env_overrides(monkeypatch):
    """Env vars override defaults (case-insensitive)."""
    monkeypatch.setenv("APP_NAME", "Custom Tracker")
    monkeypatch.setenv("API_HOST", "127.0.0.1")
    monkeypatch.setenv("API_PORT", "9000")
    monkeypatch.setenv(
        "CORS_ALLOW_ORIGINS",
        "https://example.com,https://api.example.com",
    )
    monkeypatch.setenv("CORS_ALLOW_METHODS", "GET,POST,PUT")
    monkeypatch.setenv("CORS_ALLOW_HEADERS", "Content-Type,Authorization")
    monkeypatch.setenv("CORS_ALLOW_CREDENTIALS", "true")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.app_name == "Custom Tracker"
    assert settings.api_host == "127.0.0.1"
    assert settings.api_port == 9000
    assert settings.cors_allow_origins == [
        "https://example.com",
        "https://api.example.com",
    ]
    assert settings.cors_allow_methods == ["GET", "POST", "PUT"]
    assert settings.cors_allow_headers == ["Content-Type", "Authorization"]
    assert settings.cors_allow_credentials is True


# --------------------------------------------------------------------- #
# CSV-list validator
# --------------------------------------------------------------------- #


def test_cors_list_wildcard_string(monkeypatch):
    """A bare '*' string env value is parsed as ['*']."""
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", "*")
    get_settings.cache_clear()
    assert get_settings().cors_allow_origins == ["*"]


def test_cors_list_strips_and_drops_empty(monkeypatch):
    """CSV parser strips whitespace and drops empty items."""
    monkeypatch.setenv("CORS_ALLOW_METHODS", " GET , , POST ,, ")
    get_settings.cache_clear()
    assert get_settings().cors_allow_methods == ["GET", "POST"]


def test_cors_list_accepts_native_list():
    """Direct construction with a list value passes the validator unchanged."""
    settings = Settings(cors_allow_headers=["X-Custom"])
    assert settings.cors_allow_headers == ["X-Custom"]


# --------------------------------------------------------------------- #
# Validators
# --------------------------------------------------------------------- #


def test_api_port_range(monkeypatch):
    """API_PORT outside 1..65535 fails validation."""
    monkeypatch.setenv("API_PORT", "70000")
    get_settings.cache_clear()
    with pytest.raises(ValidationError):
        get_settings()


def test_wildcard_origin_with_credentials_rejected():
    """The browser-rejected combo (origins=['*'] + credentials=True) raises."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            cors_allow_origins=["*"],
            cors_allow_credentials=True,
        )
    assert "CORS misconfiguration" in str(exc_info.value)


def test_explicit_origins_with_credentials_ok():
    """Explicit origins + credentials=True is allowed."""
    settings = Settings(
        cors_allow_origins=["https://example.com"],
        cors_allow_credentials=True,
    )
    assert settings.cors_allow_credentials is True


# --------------------------------------------------------------------- #
# get_settings caching
# --------------------------------------------------------------------- #


def test_get_settings_is_cached():
    """``get_settings`` returns the same instance until the cache is cleared."""
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2

    get_settings.cache_clear()
    s3 = get_settings()
    assert s3 is not s1

"""Application configuration via pydantic-settings.

Settings are loaded from environment variables. Existing env var names
(API_URL, API_TIMEOUT, FRONTEND_HOST, FRONTEND_PORT, FLASK_DEBUG,
SECRET_KEY) are preserved case-insensitively.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Sentinel used to detect when no SECRET_KEY was supplied; main() emits a
# warning and create_app() also warns so operators know they're running
# with an insecure default.
DEV_INSECURE_SECRET_KEY = "dev-insecure-change-me"  # nosec B105


class Settings(BaseSettings):
    """Typed, validated web frontend settings."""

    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False)

    # Application
    app_name: str = "Study Tracker"

    # Upstream API
    api_url: str = "http://localhost:3001"
    api_timeout: int = Field(default=5, gt=0, le=300)
    api_retries: int = Field(default=3, ge=0, le=10)
    api_retry_backoff: float = Field(default=0.3, ge=0.0, le=10.0)

    # Web server
    # Binding to all interfaces is intentional: the service runs inside a
    # container and must be reachable from outside it.
    frontend_host: str = "0.0.0.0"  # nosec B104
    frontend_port: int = Field(default=3000, ge=1, le=65535)

    # Flask
    debug: bool = Field(default=False, validation_alias="FLASK_DEBUG")
    secret_key: str = DEV_INSECURE_SECRET_KEY


@lru_cache
def get_settings() -> Settings:
    """Return a process-wide cached Settings instance."""
    return Settings()

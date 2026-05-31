"""Application configuration via pydantic-settings.

Settings are loaded from environment variables. Existing env var names
(APP_NAME, API_HOST, API_PORT, DATA_DIR, CORS_ALLOW_*) are preserved
case-insensitively.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed, validated application settings."""

    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False)

    # Application
    app_name: str = "Study Tracker"

    # API server
    api_host: str = "0.0.0.0"
    api_port: int = Field(default=3001, ge=1, le=65535)
    reload: bool = False

    # Storage
    data_dir: Path = Path("./data")

    # CORS
    cors_allow_origins: list[str] = ["*"]
    cors_allow_methods: list[str] = ["*"]
    cors_allow_headers: list[str] = ["*"]
    cors_allow_credentials: bool = False

    @field_validator(
        "cors_allow_origins",
        "cors_allow_methods",
        "cors_allow_headers",
        mode="before",
    )
    @classmethod
    def _parse_csv_list(cls, v: object) -> list[str]:
        """Parse comma-separated env strings into lists.

        Accepts: a list (returned as-is), "*" (-> ["*"]), or a CSV string
        (-> stripped, non-empty items).
        """
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            if v.strip() == "*":
                return ["*"]
            return [item.strip() for item in v.split(",") if item.strip()]
        raise TypeError(f"Expected str or list, got {type(v).__name__}")

    @model_validator(mode="after")
    def _validate_cors_combo(self) -> "Settings":
        """Reject the wildcard-origins + credentials combo (browsers reject it)."""
        if self.cors_allow_origins == ["*"] and self.cors_allow_credentials:
            raise ValueError(
                "CORS misconfiguration: cors_allow_origins=['*'] cannot be combined "
                "with cors_allow_credentials=True. Either set explicit origins or "
                "set CORS_ALLOW_CREDENTIALS=false."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Return a process-wide cached Settings instance."""
    return Settings()

"""Typed configuration and secrets management via pydantic-settings."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "GeoResilience-NER 2.0 Environmental Data API"
    app_version: str = "2.0.0-alpha.1"
    app_env: str = Field(default="development", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # PostgreSQL + PostGIS default for Docker Compose; override with sqlite:/// for isolated unit tests
    database_url: str = Field(
        default="postgresql+psycopg://geos:geos_dev_password@localhost:5432/geos_ner",
        alias="DATABASE_URL",
    )

    pilot_data_dir: Path = Field(
        default=BACKEND_ROOT / "data" / "pilot",
        alias="PILOT_DATA_DIR",
    )

    cors_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        alias="CORS_ORIGINS",
    )

    # Optional external secrets (never hardcoded; never logged)
    gemini_api_key: SecretStr | None = Field(default=None, alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-4-hydrogen", alias="GEMINI_MODEL")
    nasa_earthdata_token: SecretStr | None = Field(default=None, alias="NASA_EARTHDATA_TOKEN")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

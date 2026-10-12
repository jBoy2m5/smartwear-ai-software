"""Environment-backed application configuration."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


BACKEND_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseModel):
    """Validated runtime settings for the backend process."""

    model_config = ConfigDict(frozen=True)

    app_name: str = "SmartWear AI Backend"
    environment: Literal["development", "test", "production"] = "development"
    api_prefix: str = "/api/v1"
    database_url: str = f"sqlite:///{(BACKEND_ROOT / 'data' / 'smartwear.db').as_posix()}"
    static_dir: Path = BACKEND_ROOT / "static"
    pdf_dir: Path = BACKEND_ROOT / "static" / "pdf"
    keyframe_dir: Path = BACKEND_ROOT / "static" / "images"
    dataset_dir: Path = BACKEND_ROOT / "static" / "dataset"
    api_key: str | None = None
    cors_origins: tuple[str, ...] = ("http://localhost:3000", "http://localhost:5173")
    log_level: str = "INFO"
    max_page_size: int = Field(default=100, ge=1, le=1_000)
    max_keyframe_bytes: int = Field(default=10 * 1024 * 1024, ge=1)

    @field_validator("api_prefix")
    @classmethod
    def validate_api_prefix(cls, value: str) -> str:
        """Require a normalized absolute API prefix."""
        if not value.startswith("/") or value.endswith("/"):
            raise ValueError("api_prefix must start with '/' and must not end with '/'")
        return value

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        """Normalize and validate the configured logging level."""
        normalized = value.upper()
        if normalized not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("unsupported log level")
        return normalized

    @model_validator(mode="after")
    def require_production_api_key(self) -> "Settings":
        """Prevent an unauthenticated production deployment."""
        if self.environment == "production" and not self.api_key:
            raise ValueError("SMARTWEAR_API_KEY is required in production")
        return self

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> "Settings":
        """Build settings from SMARTWEAR-prefixed environment variables."""
        source = os.environ if environ is None else environ
        values: dict[str, object] = {}
        mapping = {
            "SMARTWEAR_APP_NAME": "app_name",
            "SMARTWEAR_ENVIRONMENT": "environment",
            "SMARTWEAR_API_PREFIX": "api_prefix",
            "SMARTWEAR_DATABASE_URL": "database_url",
            "SMARTWEAR_STATIC_DIR": "static_dir",
            "SMARTWEAR_PDF_DIR": "pdf_dir",
            "SMARTWEAR_KEYFRAME_DIR": "keyframe_dir",
            "SMARTWEAR_DATASET_DIR": "dataset_dir",
            "SMARTWEAR_API_KEY": "api_key",
            "SMARTWEAR_LOG_LEVEL": "log_level",
            "SMARTWEAR_MAX_PAGE_SIZE": "max_page_size",
            "SMARTWEAR_MAX_KEYFRAME_BYTES": "max_keyframe_bytes",
        }
        for environment_name, field_name in mapping.items():
            if environment_name in source:
                values[field_name] = source[environment_name]

        if "SMARTWEAR_CORS_ORIGINS" in source:
            raw_origins = source["SMARTWEAR_CORS_ORIGINS"]
            try:
                parsed_origins = json.loads(raw_origins)
            except json.JSONDecodeError:
                parsed_origins = [item.strip() for item in raw_origins.split(",") if item.strip()]
            values["cors_origins"] = tuple(parsed_origins)
        return cls.model_validate(values)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings instance."""
    return Settings.from_environment()


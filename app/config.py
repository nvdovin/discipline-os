"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration.

    Secrets are never hardcoded: every value below can be overridden by an
    environment variable or by a local ``.env`` file.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Discipline OS"
    app_version: str = "1.0.0"
    environment: str = "development"
    log_level: str = "INFO"

    bot_token: str = ""
    owner_telegram_id: int | None = None
    webapp_url: str = ""

    database_url: str = "sqlite+aiosqlite:///./data/discipline.db"

    # Development escape hatch: allows opening the Mini App in a browser
    # without Telegram initData. MUST be false in production.
    dev_mode: bool = True
    enable_scheduler: bool = True
    init_data_max_age_seconds: int = 86400

    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = Field(default_factory=list)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

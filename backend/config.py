"""Application settings loaded from environment variables / .env file."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration sourced from ``backend/.env``."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    DATABASE_URL: str = (
        "postgresql+asyncpg://clauseguard:clauseguard@localhost:5432/clauseguard"
    )


# Module-level singleton — import this wherever settings are needed.
settings = Settings()

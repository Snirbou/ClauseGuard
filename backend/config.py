"""Application settings loaded from environment variables / .env file."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent

# Values that look like a key but are really the shipped placeholder from
# .env.example.  Treating these as "configured" would send doomed requests to
# OpenAI, so they are filtered out explicitly.
_PLACEHOLDER_API_KEYS = {
    "sk-your-openai-api-key-here",
    "sk-...",
    "changeme",
    "your-key-here",
}


class Settings(BaseSettings):
    """Central configuration sourced from ``backend/.env``."""

    model_config = SettingsConfigDict(
        # Absolute path so the backend behaves the same no matter which
        # directory uvicorn was launched from.
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        # pydantic-settings defaults to extra="forbid", which made *any*
        # unrecognised key in .env crash the app at import time.
        extra="ignore",
    )

    DATABASE_URL: str = (
        "postgresql+asyncpg://clauseguard:clauseguard@localhost:5432/clauseguard"
    )

    # --- LLM / DSPy -------------------------------------------------------
    OPENAI_API_KEY: str | None = None
    # "openai" | "ollama" | "fake"
    # "fake" runs a deterministic offline analyzer (see fake_llm.py): the
    # whole product works with zero API cost, and every summary is clearly
    # labeled as canned demo output.
    DSPY_PROVIDER: str = "openai"
    DSPY_MODEL: str = "gpt-4o-mini"
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # --- Analysis runs ------------------------------------------------------
    # Clauses analyzed concurrently within one run. Each holds a worker
    # thread for the duration of an LLM round-trip.
    ANALYZE_CONCURRENCY: int = 6
    # Attempts per clause before it is counted as failed for the run.
    ANALYZE_MAX_RETRIES: int = 3

    # --- Uploads ----------------------------------------------------------
    MAX_UPLOAD_BYTES: int = 10 * 1024 * 1024   # 10 MB

    # --- Pipeline behaviour ----------------------------------------------
    # Off by default: running the DSPy pass inline would make every upload
    # bill OpenAI and block the request for as long as the analysis takes.
    AUTO_ANALYZE_ON_UPLOAD: bool = False

    # --- CORS -------------------------------------------------------------
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # ------------------------------------------------------------------
    # Derived helpers
    # ------------------------------------------------------------------

    @property
    def openai_key_configured(self) -> bool:
        """True when OPENAI_API_KEY holds something other than a placeholder."""
        key = (self.OPENAI_API_KEY or "").strip()
        if not key or key in _PLACEHOLDER_API_KEYS:
            return False
        return not key.startswith("sk-your-")

    @property
    def llm_configured(self) -> bool:
        """True when the configured provider has everything it needs to run."""
        if self.DSPY_PROVIDER in ("ollama", "fake"):
            return True          # no API key required
        return self.openai_key_configured

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def max_upload_mb(self) -> float:
        return self.MAX_UPLOAD_BYTES / (1024 * 1024)


# Module-level singleton — import this wherever settings are needed.
settings = Settings()

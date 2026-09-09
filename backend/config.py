"""Application settings loaded from environment variables / .env file."""

from __future__ import annotations

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent


def normalize_database_url(url: str) -> str:
    """Rewrite a generic Postgres URL into SQLAlchemy's asyncpg form.

    Managed hosts (Railway, Heroku-style plugins) hand out ``postgres://`` or
    ``postgresql://``; SQLAlchemy needs ``postgresql+asyncpg://`` to select
    the async driver. A ``sslmode=`` query parameter (present on Railway's
    *public* connection string, absent on the private one) is renamed to
    ``ssl=``, which is what the asyncpg dialect understands. URLs that are
    already explicit pass through unchanged, so the function is idempotent.
    """
    value = (url or "").strip()
    for prefix in ("postgres://", "postgresql://"):
        if value.startswith(prefix):
            value = "postgresql+asyncpg://" + value[len(prefix):]
            break
    if "sslmode=" in value:
        value = value.replace("?sslmode=", "?ssl=").replace("&sslmode=", "&ssl=")
    return value

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

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _normalize_database_url(cls, value: object) -> object:
        return normalize_database_url(value) if isinstance(value, str) else value

    # --- Layer 1 classifier -------------------------------------------------
    # spaCy pipeline that serves the trained clause classifier. The artifact
    # was trained with en_core_web_lg but never uses word vectors, and the
    # ablation (ml_training/scripts/07_spacy_model_ablation.py, results in
    # models/clause_classifier_v1.spacy_ablation.json) measured a 0.001
    # macro-F1 cost for en_core_web_sm at a third of the memory — so the
    # small model is the served default. classifier.py exports this into the
    # environment before ml_inference/src/nlp_singleton.py reads it.
    SPACY_MODEL: str = "en_core_web_sm"

    # --- LLM / DSPy -------------------------------------------------------
    OPENAI_API_KEY: str | None = None
    # "auto" | "openai" | "ollama" | "fake"
    #   auto   — openai when a real OPENAI_API_KEY is set, otherwise the
    #            offline demo analyzer. Inserting a key is the only step
    #            needed to switch from demo output to real analysis.
    #   fake   — deterministic offline analyzer (fake_llm.py): zero API
    #            cost, every summary clearly labeled as canned demo output.
    DSPY_PROVIDER: str = "auto"
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

    # --- OCR (scanned PDFs) -------------------------------------------------
    # Pages with no digital text are rendered and passed to Tesseract, so a
    # scanned contract is analyzed instead of refused. OCR runs inside the
    # upload request (~1s per page at 200 dpi), which is why it is capped:
    # AC-API01 budgets that request a 5s p95, and a 40-page scan would blow
    # through it. Over the cap the upload is refused with a clear message.
    OCR_ENABLED: bool = True
    OCR_MAX_PAGES: int = 20
    OCR_DPI: int = 200

    # --- Pipeline behaviour ----------------------------------------------
    # Off by default: running the DSPy pass inline would make every upload
    # bill OpenAI and block the request for as long as the analysis takes.
    AUTO_ANALYZE_ON_UPLOAD: bool = False

    # --- Auth ---------------------------------------------------------------
    # Set true when the API is served over HTTPS; the session cookie then
    # carries the Secure attribute.
    SESSION_COOKIE_SECURE: bool = False

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
    def resolved_provider(self) -> str:
        """The provider actually in effect ("auto" resolved by key presence)."""
        if self.DSPY_PROVIDER == "auto":
            return "openai" if self.openai_key_configured else "fake"
        return self.DSPY_PROVIDER

    @property
    def llm_configured(self) -> bool:
        """True when the effective provider has everything it needs to run."""
        if self.resolved_provider in ("ollama", "fake"):
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

"""Settings hardening: DATABASE_URL normalisation for managed Postgres hosts.

Railway/Heroku-style plugins hand out ``postgres://`` connection strings;
SQLAlchemy needs the explicit ``postgresql+asyncpg://`` dialect. The
normaliser must be idempotent so explicit URLs (dev, CI) pass through.
"""

from __future__ import annotations

import pytest

from config import Settings, normalize_database_url


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("postgres://u:p@h:5432/db", "postgresql+asyncpg://u:p@h:5432/db"),
        ("postgresql://u:p@h:5432/db", "postgresql+asyncpg://u:p@h:5432/db"),
        ("postgresql+asyncpg://u:p@h:5432/db", "postgresql+asyncpg://u:p@h:5432/db"),
        (
            "postgres://u:p@h:5432/db?sslmode=require",
            "postgresql+asyncpg://u:p@h:5432/db?ssl=require",
        ),
        (
            "postgresql+asyncpg://u:p@h/db?x=1&sslmode=require",
            "postgresql+asyncpg://u:p@h/db?x=1&ssl=require",
        ),
        ("  postgres://u:p@h/db  ", "postgresql+asyncpg://u:p@h/db"),
    ],
)
def test_normalize_database_url(raw: str, expected: str) -> None:
    assert normalize_database_url(raw) == expected
    # Idempotent: normalising an already-normalised URL changes nothing.
    assert normalize_database_url(expected) == expected


def test_settings_apply_the_normalizer() -> None:
    s = Settings(_env_file=None, DATABASE_URL="postgres://u:p@h:5432/db")
    assert s.DATABASE_URL == "postgresql+asyncpg://u:p@h:5432/db"


def test_settings_default_is_already_normalised() -> None:
    s = Settings(_env_file=None, DATABASE_URL=Settings.model_fields["DATABASE_URL"].default)
    assert s.DATABASE_URL.startswith("postgresql+asyncpg://")


def test_spacy_model_setting_default() -> None:
    s = Settings(_env_file=None, SPACY_MODEL="en_core_web_sm")
    assert s.SPACY_MODEL == "en_core_web_sm"

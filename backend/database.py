"""Async SQLAlchemy engine, session factory, and declarative Base."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path

import anyio.to_thread
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from config import settings

# ---------------------------------------------------------------------------
# Engine & session factory
# ---------------------------------------------------------------------------

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    # Recycle dead connections instead of surfacing them as request errors,
    # which happens whenever the Postgres container restarts under the app.
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ---------------------------------------------------------------------------
# Declarative Base
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
    pass


# ---------------------------------------------------------------------------
# Dependency for FastAPI route injection
# ---------------------------------------------------------------------------

async def get_db() -> AsyncGenerator[AsyncSession]:
    """Yield an ``AsyncSession``, rolling back on error and always closing it."""
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            # Without this, a failed request can leave the connection inside an
            # aborted transaction and poison the next checkout from the pool.
            await session.rollback()
            raise


# ---------------------------------------------------------------------------
# Schema bootstrap — Alembic migrations
# ---------------------------------------------------------------------------

# The revision that captures the schema as it existed before Alembic was
# introduced (contracts / parsed_clauses / risk_scores + indexes). Databases
# created by the old ``create_all`` path already have exactly this schema, so
# they are stamped here and then upgraded like everyone else.
_PRE_ALEMBIC_BASELINE = "1140f40c90e2"

_BACKEND_DIR = Path(__file__).resolve().parent


def _alembic_config():
    from alembic.config import Config

    return Config(str(_BACKEND_DIR / "alembic.ini"))


def _run_migrations_blocking(stamp_baseline_first: bool) -> None:
    """Run on a worker thread: alembic's async env.py calls asyncio.run()."""
    from alembic import command

    cfg = _alembic_config()
    if stamp_baseline_first:
        command.stamp(cfg, _PRE_ALEMBIC_BASELINE)
    command.upgrade(cfg, "head")


async def init_db() -> None:
    """Bring the database schema to the current head via Alembic.

    Handles three states:
      - fresh database             → run every migration from the baseline
      - pre-Alembic database       → stamp the baseline, then upgrade
      - already-migrated database  → upgrade (no-op when at head)

    Single-process dev setup: no cross-process migration lock is taken.
    """
    async with engine.connect() as conn:
        def _inspect(sync_conn) -> tuple[bool, bool]:
            from sqlalchemy import inspect as sa_inspect

            inspector = sa_inspect(sync_conn)
            names = set(inspector.get_table_names())
            return ("alembic_version" in names, "contracts" in names)

        has_version_table, has_legacy_tables = await conn.run_sync(_inspect)

    stamp_first = has_legacy_tables and not has_version_table
    await anyio.to_thread.run_sync(_run_migrations_blocking, stamp_first)

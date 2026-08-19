"""Async SQLAlchemy engine, session factory, and declarative Base."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import text
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

async def get_db() -> AsyncGenerator[AsyncSession, None]:
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
# Schema bootstrap
# ---------------------------------------------------------------------------

# ``Base.metadata.create_all`` only emits index DDL for tables it creates, so a
# database that already has the Step 1 tables would never gain these.  Issuing
# them separately is idempotent and covers both fresh and existing databases.
_INDEX_DDL = (
    "CREATE INDEX IF NOT EXISTS ix_parsed_clauses_contract_id "
    "ON parsed_clauses (contract_id)",
    "CREATE INDEX IF NOT EXISTS ix_contracts_created_at "
    "ON contracts (created_at)",
)


async def init_db() -> None:
    """Create tables (dev convenience) and ensure supporting indexes exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for statement in _INDEX_DDL:
            await conn.execute(text(statement))

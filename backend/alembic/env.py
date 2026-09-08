"""Alembic environment — async engine, URL sourced from app settings."""

from __future__ import annotations

import asyncio
import os

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

import models  # noqa: F401,E402  — imported for its table definitions
from alembic import context

# App imports resolve because alembic.ini sets prepend_sys_path to backend/.
from config import normalize_database_url, settings  # noqa: E402
from database import Base  # noqa: E402

config = context.config

# Priority: explicit env override (CI / scratch databases) > backend/.env.
# The override is normalised too, so a raw postgres:// URL works here as well.
_database_url = normalize_database_url(
    os.environ.get("ALEMBIC_DATABASE_URL") or settings.DATABASE_URL
)
config.set_main_option("sqlalchemy.url", _database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of executing (alembic upgrade --sql)."""
    context.configure(
        url=_database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _run_sync_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def _run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(_run_sync_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(_run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

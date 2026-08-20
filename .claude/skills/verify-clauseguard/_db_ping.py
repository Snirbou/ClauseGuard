"""Exit 0 if the configured Postgres is reachable, non-zero otherwise.

Run from the backend directory (so `config`/`database` import). Used by
run_checks.ps1's Database section; kept as a file to avoid embedding
multi-line Python inside the PowerShell script.
"""

import asyncio
import os
import sys

# Python puts THIS file's directory on sys.path, not the working directory,
# so `config`/`database` (in backend/) would not import. The runner invokes
# us with cwd=backend; add it explicitly.
sys.path.insert(0, os.getcwd())

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from config import settings  # noqa: E402


async def _probe() -> None:
    engine = create_async_engine(settings.DATABASE_URL)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    finally:
        await engine.dispose()


try:
    asyncio.run(_probe())
    print("OK")
except Exception as exc:  # noqa: BLE001
    print(f"FAIL: {exc}", file=sys.stderr)
    sys.exit(1)

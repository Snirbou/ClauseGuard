"""Startup and /api/health hardening.

The endpoint must fail loudly: 503 while the database is unreachable or
startup could not migrate it, 200 otherwise — and it retries the deferred
initialisation itself once the database answers, so a slow database at
deploy time never needs a manual restart.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi import Response

import main


class _Session:
    """Minimal AsyncSession stand-in for the probe query."""

    def __init__(self, ok: bool) -> None:
        self.ok = ok
        self.rolled_back = False

    async def execute(self, *_args, **_kwargs):
        if not self.ok:
            raise RuntimeError("connection refused")
        return None

    async def rollback(self) -> None:
        self.rolled_back = True


async def _noop_sleep(_seconds: float) -> None:
    return None


@pytest.fixture(autouse=True)
def _clean_startup_state():
    main.app.state.startup_error = None
    yield
    main.app.state.startup_error = None


def test_health_is_503_when_database_is_down() -> None:
    response = Response()
    session = _Session(ok=False)
    body = asyncio.run(main.health(response=response, db=session))
    assert response.status_code == 503
    assert body.status == "degraded"
    assert body.database == "unavailable"
    assert session.rolled_back is True


def test_health_is_200_when_database_answers() -> None:
    response = Response()
    body = asyncio.run(main.health(response=response, db=_Session(ok=True)))
    assert response.status_code == 200
    assert body.status == "ok"
    assert body.startup_error is None


def test_health_recovers_a_deferred_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    async def fake_init_db() -> None:
        calls.append("init")

    async def fake_recover() -> None:
        calls.append("recover")

    monkeypatch.setattr(main, "init_db", fake_init_db)
    monkeypatch.setattr(main, "recover_stale_runs", fake_recover)
    main.app.state.startup_error = "OSError: boom at boot"

    response = Response()
    body = asyncio.run(main.health(response=response, db=_Session(ok=True)))
    assert calls == ["init", "recover"]
    assert response.status_code == 200
    assert body.startup_error is None


def test_health_stays_503_when_deferred_startup_fails_again(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def failing_init_db() -> None:
        raise RuntimeError("still broken")

    monkeypatch.setattr(main, "init_db", failing_init_db)
    main.app.state.startup_error = "OSError: boom at boot"

    response = Response()
    body = asyncio.run(main.health(response=response, db=_Session(ok=True)))
    assert response.status_code == 503
    assert body.startup_error is not None
    assert "still broken" in body.startup_error


def test_init_db_retry_reports_the_final_error(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts: list[int] = []

    async def failing_init_db() -> None:
        attempts.append(1)
        raise OSError("connection refused")

    monkeypatch.setattr(main, "init_db", failing_init_db)
    monkeypatch.setattr(main.asyncio, "sleep", _noop_sleep)

    error = asyncio.run(main._init_db_with_retry(attempts=3))
    assert len(attempts) == 3
    assert error is not None and error.startswith("OSError")


def test_init_db_retry_succeeds_after_a_transient_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = {"calls": 0}

    async def flaky_init_db() -> None:
        state["calls"] += 1
        if state["calls"] < 2:
            raise OSError("connection refused")

    monkeypatch.setattr(main, "init_db", flaky_init_db)
    monkeypatch.setattr(main.asyncio, "sleep", _noop_sleep)

    assert asyncio.run(main._init_db_with_retry(attempts=3)) is None
    assert state["calls"] == 2

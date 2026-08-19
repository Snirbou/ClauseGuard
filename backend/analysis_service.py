"""analysis_service.py — the bridge between uploaded clauses and the DSPy pipeline.

This is the piece that was missing: previously a developer had to run
``run_pipeline.py --db --save`` by hand to get any AI analysis.  Everything
here is a thin orchestration layer over the existing, working modules —
``dspy_pipeline``, ``optimizer`` and ``db_writer`` are imported and called,
never reimplemented.

Two non-obvious constraints shape this file:

1. ``process_clauses()`` is synchronous and spends most of its time blocking on
   network I/O to the LLM.  Calling it directly from an async endpoint would
   stall the entire event loop, so it is dispatched to a worker thread.

2. ``dspy.configure()`` may only ever be called by the thread that called it
   first (see ``dspy/dsp/utils/settings.py``).  Calling ``configure_lm()`` on
   every request from a rotating pool of worker threads therefore raises
   ``RuntimeError`` on the second request.  ``_ensure_lm_configured()`` makes
   the call exactly once per process instead.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Iterable
from dataclasses import dataclass, field
from uuid import UUID

import anyio.to_thread
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api_schemas import RiskDistribution
from config import settings
from db_writer import save_results_to_db
from dspy_pipeline import configure_lm, process_clauses
from logger import get_logger
from models import ParsedClause
from optimizer import load_optimized_analyzer
from schemas import ClauseAnalysisResult, ClauseInput

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class AnalysisError(RuntimeError):
    """Raised when analysis cannot complete.  Carries an HTTP status code."""

    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class LLMNotConfiguredError(AnalysisError):
    def __init__(self) -> None:
        super().__init__(
            "AI analysis is unavailable because no language model is configured. "
            "Set a real OPENAI_API_KEY in backend/.env and restart the backend.",
            status_code=503,
        )


class AnalysisInProgressError(AnalysisError):
    def __init__(self) -> None:
        super().__init__(
            "Analysis is already running for this contract. Wait for it to finish.",
            status_code=409,
        )


# ---------------------------------------------------------------------------
# One-time LM configuration
# ---------------------------------------------------------------------------

_lm_lock = threading.Lock()
_lm_ready = False


def _ensure_lm_configured() -> None:
    """Call ``configure_lm()`` exactly once for the lifetime of the process."""
    global _lm_ready

    if _lm_ready:
        return

    with _lm_lock:
        if _lm_ready:            # another thread won the race
            return

        if not settings.llm_configured:
            raise LLMNotConfiguredError()

        if settings.DSPY_PROVIDER == "ollama":
            configure_lm(
                provider="ollama",
                model=settings.DSPY_MODEL,
                base_url=settings.OLLAMA_BASE_URL,
            )
        else:
            configure_lm(
                provider=settings.DSPY_PROVIDER,
                model=settings.DSPY_MODEL,
                api_key=settings.OPENAI_API_KEY,
            )

        _lm_ready = True


# ---------------------------------------------------------------------------
# In-flight guard — one analysis per contract at a time
# ---------------------------------------------------------------------------

_in_flight: set[UUID] = set()
_in_flight_guard = asyncio.Lock()


async def _claim(contract_id: UUID) -> None:
    async with _in_flight_guard:
        if contract_id in _in_flight:
            raise AnalysisInProgressError()
        _in_flight.add(contract_id)


async def _release(contract_id: UUID) -> None:
    async with _in_flight_guard:
        _in_flight.discard(contract_id)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def distribution_from_levels(levels: Iterable[str | None]) -> RiskDistribution:
    """Bucket risk levels into a ``RiskDistribution``.

    Anything that is not a recognised level (including ``None``) counts as
    unanalyzed, so the buckets always sum to the number of clauses.
    """
    dist = RiskDistribution()
    for level in levels:
        normalized = (level or "").strip().lower()
        if normalized == "high":
            dist.high += 1
        elif normalized == "medium":
            dist.medium += 1
        elif normalized == "low":
            dist.low += 1
        else:
            dist.unanalyzed += 1
    return dist


async def fetch_clause_inputs(db: AsyncSession, contract_id: UUID) -> list[ClauseInput]:
    """Load a contract's parsed clauses as DSPy pipeline inputs."""
    stmt = (
        select(ParsedClause)
        .where(ParsedClause.contract_id == contract_id)
        .order_by(ParsedClause.clause_index)
    )
    rows = (await db.execute(stmt)).scalars().all()

    return [
        ClauseInput(
            parsed_clause_id=row.id,
            contract_id=row.contract_id,
            # clause_type is nullable in the DB but required by the pipeline.
            raw_text=row.raw_text,
            clause_type=row.clause_type or "general",
        )
        for row in rows
    ]


# ---------------------------------------------------------------------------
# The pipeline run itself
# ---------------------------------------------------------------------------

def _run_pipeline_blocking(clauses: list[ClauseInput]) -> list[ClauseAnalysisResult]:
    """Runs on a worker thread — configure the LM, then analyze every clause."""
    _ensure_lm_configured()
    analyzer = load_optimized_analyzer()
    return process_clauses(clauses, analyzer=analyzer)


@dataclass
class AnalysisOutcome:
    contract_id: UUID
    clause_count: int
    saved_count: int
    results: list[ClauseAnalysisResult] = field(default_factory=list)

    @property
    def analyzed_count(self) -> int:
        return len(self.results)

    @property
    def failed_count(self) -> int:
        return max(0, self.clause_count - len(self.results))


async def analyze_contract(db: AsyncSession, contract_id: UUID) -> AnalysisOutcome:
    """Run the DSPy pipeline over one contract and persist the risk scores.

    Raises ``AnalysisError`` (with an HTTP status code) on any condition the
    caller should surface to the user rather than treat as a 500.
    """
    if not settings.llm_configured:
        raise LLMNotConfiguredError()

    clauses = await fetch_clause_inputs(db, contract_id)
    if not clauses:
        raise AnalysisError(
            "This contract has no parsed clauses to analyze.",
            status_code=400,
        )

    await _claim(contract_id)
    try:
        logger.info(
            "Analyzing contract %s — %d clause(s) via %s/%s",
            contract_id,
            len(clauses),
            settings.DSPY_PROVIDER,
            settings.DSPY_MODEL,
        )

        results = await anyio.to_thread.run_sync(_run_pipeline_blocking, clauses)

        # process_clauses() logs and skips clauses that raise, so an empty list
        # from a non-empty input means every single call failed — almost always
        # a bad API key, no credit, or an unreachable provider.
        if not results:
            raise AnalysisError(
                "The language model returned no usable results. Check that "
                "OPENAI_API_KEY is valid and that the provider is reachable; "
                "the backend log has the underlying error.",
                status_code=502,
            )

        saved_count = await save_results_to_db(results)
        if saved_count == 0:
            raise AnalysisError(
                "Analysis succeeded but the results could not be written to the "
                "database. Check the backend log.",
                status_code=500,
            )

        if saved_count < len(results):
            logger.warning(
                "Contract %s: only %d/%d results persisted.",
                contract_id,
                saved_count,
                len(results),
            )

        return AnalysisOutcome(
            contract_id=contract_id,
            clause_count=len(clauses),
            saved_count=saved_count,
            results=results,
        )
    finally:
        await _release(contract_id)

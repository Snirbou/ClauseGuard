"""analysis_service.py — asynchronous, run-based bridge to the DSPy pipeline.

POST /analyze no longer holds the HTTP request open for the whole LLM loop.
Instead it creates an ``analysis_runs`` row (PRD/DataModel §2.6), schedules
the work as an asyncio task, and returns 202 with the run id; the frontend
polls the run for progress while clause results land incrementally.

Design points, each load-bearing:

- **Bounded parallelism.** Clauses are analyzed ``ANALYZE_CONCURRENCY`` at a
  time. Each in-flight clause occupies one worker thread for the duration of
  an LLM round-trip (the DSPy call is synchronous).
- **Per-clause persistence.** Every result is committed in its own short
  transaction the moment it exists. A crash mid-run loses only the clauses
  that were in flight; completed work survives and is skipped next time via
  the content-hash cache.
- **Content-hash caching.** ``sha256(clause text | provider/model | program
  version)`` is stored with each result. A re-run skips clauses whose hash
  matches — re-analyzing an unchanged contract is free and instant.
- **Single-owner LM configuration.** ``dspy.configure()`` may only ever be
  called by the thread that called it first, so it happens exactly once per
  process, guarded by a lock.
- **The "fake" provider** (``DSPY_PROVIDER=fake``) swaps in a deterministic
  offline analyzer so the whole machinery runs without an API key — used by
  demo mode, the smoke test, and CI.

Module state (``_active_tasks``) makes this single-process by design; the
DB-level active-run check additionally rejects doubles across restarts.
"""

from __future__ import annotations

import asyncio
import hashlib
import threading
import time
from collections.abc import Iterable
from datetime import UTC, datetime
from uuid import UUID

import anyio.to_thread
import dspy
from sqlalchemy import delete as sa_delete
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from api_schemas import RiskDistribution
from config import settings
from contract_summary import (
    fake_executive_summary,
    generate_executive_summary_blocking,
)
from database import async_session_factory
from db_writer import save_result_to_db
from dspy_pipeline import configure_lm, process_clauses
from fake_llm import FakeAnalyzer
from logger import get_logger
from models import AnalysisRun, Contract, ContractFinding, ParsedClause, RiskScore
from optimizer import load_optimized_analyzer
from pain_points import detect_missing_protections
from schemas import ClauseAnalysisResult, ClauseInput
from scoring import compute_hybrid_risk_level

logger = get_logger(__name__)

ACTIVE_STATUSES = ("pending", "running")


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class AnalysisError(RuntimeError):
    """Raised when analysis cannot start/complete. Carries an HTTP status."""

    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class LLMNotConfiguredError(AnalysisError):
    def __init__(self) -> None:
        super().__init__(
            "AI analysis is unavailable because no language model is configured. "
            "Set a real OPENAI_API_KEY in backend/.env and restart the backend "
            "(or set DSPY_PROVIDER=fake for offline demo mode).",
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

    if _lm_ready or settings.DSPY_PROVIDER == "fake":
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


def _build_analyzer():
    """Runs on a worker thread: configure the LM and build the analyzer."""
    if settings.DSPY_PROVIDER == "fake":
        return FakeAnalyzer()
    _ensure_lm_configured()
    return load_optimized_analyzer()


# ---------------------------------------------------------------------------
# Content-hash cache
# ---------------------------------------------------------------------------

def pipeline_fingerprint() -> str:
    """Identity of the analysis pipeline for cache-invalidation purposes."""
    return f"{settings.DSPY_PROVIDER}/{settings.DSPY_MODEL}|dspy-{dspy.__version__}"


def clause_content_hash(raw_text: str) -> str:
    payload = f"{raw_text}|{pipeline_fingerprint()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


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
            # Confidence feeds the Layer 3 hybrid blend. 0.5 for legacy rows
            # persisted before the column was populated: neutral uncertainty.
            clause_type_confidence=float(row.clause_type_confidence)
            if row.clause_type_confidence is not None
            else 0.5,
        )
        for row in rows
    ]


async def _existing_hashes(db: AsyncSession, contract_id: UUID) -> dict[UUID, str | None]:
    stmt = (
        select(RiskScore.parsed_clause_id, RiskScore.content_hash)
        .join(ParsedClause, ParsedClause.id == RiskScore.parsed_clause_id)
        .where(ParsedClause.contract_id == contract_id)
    )
    rows = (await db.execute(stmt)).all()
    return {row.parsed_clause_id: row.content_hash for row in rows}


# ---------------------------------------------------------------------------
# Run lifecycle
# ---------------------------------------------------------------------------

# run_id -> asyncio.Task, for wait=true, graceful shutdown, and tests.
_active_tasks: dict[UUID, asyncio.Task] = {}
_start_guard = asyncio.Lock()


async def start_analysis(
    db: AsyncSession,
    contract_id: UUID,
    *,
    force: bool = False,
) -> AnalysisRun:
    """Create an analysis run and schedule its execution. Returns the run row.

    Raises AnalysisError subclasses for every condition the API should
    surface (503 no LLM, 400 no clauses, 409 already running).
    """
    if not settings.llm_configured:
        raise LLMNotConfiguredError()

    clause_count = len(await fetch_clause_inputs(db, contract_id))
    if clause_count == 0:
        raise AnalysisError(
            "This contract has no parsed clauses to analyze.",
            status_code=400,
        )

    async with _start_guard:
        active = await db.execute(
            select(AnalysisRun.id)
            .where(
                AnalysisRun.contract_id == contract_id,
                AnalysisRun.status.in_(ACTIVE_STATUSES),
            )
            .limit(1)
        )
        if active.first() is not None:
            raise AnalysisInProgressError()

        run = AnalysisRun(
            contract_id=contract_id,
            status="pending",
            clause_count=clause_count,
            run_metadata={
                "provider": settings.DSPY_PROVIDER,
                "model": settings.DSPY_MODEL,
                "dspy_version": dspy.__version__,
                "force": force,
            },
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)

    task = asyncio.create_task(
        _execute_run(run.id, contract_id, force=force),
        name=f"analysis-run-{run.id}",
    )
    _active_tasks[run.id] = task
    task.add_done_callback(lambda _t, rid=run.id: _active_tasks.pop(rid, None))
    return run


async def wait_for_run(run_id: UUID) -> None:
    """Await a run scheduled by this process (used by ?wait=true)."""
    task = _active_tasks.get(run_id)
    if task is not None:
        await asyncio.shield(task)


async def get_run(db: AsyncSession, run_id: UUID) -> AnalysisRun | None:
    return await db.get(AnalysisRun, run_id)


async def latest_run_for_contract(
    db: AsyncSession, contract_id: UUID
) -> AnalysisRun | None:
    stmt = (
        select(AnalysisRun)
        .where(AnalysisRun.contract_id == contract_id)
        .order_by(AnalysisRun.started_at.desc())
        .limit(1)
    )
    return (await db.execute(stmt)).scalars().first()


async def recover_stale_runs() -> int:
    """Mark runs left pending/running by a previous process as failed.

    Called once at startup: any run in an active state at boot cannot still
    be executing (tasks do not survive the process), so surfacing it as
    failed lets the user simply re-run.
    """
    async with async_session_factory() as session:
        async with session.begin():
            result = await session.execute(
                update(AnalysisRun)
                .where(AnalysisRun.status.in_(ACTIVE_STATUSES))
                .values(
                    status="failed",
                    completed_at=datetime.now(UTC),
                    error_message="Interrupted by a backend restart. Run the analysis again.",
                )
            )
    count = result.rowcount or 0
    if count:
        logger.warning("Recovered %d stale analysis run(s) from a previous process.", count)
    return count


async def shutdown_analysis_tasks() -> None:
    """Cancel in-flight runs on graceful shutdown (they finalize as failed)."""
    tasks = list(_active_tasks.values())
    for task in tasks:
        task.cancel()
    for task in tasks:
        try:
            await task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

def _analyze_clause_blocking(analyzer, clause: ClauseInput) -> ClauseAnalysisResult | None:
    """Runs on a worker thread: analyze one clause with bounded retries.

    ``process_clauses`` logs and swallows per-clause exceptions, returning an
    empty list — that empty list is the retry signal here.
    """
    for attempt in range(settings.ANALYZE_MAX_RETRIES):
        results = process_clauses([clause], analyzer=analyzer)
        if results:
            return results[0]
        if attempt < settings.ANALYZE_MAX_RETRIES - 1:
            # Exponential backoff inside the worker thread; the event loop
            # is not blocked. Deterministic delays keep tests predictable.
            time.sleep(0.8 * (2**attempt))
    return None


async def _update_run(run_id: UUID, **values) -> None:
    async with async_session_factory() as session:
        async with session.begin():
            await session.execute(
                update(AnalysisRun).where(AnalysisRun.id == run_id).values(**values)
            )


async def _increment_progress(run_id: UUID) -> None:
    async with async_session_factory() as session:
        async with session.begin():
            await session.execute(
                update(AnalysisRun)
                .where(AnalysisRun.id == run_id)
                .values(completed_clauses=AnalysisRun.completed_clauses + 1)
            )


async def _execute_run(run_id: UUID, contract_id: UUID, *, force: bool) -> None:
    """The background body of one analysis run."""
    t0 = time.monotonic()
    metadata_patch: dict = {}

    try:
        await _update_run(run_id, status="running")

        async with async_session_factory() as session:
            clauses = await fetch_clause_inputs(session, contract_id)
            existing = await _existing_hashes(session, contract_id)

        hashes = {c.parsed_clause_id: clause_content_hash(c.raw_text) for c in clauses}

        if force:
            cached: list[ClauseInput] = []
            to_run = clauses
        else:
            cached = [c for c in clauses if existing.get(c.parsed_clause_id) == hashes[c.parsed_clause_id]]
            cached_ids = {c.parsed_clause_id for c in cached}
            to_run = [c for c in clauses if c.parsed_clause_id not in cached_ids]

        await _update_run(
            run_id,
            clause_count=len(clauses),
            completed_clauses=len(cached),
        )
        metadata_patch["cached_clauses"] = len(cached)

        failed_ids: list[str] = []
        analyzed_count = 0

        if to_run:
            analyzer = await anyio.to_thread.run_sync(_build_analyzer)
            semaphore = asyncio.Semaphore(max(1, settings.ANALYZE_CONCURRENCY))

            async def _one(clause: ClauseInput) -> bool:
                async with semaphore:
                    result = await anyio.to_thread.run_sync(
                        _analyze_clause_blocking, analyzer, clause
                    )
                if result is None:
                    failed_ids.append(str(clause.parsed_clause_id))
                    return False

                # Layer 3: blend L1 confidence with the L2 output. db_writer
                # applies the identical function when persisting, so response
                # and storage always agree.
                result.risk_level = compute_hybrid_risk_level(
                    clause_type=result.clause_type,
                    clause_type_confidence=result.clause_type_confidence,
                    dspy_risk_score=result.dspy_risk_score,
                    num_risk_factors=len(result.risk_factors),
                )
                saved = await save_result_to_db(
                    result, content_hash=hashes[clause.parsed_clause_id]
                )
                if not saved:
                    failed_ids.append(str(clause.parsed_clause_id))
                    return False
                await _increment_progress(run_id)
                return True

            outcomes = await asyncio.gather(*(_one(c) for c in to_run))
            analyzed_count = sum(1 for ok in outcomes if ok)

        succeeded_total = analyzed_count + len(cached)
        metadata_patch["analyzed_clauses"] = analyzed_count
        if failed_ids:
            metadata_patch["failed_parsed_clause_ids"] = failed_ids

        # Contract-level pass: missing-protection findings, comparative
        # percentiles, executive summary. Partial per-clause failures do not
        # block it — whatever was analyzed still deserves the overview.
        if succeeded_total > 0:
            try:
                findings_count = await _contract_level_pass(contract_id, clauses)
                metadata_patch["findings"] = findings_count
            except Exception:
                logger.exception(
                    "Contract-level pass failed for %s (per-clause results are saved).",
                    contract_id,
                )

        elapsed_ms = int((time.monotonic() - t0) * 1000)

        if succeeded_total == 0:
            await _finalize(
                run_id,
                status="failed",
                elapsed_ms=elapsed_ms,
                metadata_patch=metadata_patch,
                error_message=(
                    "The language model returned no usable results. Check that "
                    "OPENAI_API_KEY is valid and the provider is reachable; the "
                    "backend log has the underlying error."
                ),
            )
        else:
            error = None
            if failed_ids:
                error = f"{len(failed_ids)} clause(s) failed after retries; the rest completed."
            await _finalize(
                run_id,
                status="completed",
                elapsed_ms=elapsed_ms,
                metadata_patch=metadata_patch,
                error_message=error,
            )
            logger.info(
                "Run %s completed: %d analyzed, %d cached, %d failed, %d ms.",
                run_id, analyzed_count, len(cached), len(failed_ids), elapsed_ms,
            )

    except asyncio.CancelledError:
        await _finalize(
            run_id,
            status="failed",
            elapsed_ms=int((time.monotonic() - t0) * 1000),
            metadata_patch=metadata_patch,
            error_message="The backend shut down mid-run. Run the analysis again.",
        )
        raise
    except Exception as exc:
        logger.exception("Analysis run %s crashed.", run_id)
        await _finalize(
            run_id,
            status="failed",
            elapsed_ms=int((time.monotonic() - t0) * 1000),
            metadata_patch=metadata_patch,
            error_message=f"Unexpected error: {exc}",
        )


# SQL for AC-R02's comparative framing: each clause's percentile rank of the
# raw risk score within its own contract, as an integer 0–100.
_PERCENTILE_SQL = text(
    """
    UPDATE risk_scores rs
    SET risk_percentile = sub.pct
    FROM (
        SELECT rs2.id,
               CAST(ROUND(100 * PERCENT_RANK() OVER (ORDER BY rs2.risk_score)) AS INT) AS pct
        FROM risk_scores rs2
        JOIN parsed_clauses pc ON pc.id = rs2.parsed_clause_id
        WHERE pc.contract_id = :contract_id
    ) sub
    WHERE rs.id = sub.id
    """
)


async def _contract_level_pass(contract_id: UUID, clauses: list[ClauseInput]) -> int:
    """Findings + percentiles + executive summary. Returns findings count."""
    # 1. Missing-protection findings from the clause types present.
    present_types = {c.clause_type for c in clauses}
    findings = detect_missing_protections(present_types)

    async with async_session_factory() as session:
        async with session.begin():
            # Refresh atomically: findings always mirror the latest run.
            await session.execute(
                sa_delete(ContractFinding).where(
                    ContractFinding.contract_id == contract_id
                )
            )
            for finding in findings:
                session.add(
                    ContractFinding(
                        contract_id=contract_id,
                        finding_type="missing_protection",
                        pain_point=finding.pain_point,
                        severity=finding.severity,
                        title=finding.title,
                        detail=finding.detail,
                    )
                )

            # 2. Comparative percentiles within the contract (AC-R02).
            await session.execute(_PERCENTILE_SQL, {"contract_id": contract_id})

    # 3. Executive summary over the persisted per-clause results.
    async with async_session_factory() as session:
        rows = (
            await session.execute(
                select(ParsedClause.clause_index, ParsedClause.clause_type, RiskScore)
                .join(RiskScore, RiskScore.parsed_clause_id == ParsedClause.id)
                .where(ParsedClause.contract_id == contract_id)
                .order_by(ParsedClause.clause_index)
            )
        ).all()

    if rows:
        levels = [row.RiskScore.risk_level for row in rows]
        distribution = distribution_from_levels(levels)

        if settings.DSPY_PROVIDER == "fake":
            summary = fake_executive_summary(
                distribution, len(clauses), [f.title for f in findings]
            )
        else:
            digest_lines = [
                f"#{row.clause_index} [{row.clause_type}] risk={row.RiskScore.risk_level}: "
                f"{(row.RiskScore.plain_language_summary or '')[:140]}"
                for row in rows
            ]
            digest_lines += [f"MISSING PROTECTION: {f.title} — {f.detail}" for f in findings]
            digest = "\n".join(digest_lines)

            def _summarize() -> str:
                _ensure_lm_configured()
                return generate_executive_summary_blocking(digest)

            summary = await anyio.to_thread.run_sync(_summarize)

        async with async_session_factory() as session:
            async with session.begin():
                await session.execute(
                    update(Contract)
                    .where(Contract.id == contract_id)
                    .values(analysis_summary=summary)
                )

    return len(findings)


async def _finalize(
    run_id: UUID,
    *,
    status: str,
    elapsed_ms: int,
    metadata_patch: dict,
    error_message: str | None,
) -> None:
    try:
        async with async_session_factory() as session:
            async with session.begin():
                run = await session.get(AnalysisRun, run_id)
                if run is None:
                    return
                merged = dict(run.run_metadata or {})
                merged.update(metadata_patch)
                run.status = status
                run.completed_at = datetime.now(UTC)
                run.processing_time_ms = elapsed_ms
                run.error_message = error_message
                run.run_metadata = merged
    except Exception:
        logger.exception("Failed to finalize analysis run %s.", run_id)

"""
db_writer.py — Database persistence layer for DSPy pipeline outputs.

Saves ClauseAnalysisResult objects to the PostgreSQL risk_scores table.
"""

from __future__ import annotations

import dspy
from sqlalchemy.dialects.postgresql import insert

from database import async_session_factory
from logger import get_logger
from models import RiskScore
from schemas import ClauseAnalysisResult
from scoring import compute_hybrid_risk_level

logger = get_logger(__name__)


async def save_results_to_db(results: list[ClauseAnalysisResult]) -> int:
    """
    Insert or update (upsert) risk_scores records in the database.

    Parameters
    ----------
    results : list[ClauseAnalysisResult]
        The outputs from the DSPy pipeline.

    Returns
    -------
    int
        The number of records successfully saved.
    """
    if not results:
        return 0

    dspy_version = dspy.__version__
    saved_count = 0

    async with async_session_factory() as session:
        # Open the outer transaction explicitly so per-row savepoints have
        # something to nest inside. Without this, a single row failure leaves
        # the implicit transaction in an aborted state, and every subsequent
        # await session.execute(...) raises the asyncpg
        # "another operation is in progress" / InvalidRequestError.
        async with session.begin():
            for res in results:
                # Layer 3: blend L1 + L2 signals into the persisted risk_level.
                # The raw L2 score (dspy_risk_score) is preserved separately
                # in risk_scores.risk_score for traceability and re-bucketing.
                hybrid_level = compute_hybrid_risk_level(
                    clause_type=res.clause_type,
                    clause_type_confidence=res.clause_type_confidence,
                    dspy_risk_score=res.dspy_risk_score,
                    num_risk_factors=len(res.risk_factors),
                )

                # Use PostgreSQL UPSERT (INSERT ... ON CONFLICT DO UPDATE)
                # matching by parsed_clause_id (which is UNIQUE).
                stmt = insert(RiskScore).values(
                    parsed_clause_id=res.parsed_clause_id,
                    risk_level=hybrid_level,
                    risk_score=res.dspy_risk_score,
                    risk_factors=res.risk_factors,
                    plain_language_summary=res.plain_language_summary,
                    dspy_program_version=dspy_version,
                )

                # If the record already exists, update the computed values
                stmt = stmt.on_conflict_do_update(
                    index_elements=["parsed_clause_id"],
                    set_={
                        "risk_level": stmt.excluded.risk_level,
                        "risk_score": stmt.excluded.risk_score,
                        "risk_factors": stmt.excluded.risk_factors,
                        "plain_language_summary": stmt.excluded.plain_language_summary,
                        "dspy_program_version": stmt.excluded.dspy_program_version,
                    },
                )

                # Each row is wrapped in a SAVEPOINT so that a failure on
                # one clause auto-rolls-back to the savepoint and leaves
                # the connection in a clean state for the next iteration.
                try:
                    async with session.begin_nested():
                        await session.execute(stmt)
                    saved_count += 1
                except Exception as exc:
                    logger.error(
                        "Failed to save result for clause %s: %s",
                        res.parsed_clause_id,
                        exc,
                    )
            # session.begin() context commits on successful exit, rolls back on raise.

    logger.info("Successfully saved %d/%d results to DB.", saved_count, len(results))
    return saved_count

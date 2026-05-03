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
        for res in results:
            try:
                # Use PostgreSQL UPSERT (INSERT ... ON CONFLICT DO UPDATE)
                # matching by parsed_clause_id (which is UNIQUE).
                stmt = insert(RiskScore).values(
                    parsed_clause_id=res.parsed_clause_id,
                    risk_level=res.risk_level,
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

                await session.execute(stmt)
                saved_count += 1
            except Exception as exc:
                logger.error("Failed to save result for clause %s: %s", res.parsed_clause_id, exc)

        try:
            await session.commit()
        except Exception as exc:
            logger.error("Failed to commit DB transaction: %s", exc)
            return 0

    logger.info("Successfully saved %d/%d results to DB.", saved_count, len(results))
    return saved_count

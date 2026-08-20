"""
run_pipeline.py — CLI runner for the ClauseGuard DSPy pipeline (Developer 2, Stage 2).

USAGE
-----
    # Mode 1: Mock data (offline dev)
    python run_pipeline.py --mock
    python run_pipeline.py --mock --save

    # Mode 2: Live DB
    python run_pipeline.py --db --contract-id <UUID> --save

    # Mode 3: Optimization
    python run_pipeline.py --mock --optimize          # BootstrapFewShot
    python run_pipeline.py --mock --optimize-mipro    # MIPROv2
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from uuid import UUID

# Load .env variables before importing pipeline modules
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

from db_writer import save_results_to_db  # noqa: E402
from dspy_pipeline import configure_lm, process_clauses  # noqa: E402
from logger import RunStats, get_logger  # noqa: E402
from mock_data import get_mock_clauses  # noqa: E402
from optimizer import load_optimized_analyzer, run_bootstrap_fewshot, run_miprov2  # noqa: E402
from schemas import ClauseAnalysisResult, ClauseInput  # noqa: E402

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Pretty-print helpers
# ---------------------------------------------------------------------------

_RISK_EMOJI = {"low": "[LOW]", "medium": "[MED]", "high": "[HIGH]"}
_DIVIDER = "-" * 72


def _print_result(idx: int, result: ClauseAnalysisResult) -> None:
    """Print a single ClauseAnalysisResult in a human-readable format."""
    risk_emoji = _RISK_EMOJI.get(result.risk_level, "[???]")
    print(f"\n{_DIVIDER}")
    print(f"  Clause #{idx}  |  Type: {result.clause_type}")
    print(f"  ID: {result.parsed_clause_id}")
    print(f"{_DIVIDER}")
    print(f"  Summary:\n     {result.plain_language_summary}")
    print(f"\n  Risk Factors:\n     {', '.join(result.risk_factors) if result.risk_factors else 'None'}")
    print(f"\n  {risk_emoji} Risk Level: {result.risk_level.upper()} (Score: {result.dspy_risk_score:.2f})")


def _print_summary(results: list[ClauseAnalysisResult]) -> None:
    """Print a final summary table after all clauses are processed."""
    print(f"\n{'=' * 72}")
    print("  PIPELINE COMPLETE — SUMMARY")
    print(f"{'=' * 72}")
    print(f"  {'#':<4} {'Clause Type':<20} {'Score':<6} {'Risk':<10} {'Clause ID'}")
    print(f"  {'-'*4} {'-'*20} {'-'*6} {'-'*10} {'-'*36}")
    for i, r in enumerate(results, 1):
        emoji = _RISK_EMOJI.get(r.risk_level, "[???]")
        print(
            f"  {i:<4} {r.clause_type:<20} "
            f"{r.dspy_risk_score:<6.2f} {emoji} {r.risk_level:<8} {r.parsed_clause_id}"
        )
    print(f"{'=' * 72}\n")


# ---------------------------------------------------------------------------
# Pipeline Execution Core
# ---------------------------------------------------------------------------

async def execute_pipeline(
    clauses: list[ClauseInput],
    provider: str,
    model: str,
    should_save: bool,
    optimize_bfs: bool,
    optimize_mipro: bool,
) -> None:
    configure_lm(provider=provider, model=model)

    # 1. Optimisation Phase
    analyzer = None
    if optimize_mipro:
        analyzer = run_miprov2()
    elif optimize_bfs:
        analyzer = run_bootstrap_fewshot()
    else:
        analyzer = load_optimized_analyzer()

    # 2. Processing Phase (DSPy is sync — runs inline; brief block is fine for a CLI)
    logger.info("Processing %d clauses...", len(clauses))
    stats = RunStats(total=len(clauses))

    results = process_clauses(clauses, analyzer=analyzer)

    for _r in results:
        stats.record_success()

    for i, result in enumerate(results, 1):
        _print_result(i, result)

    _print_summary(results)
    stats.log_summary(logger)

    # 3. Persistence Phase
    if should_save:
        logger.info("Saving results to database...")
        saved_count = await save_results_to_db(results)
        logger.info("Save complete. DB updated with %d records.", saved_count)
    else:
        logger.info("Skipping database save (use --save to persist).")


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------

async def _run_mock_async(args: argparse.Namespace) -> None:
    logger.info("Mode: MOCK DATA (no database required)")
    clauses = get_mock_clauses()
    await execute_pipeline(
        clauses=clauses,
        provider=args.provider,
        model=args.model,
        should_save=args.save,
        optimize_bfs=args.optimize,
        optimize_mipro=args.optimize_mipro,
    )


def run_mock(args: argparse.Namespace) -> None:
    asyncio.run(_run_mock_async(args))


async def _fetch_clauses_from_db(contract_id: UUID | None) -> list[ClauseInput]:
    from sqlalchemy import select  # noqa: PLC0415

    from database import async_session_factory  # noqa: PLC0415
    from models import ParsedClause  # noqa: PLC0415

    async with async_session_factory() as session:
        stmt = select(ParsedClause)
        if contract_id is not None:
            stmt = stmt.where(ParsedClause.contract_id == contract_id)
        stmt = stmt.order_by(ParsedClause.contract_id, ParsedClause.clause_index)

        result = await session.execute(stmt)
        rows = result.scalars().all()

    if not rows:
        hint = f"contract_id={contract_id}" if contract_id else "any contract"
        logger.warning("No clauses found in DB for %s.", hint)
        sys.exit(0)

    return [
        ClauseInput(
            parsed_clause_id=row.id,
            contract_id=row.contract_id,
            raw_text=row.raw_text,
            clause_type=row.clause_type or "general",
            clause_type_confidence=float(row.clause_type_confidence or 0.0),
        )
        for row in rows
    ]


async def _run_db_async(args: argparse.Namespace) -> None:
    scope = f"contract_id={args.contract_id}" if args.contract_id else "ALL contracts"
    logger.info("Mode: LIVE DATABASE — scope: %s", scope)

    clauses = await _fetch_clauses_from_db(args.contract_id)
    logger.info("Fetched %d clauses from DB.", len(clauses))

    await execute_pipeline(
        clauses=clauses,
        provider=args.provider,
        model=args.model,
        should_save=args.save,
        optimize_bfs=args.optimize,
        optimize_mipro=args.optimize_mipro,
    )


def run_db(args: argparse.Namespace) -> None:
    # Single asyncio.run() so the SQLAlchemy/asyncpg engine pool stays bound
    # to one event loop. Running fetch and save in separate asyncio.run() calls
    # caused "another operation is in progress" because pooled asyncpg
    # connections were tied to the first (now-closed) loop.
    asyncio.run(_run_db_async(args))


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_pipeline",
        description="ClauseGuard DSPy Pipeline Runner (Developer 2, Stage 2)",
    )

    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--mock", action="store_true", help="Run with mock clauses.")
    mode_group.add_argument("--db", action="store_true", help="Run against PostgreSQL data.")

    parser.add_argument("--contract-id", type=UUID, default=None, help="Filter by contract UUID.")
    
    parser.add_argument("--save", action="store_true", help="Save results to the risk_scores table.")
    
    parser.add_argument("--optimize", action="store_true", help="Run BootstrapFewShot optimizer before processing.")
    parser.add_argument("--optimize-mipro", action="store_true", help="Run MIPROv2 optimizer (slower, better).")

    parser.add_argument("--provider", default="openai", choices=["openai", "ollama"], help="LLM provider.")
    parser.add_argument(
        "--model",
        default=None,
        help="Model name. Defaults: 'gpt-4o-mini' for openai, 'llama3' for ollama.",
    )

    return parser


_PROVIDER_DEFAULT_MODEL = {"openai": "gpt-4o-mini", "ollama": "llama3"}


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.model is None:
        args.model = _PROVIDER_DEFAULT_MODEL[args.provider]

    if args.mock:
        run_mock(args)
    elif args.db:
        run_db(args)


if __name__ == "__main__":
    main()

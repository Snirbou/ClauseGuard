"""
run_pipeline.py — CLI runner for the ClauseGuard DSPy pipeline (Developer 2).

USAGE
-----
    # Mode 1: Mock data (no DB required — great for development)
    python run_pipeline.py --mock

    # Mode 2: Live DB — process a specific contract by UUID
    python run_pipeline.py --db --contract-id <UUID>

    # Mode 3: Live DB — process ALL contracts in the DB
    python run_pipeline.py --db

REQUIREMENTS
------------
    - backend/.env must contain OPENAI_API_KEY (for OpenAI) or Ollama running locally
    - For --db mode: DATABASE_URL must be set and PostgreSQL must be reachable

EXAMPLES
--------
    python run_pipeline.py --mock
    python run_pipeline.py --mock --provider ollama --model llama3.2
    python run_pipeline.py --db --contract-id a1b2c3d4-e5f6-7890-abcd-ef1234567890
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from uuid import UUID

# Load .env variables before importing pipeline modules
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

from dspy_pipeline import configure_lm, process_clauses  # noqa: E402
from mock_data import get_mock_clauses  # noqa: E402
from schemas import ClauseAnalysisResult, ClauseInput  # noqa: E402


# ---------------------------------------------------------------------------
# Pretty-print helpers
# ---------------------------------------------------------------------------

_RISK_EMOJI = {"low": "[LOW]", "medium": "[MED]", "high": "[HIGH]"}
_DIVIDER = "-" * 72


def _print_result(idx: int, result: ClauseAnalysisResult) -> None:
    """Print a single ClauseAnalysisResult in a human-readable format."""
    risk_emoji = _RISK_EMOJI.get(result.initial_risk_assessment, "⚪")
    print(f"\n{_DIVIDER}")
    print(f"  Clause #{idx}  |  Type: {result.clause_type}")
    print(f"  ID: {result.parsed_clause_id}")
    print(f"{_DIVIDER}")
    print(f"  Summary:\n     {result.plain_language_summary}")
    print(f"\n  {risk_emoji} Risk Level: {result.initial_risk_assessment.upper()}")


def _print_summary(results: list[ClauseAnalysisResult]) -> None:
    """Print a final summary table after all clauses are processed."""
    print(f"\n{'=' * 72}")
    print("  PIPELINE COMPLETE — SUMMARY")
    print(f"{'=' * 72}")
    print(f"  {'#':<4} {'Clause Type':<20} {'Risk':<10} {'Clause ID'}")
    print(f"  {'-'*4} {'-'*20} {'-'*10} {'-'*36}")
    for i, r in enumerate(results, 1):
        emoji = _RISK_EMOJI.get(r.initial_risk_assessment, "⚪")
        print(
            f"  {i:<4} {r.clause_type:<20} "
            f"{emoji} {r.initial_risk_assessment:<8} {r.parsed_clause_id}"
        )
    print(f"{'=' * 72}\n")


# ---------------------------------------------------------------------------
# Mode 1: Mock data (no DB)
# ---------------------------------------------------------------------------

def run_mock(provider: str, model: str) -> None:
    """Run the pipeline using hardcoded mock clauses."""
    print("\n[run_pipeline] Mode: MOCK DATA (no database required)")
    configure_lm(provider=provider, model=model)

    clauses = get_mock_clauses()
    print(f"[run_pipeline] Processing {len(clauses)} mock clauses…\n")

    results = process_clauses(clauses)

    for i, result in enumerate(results, 1):
        _print_result(i, result)

    _print_summary(results)


# ---------------------------------------------------------------------------
# Mode 2: Live database
# ---------------------------------------------------------------------------

async def _fetch_clauses_from_db(contract_id: UUID | None) -> list[ClauseInput]:
    """
    Async helper: query parsed_clauses from PostgreSQL.

    Imports database modules lazily so --mock mode never needs a DB connection.
    """
    # Lazy imports — only needed for --db mode
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
        hint = (
            f"contract_id={contract_id}" if contract_id else "any contract"
        )
        print(f"[run_pipeline] ⚠  No clauses found in DB for {hint}.")
        sys.exit(0)

    return [
        ClauseInput(
            parsed_clause_id=row.id,
            contract_id=row.contract_id,
            raw_text=row.raw_text,
            clause_type=row.clause_type or "general",
        )
        for row in rows
    ]


def run_db(provider: str, model: str, contract_id: UUID | None) -> None:
    """Run the pipeline against live data from PostgreSQL."""
    scope = f"contract_id={contract_id}" if contract_id else "ALL contracts"
    print(f"\n[run_pipeline] Mode: LIVE DATABASE — scope: {scope}")
    configure_lm(provider=provider, model=model)

    clauses = asyncio.run(_fetch_clauses_from_db(contract_id))
    print(f"[run_pipeline] Fetched {len(clauses)} clauses from DB…\n")

    results = process_clauses(clauses)

    for i, result in enumerate(results, 1):
        _print_result(i, result)

    _print_summary(results)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_pipeline",
        description="ClauseGuard DSPy Pipeline Runner (Developer 2, Step 1)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Mode (mutually exclusive)
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--mock",
        action="store_true",
        help="Run with built-in mock clauses (no database required).",
    )
    mode_group.add_argument(
        "--db",
        action="store_true",
        help="Run against live PostgreSQL data (requires DATABASE_URL in .env).",
    )

    # DB options
    parser.add_argument(
        "--contract-id",
        type=UUID,
        default=None,
        metavar="UUID",
        help=(
            "Filter by a specific contract UUID. "
            "Only valid with --db. Omit to process all contracts."
        ),
    )

    # LLM options
    parser.add_argument(
        "--provider",
        default="openai",
        choices=["openai", "ollama"],
        help="LLM provider to use (default: openai).",
    )
    parser.add_argument(
        "--model",
        default="gpt-4o-mini",
        help=(
            "Model name (default: gpt-4o-mini). "
            "For Ollama: try 'llama3.2' or 'mistral'."
        ),
    )

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.mock:
        run_mock(provider=args.provider, model=args.model)
    elif args.db:
        run_db(
            provider=args.provider,
            model=args.model,
            contract_id=args.contract_id,
        )


if __name__ == "__main__":
    main()

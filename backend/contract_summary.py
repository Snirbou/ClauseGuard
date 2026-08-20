"""Contract-level executive summary — one DSPy call over the clause digest.

Kept out of dspy_pipeline.py (which owns the per-clause signature) so the
per-clause pipeline stays exactly as the CLI tools expect it.
"""

from __future__ import annotations

import dspy

from api_schemas import RiskDistribution
from logger import get_logger

logger = get_logger(__name__)


class ContractExecutiveSummary(dspy.Signature):
    """Summarize a full contract analysis for the person about to sign it.

    You are an expert legal document assistant. You are given a digest of a
    freelance service agreement: one line per clause (type, risk level, short
    summary) plus a list of protections that appear to be missing. Write an
    executive summary for the freelancer.

    Constraints: 3–5 sentences, plain English, no legal jargon. Be strictly
    observational — describe what the contract contains and which patterns
    are commonly considered risky. NEVER give advice, recommendations, or
    instructions (no "you should", "we recommend"), and NEVER suggest
    alternative wording.
    """

    contract_digest: str = dspy.InputField(
        desc="One line per clause: index, type, risk level, short summary; "
        "followed by contract-level findings (missing protections)."
    )
    executive_summary: str = dspy.OutputField(
        desc="3-5 sentence plain-English overview of the contract's risk "
        "profile. Observational only; not legal advice."
    )


def generate_executive_summary_blocking(digest: str) -> str:
    """Run the summary signature. Call on a worker thread, LM configured."""
    module = dspy.ChainOfThought(ContractExecutiveSummary)
    prediction = module(contract_digest=digest)
    return prediction.executive_summary.strip()


def fake_executive_summary(
    distribution: RiskDistribution,
    clause_count: int,
    missing_titles: list[str],
) -> str:
    """Deterministic offline summary for DSPY_PROVIDER=fake."""
    parts = [
        f"[Demo analysis — no language model configured] This contract was "
        f"segmented into {clause_count} clauses: {distribution.high} rated "
        f"high risk, {distribution.medium} medium, and {distribution.low} low."
    ]
    if missing_titles:
        parts.append(
            "Contract-level review also flagged: " + "; ".join(missing_titles) + "."
        )
    else:
        parts.append(
            "All five commonly expected protection areas (payment, scope, "
            "IP, termination, liability) are addressed by at least one clause."
        )
    parts.append(
        "Connect an OpenAI API key in backend/.env to replace this canned "
        "text with a real executive summary."
    )
    return " ".join(parts)

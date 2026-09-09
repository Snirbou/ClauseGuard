"""Deterministic stand-in for the DSPy analyzer — no network, no API key.

Activated with ``DSPY_PROVIDER=fake`` in backend/.env. Exists for two
purposes:

1. **Demo mode** — the full product (upload → analyze → risk UI) works end
   to end on a machine with no OpenAI key.
2. **Tests** — the smoke test and CI can exercise the entire asynchronous
   analysis machinery (runs, progress, caching, hybrid scoring,
   persistence) with reproducible outputs.

Outputs are derived from a hash of the clause text, so the same clause
always produces the same score — which also makes the content-hash cache
observable in tests. The generated text is clearly labeled as canned so it
can never be mistaken for real analysis.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

# Deterministic per-type base risk, tuned so a typical contract shows a mix
# of levels in the UI. The text-hash jitter (±0.15) keeps identical types
# from all landing on identical scores.
_TYPE_BASE_RISK: dict[str, float] = {
    "liability": 0.75,
    "ip_assignment": 0.70,
    "termination": 0.55,
    "payment_terms": 0.45,
    "confidentiality": 0.35,
    "scope_of_work": 0.30,
    "governing_law": 0.25,
    "general": 0.20,
}

_TYPE_FACTORS: dict[str, list[str]] = {
    "liability": ["Indemnification obligation present", "No liability cap detected"],
    "ip_assignment": ["Broad IP assignment language", "No carve-out for pre-existing work"],
    "termination": ["Termination terms may be asymmetric"],
    "payment_terms": ["Extended payment window"],
    "confidentiality": ["Confidentiality obligation may be perpetual"],
    "scope_of_work": ["Deliverables depend on external exhibit"],
    "governing_law": ["Fixed forum may add travel/cost burden"],
    "general": [],
}


@dataclass
class _FakePrediction:
    plain_language_summary: str
    risk_factors: str
    dspy_risk_score: str


class FakeAnalyzer:
    """Drop-in for ClauseAnalyzerV2: callable(raw_text, clause_type) → prediction."""

    def __call__(self, raw_text: str, clause_type: str) -> _FakePrediction:
        digest = hashlib.sha256(raw_text.encode("utf-8")).digest()
        jitter = (digest[0] / 255.0 - 0.5) * 0.30          # deterministic ±0.15
        base = _TYPE_BASE_RISK.get(clause_type, 0.30)
        score = max(0.02, min(0.98, base + jitter))

        factors = _TYPE_FACTORS.get(clause_type, [])
        factors_text = ", ".join(factors) if factors else "None"

        summary = (
            f"[Demo analysis — no language model configured] This clause was "
            f"categorized as {clause_type.replace('_', ' ')}. It spans "
            f"{len(raw_text)} characters. Connect an OpenAI API key in "
            f"backend/.env to replace this canned text with a real "
            f"plain-language explanation."
        )

        return _FakePrediction(
            plain_language_summary=summary,
            risk_factors=factors_text,
            dspy_risk_score=f"{score:.2f}",
        )


_NUMBER_TOKEN = re.compile(r"\d+(?:[.,]\d+)?")


@dataclass
class _FakeVerdict:
    faithful: bool
    unsupported_claims: list[str]


class FakeFaithfulnessJudge:
    """Offline twin of ``judge.SummaryFaithfulness`` for ``DSPY_PROVIDER=fake``.

    Installed by the evaluation harness so the optimizer metric can be
    exercised end to end without an LM. The heuristic is deliberately narrow
    and deterministic: a summary is "faithful" when every number it mentions
    also appears in the clause. That catches the one class of fabrication a
    regex can see — an invented amount, day count or percentage — and
    nothing else, which is exactly what a plumbing test needs and exactly
    why its verdicts are labelled ``measured: false`` in any report.
    """

    def __call__(self, clause_text: str, summary: str) -> _FakeVerdict:
        clause_numbers = {token.replace(",", "") for token in _NUMBER_TOKEN.findall(clause_text)}
        invented = [
            token
            for token in _NUMBER_TOKEN.findall(summary)
            if token.replace(",", "") not in clause_numbers
        ]
        return _FakeVerdict(faithful=not invented, unsupported_claims=invented)

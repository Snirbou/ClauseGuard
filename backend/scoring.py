"""
scoring.py — Layer 3 hybrid risk scoring for ClauseGuard.

Blends the L1 classifier confidence, the L2 DSPy risk score, the L2-extracted
risk-factor count, and a clause-type severity prior into a single deterministic
risk level (low / medium / high) persisted to risk_scores.risk_level.

Pure module: no DB, IO, DSPy, or framework imports. Unit-testable in isolation.
"""

from __future__ import annotations

from typing import Literal

RiskLevel = Literal["low", "medium", "high"]


SEVERITY_PRIOR: dict[str, float] = {
    "liability":       1.00,
    "ip_assignment":   0.85,
    "termination":     0.70,
    "payment_terms":   0.55,
    "confidentiality": 0.40,
    "scope_of_work":   0.30,
    "general":         0.30,
    "governing_law":   0.20,
}

W_DSPY        = 0.65
W_FACTORS     = 0.15
W_UNCERTAINTY = 0.10
W_TYPE_PRIOR  = 0.10
FACTOR_SATURATION = 4

THRESHOLD_HIGH   = 0.65
THRESHOLD_MEDIUM = 0.35


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def compute_hybrid_score(
    *,
    clause_type: str,
    clause_type_confidence: float,
    dspy_risk_score: float,
    num_risk_factors: int,
) -> float:
    """Blend L1 + L2 signals into a single hybrid risk score in [0, 1]."""
    factor_density = min(max(num_risk_factors, 0) / FACTOR_SATURATION, 1.0)
    uncertainty    = 1.0 - _clamp01(clause_type_confidence)
    type_severity  = SEVERITY_PRIOR.get(clause_type, SEVERITY_PRIOR["general"])
    s2             = _clamp01(dspy_risk_score)

    hybrid = (
        W_DSPY        * s2
      + W_FACTORS     * factor_density
      + W_UNCERTAINTY * uncertainty
      + W_TYPE_PRIOR  * type_severity
    )
    return _clamp01(hybrid)


def compute_hybrid_risk_level(
    *,
    clause_type: str,
    clause_type_confidence: float,
    dspy_risk_score: float,
    num_risk_factors: int,
) -> RiskLevel:
    """Bucket the hybrid score into a categorical risk level."""
    score = compute_hybrid_score(
        clause_type=clause_type,
        clause_type_confidence=clause_type_confidence,
        dspy_risk_score=dspy_risk_score,
        num_risk_factors=num_risk_factors,
    )
    if score >= THRESHOLD_HIGH:
        return "high"
    if score >= THRESHOLD_MEDIUM:
        return "medium"
    return "low"

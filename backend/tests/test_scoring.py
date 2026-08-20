"""Unit tests for backend.scoring — Layer 3 hybrid risk scoring."""

from __future__ import annotations

import itertools

import pytest

from scoring import (
    FACTOR_SATURATION,
    SEVERITY_PRIOR,
    THRESHOLD_HIGH,
    THRESHOLD_MEDIUM,
    compute_hybrid_risk_level,
    compute_hybrid_score,
)

CG8 = list(SEVERITY_PRIOR.keys())


# --- Range tests ----------------------------------------------------------

@pytest.mark.parametrize("c1,s2,nf,ctype", [
    (c1, s2, nf, ctype)
    for c1, s2, nf, ctype in itertools.product([0.0, 1.0], [0.0, 1.0], [0, 8], CG8)
])
def test_score_in_unit_interval(c1, s2, nf, ctype):
    score = compute_hybrid_score(
        clause_type=ctype,
        clause_type_confidence=c1,
        dspy_risk_score=s2,
        num_risk_factors=nf,
    )
    assert 0.0 <= score <= 1.0


# --- Bucketing tests ------------------------------------------------------

def test_low_corner():
    # high confidence, zero dspy, zero factors, lowest type prior
    score = compute_hybrid_score(
        clause_type="governing_law",
        clause_type_confidence=1.0,
        dspy_risk_score=0.0,
        num_risk_factors=0,
    )
    # = 0 + 0 + 0 + 0.10 * 0.20 = 0.02
    assert score == pytest.approx(0.02)
    assert compute_hybrid_risk_level(
        clause_type="governing_law",
        clause_type_confidence=1.0,
        dspy_risk_score=0.0,
        num_risk_factors=0,
    ) == "low"


def test_high_corner():
    # zero confidence, max dspy, saturated factors, highest type prior
    score = compute_hybrid_score(
        clause_type="liability",
        clause_type_confidence=0.0,
        dspy_risk_score=1.0,
        num_risk_factors=FACTOR_SATURATION,
    )
    # = 0.65 + 0.15 + 0.10 + 0.10 = 1.00
    assert score == pytest.approx(1.0)
    assert compute_hybrid_risk_level(
        clause_type="liability",
        clause_type_confidence=0.0,
        dspy_risk_score=1.0,
        num_risk_factors=FACTOR_SATURATION,
    ) == "high"


def test_threshold_boundaries():
    # Construct an input that lands just below and just above each threshold
    # via the dspy_risk_score (the dominant 0.65 weight).
    # type_prior ("general") = 0.30 → 0.10 * 0.30 = 0.03 baseline
    # uncertainty = 1 - 1 = 0; factors = 0 → other terms zero
    base = 0.10 * SEVERITY_PRIOR["general"]   # 0.03
    s2_med = (THRESHOLD_MEDIUM - base) / 0.65  # exact crossing point
    s2_high = (THRESHOLD_HIGH - base) / 0.65

    # Just below medium → low
    assert compute_hybrid_risk_level(
        clause_type="general",
        clause_type_confidence=1.0,
        dspy_risk_score=s2_med - 0.01,
        num_risk_factors=0,
    ) == "low"
    # At/above medium → medium
    assert compute_hybrid_risk_level(
        clause_type="general",
        clause_type_confidence=1.0,
        dspy_risk_score=s2_med + 0.01,
        num_risk_factors=0,
    ) == "medium"
    # At/above high → high
    assert compute_hybrid_risk_level(
        clause_type="general",
        clause_type_confidence=1.0,
        dspy_risk_score=s2_high + 0.01,
        num_risk_factors=0,
    ) == "high"


# --- Behavioral / property tests ------------------------------------------

def test_factor_saturation():
    base_args = dict(
        clause_type="payment_terms",
        clause_type_confidence=0.9,
        dspy_risk_score=0.4,
    )
    at_sat = compute_hybrid_score(num_risk_factors=FACTOR_SATURATION, **base_args)
    far_above = compute_hybrid_score(num_risk_factors=FACTOR_SATURATION + 50, **base_args)
    assert at_sat == pytest.approx(far_above)


def test_unknown_clause_type_falls_back_to_general_prior():
    args = dict(
        clause_type_confidence=0.8,
        dspy_risk_score=0.5,
        num_risk_factors=2,
    )
    unknown = compute_hybrid_score(clause_type="not_a_real_type", **args)
    general = compute_hybrid_score(clause_type="general", **args)
    assert unknown == pytest.approx(general)


def test_monotone_in_dspy_score():
    # For fixed other inputs, score must be non-decreasing in dspy_risk_score.
    args = dict(
        clause_type="termination",
        clause_type_confidence=0.7,
        num_risk_factors=1,
    )
    prev = -1.0
    for s2 in [0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0]:
        cur = compute_hybrid_score(dspy_risk_score=s2, **args)
        assert cur >= prev
        prev = cur


def test_monotone_in_factor_count_until_saturation():
    args = dict(
        clause_type="ip_assignment",
        clause_type_confidence=0.95,
        dspy_risk_score=0.3,
    )
    prev = -1.0
    for nf in range(0, FACTOR_SATURATION + 1):
        cur = compute_hybrid_score(num_risk_factors=nf, **args)
        assert cur >= prev
        prev = cur


def test_low_l1_confidence_raises_score():
    high_conf = compute_hybrid_score(
        clause_type="liability",
        clause_type_confidence=1.0,
        dspy_risk_score=0.5,
        num_risk_factors=0,
    )
    low_conf = compute_hybrid_score(
        clause_type="liability",
        clause_type_confidence=0.0,
        dspy_risk_score=0.5,
        num_risk_factors=0,
    )
    assert low_conf > high_conf  # uncertainty premium fires


def test_clamps_out_of_range_inputs():
    # Inputs outside [0,1] are clamped, not rejected
    score = compute_hybrid_score(
        clause_type="general",
        clause_type_confidence=2.5,
        dspy_risk_score=-0.7,
        num_risk_factors=-3,
    )
    # confidence clamped to 1.0 → uncertainty=0; dspy clamped to 0; factors clamped to 0
    # only type_prior contributes: 0.10 * 0.30 = 0.03
    assert score == pytest.approx(0.03)

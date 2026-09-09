"""judge_metric, the faithfulness judge, and the shape of the trainset file.

Every test here runs with NO API key: the judge is stubbed. What is being
checked is the metric's arithmetic and its gates, not the LM's opinion.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import dspy
import pytest

import judge
import optimizer
import upl
from readability import flesch_kincaid_grade

# A summary that is faithful, plain, and observational — the shape the metric
# is supposed to reward.
GOOD_SUMMARY = (
    "You keep the rights to the tools you built before this job. The client "
    "gets to use them only inside the work you hand over."
)

CLAUSE = (
    "The Contractor retains ownership of all materials created before this "
    "Agreement and grants the Client a licence to use them solely as embedded "
    "in the Deliverables."
)


def _example(risk_factors: str = "None", risk_score: str = "0.2") -> dspy.Example:
    return dspy.Example(
        raw_text=CLAUSE,
        clause_type="ip_assignment",
        plain_language_summary=GOOD_SUMMARY,
        risk_factors=risk_factors,
        dspy_risk_score=risk_score,
    ).with_inputs("raw_text", "clause_type")


def _pred(summary: str = GOOD_SUMMARY, factors: str = "None", score: str = "0.2"):
    return SimpleNamespace(
        plain_language_summary=summary,
        risk_factors=factors,
        dspy_risk_score=score,
    )


@pytest.fixture
def faithful_judge(monkeypatch):
    """Stub the judge as always-faithful. No LM, no key, no network.

    Patched on ``optimizer``, not ``judge``: the metric binds the name at
    import, so a stub installed on the wrong module would silently never
    run — the real judge would fail without an LM, the renormalising
    fallback would fire, and the tests would pass for the wrong reason.
    The returned counter lets a test prove the stub was actually consulted.
    """
    calls = {"n": 0}

    def stub(clause: str, summary: str) -> judge.FaithfulnessVerdict:
        calls["n"] += 1
        return judge.FaithfulnessVerdict(faithful=True)

    monkeypatch.setattr(optimizer, "judge_faithfulness", stub)
    return calls


@pytest.fixture
def unfaithful_judge(monkeypatch):
    monkeypatch.setattr(
        optimizer,
        "judge_faithfulness",
        lambda clause, summary: judge.FaithfulnessVerdict(
            faithful=False, unsupported_claims=["invented a 30-day term"]
        ),
    )


# ---------------------------------------------------------------------------
# The UPL gate
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "advice",
    [
        "You should not sign this clause without changing it.",
        "We recommend that you ask for a cap on liability.",
        "Make sure you keep a copy of every invoice.",
    ],
)
def test_prescriptive_language_scores_zero(advice, faithful_judge) -> None:
    """AC-P02 is a gate, not a weighted component.

    A partial score would let the optimizer trade advice-giving against
    readability, which is exactly the drift the guardrail exists to stop.
    """
    assert upl.violations(advice), "test fixture is not actually prescriptive"
    assert optimizer.judge_metric(_example(), _pred(summary=advice)) == 0.0


def test_prescriptive_language_fails_the_bootstrap_gate(faithful_judge) -> None:
    score = optimizer.judge_metric(
        _example(), _pred(summary="You should renegotiate this."), trace=[]
    )
    assert score is False


def test_empty_summary_scores_zero(faithful_judge) -> None:
    assert optimizer.judge_metric(_example(), _pred(summary="   ")) == 0.0


# ---------------------------------------------------------------------------
# The weighted components
# ---------------------------------------------------------------------------


def test_a_clean_faithful_prediction_clears_the_threshold(faithful_judge) -> None:
    score = optimizer.judge_metric(_example(), _pred())
    assert score >= optimizer.JUDGE_PASS_THRESHOLD
    assert optimizer.judge_metric(_example(), _pred(), trace=[]) is True
    assert faithful_judge["n"] == 2, "the stubbed judge was never consulted"


def test_an_unfaithful_summary_falls_below_the_threshold(unfaithful_judge) -> None:
    """A fluent, readable, well-calibrated lie must still fail the gate.

    Everything except faithfulness is perfect here, so this is the case the
    old length-based metric scored full marks.
    """
    assert optimizer.judge_metric(_example(), _pred()) < optimizer.JUDGE_PASS_THRESHOLD


def test_faithfulness_is_worth_its_declared_weight(monkeypatch) -> None:
    def verdict(faithful: bool):
        return lambda clause, summary: judge.FaithfulnessVerdict(faithful=faithful)

    monkeypatch.setattr(optimizer, "judge_faithfulness", verdict(True))
    high = optimizer.judge_metric(_example(), _pred())
    monkeypatch.setattr(optimizer, "judge_faithfulness", verdict(False))
    low = optimizer.judge_metric(_example(), _pred())
    assert high - low == pytest.approx(optimizer.W_FAITHFUL, abs=1e-6)


def test_inventing_risks_for_a_benign_clause_is_penalised(faithful_judge) -> None:
    """The gold label says "None"; predicting factors anyway must cost."""
    clean = optimizer.judge_metric(_example(risk_factors="None"), _pred(factors="None"))
    invented = optimizer.judge_metric(
        _example(risk_factors="None"), _pred(factors="Uncapped indemnity")
    )
    assert invented < clean


def test_missing_the_risks_on_a_risky_clause_is_penalised(faithful_judge) -> None:
    example = _example(risk_factors="Uncapped indemnity", risk_score="0.9")
    found = optimizer.judge_metric(example, _pred(factors="Uncapped indemnity", score="0.9"))
    missed = optimizer.judge_metric(example, _pred(factors="None", score="0.9"))
    assert missed < found


def test_risk_score_proximity_is_graded(faithful_judge) -> None:
    example = _example(risk_score="0.8")
    close = optimizer.judge_metric(example, _pred(score="0.75"))
    near = optimizer.judge_metric(example, _pred(score="0.5"))
    far = optimizer.judge_metric(example, _pred(score="0.1"))
    assert close > near > far


def test_an_unreadable_summary_scores_below_a_plain_one(faithful_judge) -> None:
    dense = (
        "Notwithstanding the foregoing, the Contractor's retention of "
        "proprietary antecedent materials is subject to the irrevocable "
        "licence granted hereunder to the Client in perpetuity, provided that "
        "such utilisation remains circumscribed to the incorporation thereof "
        "within the contractually specified Deliverables."
    )
    assert not upl.violations(dense)
    assert optimizer.judge_metric(_example(), _pred(summary=dense)) < optimizer.judge_metric(
        _example(), _pred()
    )


# ---------------------------------------------------------------------------
# Judge failure must not look like a bad answer
# ---------------------------------------------------------------------------


def test_a_broken_judge_renormalises_instead_of_zeroing(monkeypatch) -> None:
    monkeypatch.setattr(
        optimizer,
        "judge_faithfulness",
        lambda clause, summary: judge.FaithfulnessVerdict(faithful=False, judged=False),
    )
    score = optimizer.judge_metric(_example(), _pred())
    # Every remaining component is perfect, so renormalising must give 1.0 —
    # scoring 0 here would tell the optimizer the program was terrible when
    # in fact only the judge broke.
    assert score == pytest.approx(1.0, abs=1e-6)


def test_the_judge_never_raises(monkeypatch) -> None:
    def explode(*_args, **_kwargs):
        raise RuntimeError("no LM configured")

    monkeypatch.setattr(judge, "_get_program", explode)
    judge.reset_judge()
    verdict = judge.judge_faithfulness(CLAUSE, GOOD_SUMMARY)
    assert verdict.judged is False


def test_the_judge_memoises(monkeypatch) -> None:
    judge.reset_judge()
    calls = {"n": 0}

    def program(**kwargs):
        calls["n"] += 1
        return SimpleNamespace(faithful=True, unsupported_claims=[])

    monkeypatch.setattr(judge, "_get_program", lambda: program)
    for _ in range(4):
        assert judge.judge_faithfulness(CLAUSE, GOOD_SUMMARY).faithful is True
    assert calls["n"] == 1
    judge.reset_judge()


def test_an_empty_summary_is_unfaithful_not_unjudged() -> None:
    judge.reset_judge()
    verdict = judge.judge_faithfulness(CLAUSE, "")
    assert verdict.judged is True
    assert verdict.faithful is False


# ---------------------------------------------------------------------------
# The trainset file
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def trainset_rows() -> list[dict]:
    try:
        with open(optimizer.TRAINSET_PATH, encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError:
        pytest.skip("no trainset file in this checkout")
    return payload["examples"]


def test_trainset_covers_every_clause_type_three_times(trainset_rows) -> None:
    from ml_inference.src.label_map import CG8_TARGETS

    counts: dict[str, int] = {}
    for row in trainset_rows:
        counts[row["clause_type"]] = counts.get(row["clause_type"], 0) + 1
    assert set(counts) == set(CG8_TARGETS)
    assert all(n == 3 for n in counts.values()), counts


def test_trainset_splits_sixteen_eight_with_full_coverage(trainset_rows) -> None:
    trainset, valset = optimizer.load_split()
    assert (len(trainset), len(valset)) == (16, 8)
    assert {e.clause_type for e in trainset} == {e.clause_type for e in valset}


def test_the_split_is_deterministic(trainset_rows) -> None:
    first = [e.raw_text for e in optimizer.load_split()[1]]
    second = [e.raw_text for e in optimizer.load_split()[1]]
    assert first == second


def test_every_gold_summary_is_upl_clean(trainset_rows) -> None:
    """The training targets must satisfy the guardrail they teach.

    A gold summary containing advice would train the model to produce advice
    and then be scored 0.0 for it by the very metric built from these labels.
    """
    offenders = [
        (row["clause_type"], upl.violations(row["plain_language_summary"]))
        for row in trainset_rows
        if upl.violations(row["plain_language_summary"])
    ]
    assert not offenders, offenders


def test_every_gold_summary_is_readable(trainset_rows) -> None:
    """AC-P04's target is grade 12; gold labels must not exceed it badly."""
    too_dense = [
        (row["clause_type"], grade)
        for row in trainset_rows
        if (grade := flesch_kincaid_grade(row["plain_language_summary"])) is not None
        and grade > optimizer.GRADE_FLOOR
    ]
    assert not too_dense, too_dense


def test_gold_risk_scores_are_in_range(trainset_rows) -> None:
    for row in trainset_rows:
        value = float(row["dspy_risk_score"])
        assert 0.0 <= value <= 1.0, row["clause_type"]


def test_gold_labels_score_well_under_the_metric(trainset_rows, faithful_judge) -> None:
    """A gold label fed back as its own prediction should score near 1.0.

    If the metric cannot recognise its own targets, it is measuring something
    other than what the trainset teaches.
    """
    for row in trainset_rows:
        example = dspy.Example(**{
            k: row[k]
            for k in (
                "raw_text",
                "clause_type",
                "plain_language_summary",
                "risk_factors",
                "dspy_risk_score",
            )
        }).with_inputs("raw_text", "clause_type")
        prediction = _pred(
            summary=row["plain_language_summary"],
            factors=row["risk_factors"],
            score=row["dspy_risk_score"],
        )
        score = optimizer.judge_metric(example, prediction)
        assert score >= optimizer.JUDGE_PASS_THRESHOLD, (row["clause_type"], score)


# ---------------------------------------------------------------------------
# Determinism of the task LM
# ---------------------------------------------------------------------------


def test_configure_lm_pins_the_task_temperature(monkeypatch) -> None:
    import dspy_pipeline

    captured: dict[str, object] = {}
    monkeypatch.setattr(
        dspy_pipeline.dspy, "LM", lambda **kwargs: captured.update(kwargs) or object()
    )
    monkeypatch.setattr(dspy_pipeline.dspy, "configure", lambda **_kwargs: None)
    dspy_pipeline.configure_lm(provider="openai", model="gpt-4o-mini", api_key="sk-test")
    assert captured["temperature"] == 0.0


# ---------------------------------------------------------------------------
# The risk-score parser the metric and the product both rely on
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # The regression: the old pattern matched ".0" inside "1.0" and
        # returned the minimum score for the maximum answer.
        ("1.0", 1.0),
        ("1.00", 1.0),
        ("1", 1.0),
        ("0.0", 0.0),
        ("0", 0.0),
        ("0.85", 0.85),
        (".85", 0.85),
        ("risk: 0.9", 0.9),
        ("0.5 out of 1.0", 0.5),
        # Prose that mentions a section number before the score.
        ("clause 3.2 scores 0.4", 0.4),
        # A model asked for 0-1 that answers in percent means 0.85, not 1.0.
        ("85%", 0.85),
        # Out-of-range answers clamp instead of wrapping or crashing.
        ("10 out of 10", 1.0),
        ("-0.3", 0.3),
    ],
)
def test_parse_risk_score_reads_the_whole_number(raw: str, expected: float) -> None:
    from dspy_pipeline import _parse_risk_score

    assert _parse_risk_score(raw) == pytest.approx(expected)


@pytest.mark.parametrize("raw", ["", "high", "n/a", None])
def test_parse_risk_score_without_a_number_is_unknown_not_low(raw) -> None:
    """An unparseable answer is unknown risk; reporting it as 0.0 would hide it."""
    from dspy_pipeline import UNPARSEABLE_RISK_SCORE, _parse_risk_score

    assert _parse_risk_score(raw) == UNPARSEABLE_RISK_SCORE

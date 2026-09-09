"""Unit tests for the AC-R05 risk-evaluation harness and its sidecar reader.

Everything here is offline: the metric math, the threshold sweep, the anchor
resolution, the provider gate that decides which file a run may write, and
``eval_info.risk_eval_info()``. The parts that need an LLM, the spaCy
classifier, or the private corpus are exercised by running the script itself
(Phase 4), never by the test suite.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import fitz
import pytest

import eval_info

# eval/ is a scripts directory, not an importable package from here: its
# __init__.py may or may not exist, and importing through it would execute
# unrelated sibling modules. Load risk_eval as a top-level module instead.
EVAL_DIR = Path(__file__).resolve().parents[1] / "eval"
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))

import risk_eval  # noqa: E402  isort: skip


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _prediction(
    *,
    gold_high: bool,
    predicted_high: bool,
    source: str = "cuad",
    dspy_risk_score: float = 0.5,
    clause_type: str = "general",
    confidence: float = 0.9,
    num_risk_factors: int = 1,
) -> risk_eval.Prediction:
    return risk_eval.Prediction(
        clause=risk_eval.EvalClause(
            source=source, doc="doc", text="clause text", gold_high_risk=gold_high
        ),
        clause_type=clause_type,
        clause_type_confidence=confidence,
        dspy_risk_score=dspy_risk_score,
        num_risk_factors=num_risk_factors,
        risk_level="high" if predicted_high else "low",
        cached=True,
    )


def _pdf(body: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_textbox(fitz.Rect(56, 56, 556, 780), body, fontsize=10.0, fontname="helv")
    data = doc.tobytes()
    doc.close()
    return data


# ---------------------------------------------------------------------------
# Metric math
# ---------------------------------------------------------------------------

def test_metrics_on_a_mixed_run() -> None:
    #        truth:  T  T  T  F  F
    #        pred :  T  F  T  T  F      -> tp=2 fn=1 fp=1 tn=1
    truths = [True, True, True, False, False]
    preds = [True, False, True, True, False]
    metrics = risk_eval.binary_metrics(truths, preds)

    assert metrics["confusion"] == {"tp": 2, "fp": 1, "fn": 1, "tn": 1}
    assert metrics["n"] == 5
    assert metrics["precision"] == pytest.approx(2 / 3)
    assert metrics["recall"] == pytest.approx(2 / 3)
    assert metrics["f1"] == pytest.approx(2 / 3)


def test_perfect_run_scores_one() -> None:
    metrics = risk_eval.binary_metrics([True, False, True], [True, False, True])
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["f1"] == 1.0
    assert metrics["confusion"] == {"tp": 2, "fp": 0, "fn": 0, "tn": 1}


def test_detector_that_never_fires_scores_zero_not_one() -> None:
    # The zero-division convention that matters: no predicted positives must
    # not read as perfect precision on the dashboard.
    metrics = risk_eval.binary_metrics([True, True, False], [False, False, False])
    assert metrics["precision"] == 0.0
    assert metrics["recall"] == 0.0
    assert metrics["f1"] == 0.0
    assert metrics["confusion"] == {"tp": 0, "fp": 0, "fn": 2, "tn": 1}


def test_all_positive_predictions() -> None:
    metrics = risk_eval.binary_metrics([True, False, False, False], [True, True, True, True])
    assert metrics["precision"] == pytest.approx(0.25)   # the base rate
    assert metrics["recall"] == 1.0
    assert metrics["f1"] == pytest.approx(0.4)


def test_no_gold_positives_gives_zero_recall() -> None:
    metrics = risk_eval.binary_metrics([False, False], [True, False])
    assert metrics["recall"] == 0.0
    assert metrics["precision"] == 0.0
    assert metrics["f1"] == 0.0


def test_empty_run_is_all_zeros_not_a_crash() -> None:
    metrics = risk_eval.binary_metrics([], [])
    assert metrics == {
        "n": 0,
        "precision": 0.0,
        "recall": 0.0,
        "f1": 0.0,
        "confusion": {"tp": 0, "fp": 0, "fn": 0, "tn": 0},
    }


def test_mismatched_lengths_are_rejected() -> None:
    with pytest.raises(ValueError):
        risk_eval.binary_metrics([True, False], [True])


# ---------------------------------------------------------------------------
# Threshold sweep
# ---------------------------------------------------------------------------

def test_sweep_covers_the_documented_range_and_marks_the_live_threshold() -> None:
    rows = [(0.30, False), (0.55, True), (0.70, True), (0.90, True)]
    sweep = risk_eval.threshold_sweep(rows)

    assert [row["threshold"] for row in sweep] == list(risk_eval.SWEEP_THRESHOLDS)
    assert sweep[0]["threshold"] == 0.40 and sweep[-1]["threshold"] == 0.85
    assert sum(1 for row in sweep if row["current"]) == 1
    current = next(row for row in sweep if row["current"])
    assert current["threshold"] == pytest.approx(risk_eval.THRESHOLD_HIGH)


def test_raising_the_threshold_never_increases_recall() -> None:
    rows = [
        (0.10, False), (0.38, True), (0.44, False), (0.52, True),
        (0.61, True), (0.66, False), (0.78, True), (0.83, False), (0.99, True),
    ]
    sweep = risk_eval.threshold_sweep(rows)

    recalls = [row["recall"] for row in sweep]
    assert recalls == sorted(recalls, reverse=True)
    # The same monotonicity in the raw counts, which is what drives it.
    flagged = [row["confusion"]["tp"] + row["confusion"]["fp"] for row in sweep]
    assert flagged == sorted(flagged, reverse=True)


def test_sweep_uses_a_ge_comparison_at_the_boundary() -> None:
    sweep = risk_eval.threshold_sweep([(0.65, True)], thresholds=[0.65, 0.70])
    assert sweep[0]["confusion"]["tp"] == 1   # score == threshold counts as high
    assert sweep[1]["confusion"]["fn"] == 1


# ---------------------------------------------------------------------------
# Payload
# ---------------------------------------------------------------------------

def test_payload_reports_per_source_and_carries_no_clause_text() -> None:
    predictions = [
        _prediction(gold_high=True, predicted_high=True, source="gold"),
        _prediction(gold_high=False, predicted_high=True, source="gold"),
        _prediction(gold_high=True, predicted_high=False, source="cuad"),
        _prediction(gold_high=False, predicted_high=False, source="cuad"),
    ]
    payload = risk_eval.build_payload(
        predictions, measured=True, provider="openai", model="gpt-4o-mini",
        caveats=[risk_eval.CUAD_CAVEAT],
    )

    assert payload["n"] == 4
    assert payload["dataset"] == {"cuad": 2, "gold": 2}
    assert payload["confusion"] == {"tp": 1, "fp": 1, "fn": 1, "tn": 1}
    assert payload["precision_high"] == pytest.approx(0.5)
    assert payload["recall_high"] == pytest.approx(0.5)
    assert payload["targets"] == {"precision": 0.75, "recall": 0.70}
    assert payload["meets_targets"] is False
    assert payload["per_source"]["gold"]["recall"] == 1.0
    assert payload["per_source"]["cuad"]["recall"] == 0.0
    assert risk_eval.CUAD_CAVEAT in payload["caveats"]

    # Metrics only: nothing that could carry contract text into git.
    assert "clause text" not in json.dumps(payload)


def test_payload_meets_targets_when_both_are_cleared() -> None:
    predictions = [_prediction(gold_high=True, predicted_high=True) for _ in range(8)]
    predictions += [_prediction(gold_high=False, predicted_high=False) for _ in range(2)]
    payload = risk_eval.build_payload(
        predictions, measured=True, provider="openai", model="gpt-4o-mini"
    )
    assert payload["precision_high"] == 1.0
    assert payload["recall_high"] == 1.0
    assert payload["meets_targets"] is True


# ---------------------------------------------------------------------------
# Provider gate
# ---------------------------------------------------------------------------

def test_fake_provider_writes_only_the_provisional_file(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    models_dir = tmp_path / "models"
    payload = risk_eval.build_payload(
        [_prediction(gold_high=True, predicted_high=True)],
        measured=False, provider="fake", model="fake",
        caveats=[risk_eval.FAKE_CAVEAT],
    )

    path = risk_eval.write_report(
        payload, provider="fake", results_dir=results_dir, models_dir=models_dir
    )

    assert path == results_dir / "risk_eval.provisional.json"
    written = json.loads(path.read_text(encoding="utf-8"))
    assert written["provisional"] is True
    assert written["measured"] is False
    assert risk_eval.FAKE_CAVEAT in written["caveats"]
    # The committed sidecar the dashboard reads must not exist.
    assert not (models_dir / "risk_eval.json").exists()


def test_openai_provider_writes_the_committed_sidecar(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    models_dir = tmp_path / "models"
    payload = risk_eval.build_payload(
        [_prediction(gold_high=True, predicted_high=True)],
        measured=True, provider="openai", model="gpt-4o-mini",
    )

    path = risk_eval.write_report(
        payload, provider="openai", results_dir=results_dir, models_dir=models_dir
    )

    assert path == models_dir / "risk_eval.json"
    written = json.loads(path.read_text(encoding="utf-8"))
    assert written["measured"] is True
    assert written["provisional"] is False
    assert not (results_dir / "risk_eval.provisional.json").exists()


# ---------------------------------------------------------------------------
# Layer 2 cache
# ---------------------------------------------------------------------------

def test_cache_key_separates_clauses_providers_and_models() -> None:
    base = risk_eval.cache_key("text", "openai", "gpt-4o-mini")
    assert base != risk_eval.cache_key("other", "openai", "gpt-4o-mini")
    assert base != risk_eval.cache_key("text", "fake", "gpt-4o-mini")
    assert base != risk_eval.cache_key("text", "openai", "gpt-4o")
    assert base == risk_eval.cache_key("text", "openai", "gpt-4o-mini")


def test_cache_roundtrips_and_survives_a_truncated_tail(tmp_path: Path) -> None:
    path = tmp_path / "l2_cache.jsonl"
    risk_eval.append_l2_cache(path, "k1", {"dspy_risk_score": 0.4, "risk_factors": []})
    risk_eval.append_l2_cache(path, "k2", {"dspy_risk_score": 0.8, "risk_factors": ["a"]})
    # A run killed mid-write leaves a half line; it must not poison the cache.
    with path.open("a", encoding="utf-8") as handle:
        handle.write('{"key": "k3", "dspy_ri')

    cache = risk_eval.load_l2_cache(path)
    assert set(cache) == {"k1", "k2"}
    assert cache["k2"]["dspy_risk_score"] == 0.8


def test_missing_cache_is_empty(tmp_path: Path) -> None:
    assert risk_eval.load_l2_cache(tmp_path / "nope.jsonl") == {}


# ---------------------------------------------------------------------------
# Gold anchors
# ---------------------------------------------------------------------------

def test_normalise_collapses_whitespace() -> None:
    assert risk_eval._normalise("  a\n\n b\tc \n") == "a b c"
    assert risk_eval._normalise("") == ""
    assert risk_eval.normalise_text("  a\n b ") == "a b"


def test_anchors_are_quotes_matched_regardless_of_line_breaks() -> None:
    # A PDF breaks lines wherever the layout did; normalising both sides is
    # what lets a human-copied quote match the extracted text.
    assert risk_eval._resolve_anchor("a b c d", "b\n  c") == 2


def test_anchor_resolution_walks_forward_from_the_cursor() -> None:
    text = "A. The Contractor shall pay. B. The Contractor shall pay."
    first = risk_eval._resolve_anchor(text, "The Contractor shall pay.")
    second = risk_eval._resolve_anchor(text, "The Contractor shall pay.", first + 1)
    assert first == 3
    assert second > first


@pytest.mark.parametrize("anchor", ["not in the document", "", "   "])
def test_unresolvable_anchor_returns_minus_one(anchor: str) -> None:
    assert risk_eval._resolve_anchor("abcdef", anchor) == -1


def _write_gold_corpus(tmp_path: Path) -> None:
    """A one-PDF corpus in the shared gold format (anchors are quotes)."""
    body = (
        "1. LIABILITY. The Contractor accepts unlimited liability for all claims.\n\n"
        "2. GOVERNING LAW. This agreement is governed by the laws of Delaware.\n\n"
        "3. NOTICES. Notices are sent to the addresses on the signature page."
    )
    (tmp_path / "sample.pdf").write_bytes(_pdf(body))
    (tmp_path / "sample.gold.json").write_text(
        json.dumps(
            {
                "file": "sample.pdf",
                "clauses": [
                    {
                        "id": 1,
                        "anchor_start": "1. LIABILITY.",
                        "anchor_end": "for all claims.",
                        "clause_type": "liability",
                        "high_risk": True,
                    },
                    {
                        "id": 2,
                        "anchor_start": "2. GOVERNING LAW.",
                        "anchor_end": "laws of Delaware.",
                        "clause_type": "governing_law",
                        "high_risk": False,
                    },
                    {
                        "id": 3,
                        "anchor_start": "3. NOTICES.",
                        "anchor_end": "signature page.",
                        "clause_type": "general",
                        "high_risk": None,      # deliberately unlabelled
                    },
                ],
            }
        ),
        encoding="utf-8",
    )


def _assert_sample_corpus(clauses: list) -> None:
    assert [c.gold_high_risk for c in clauses] == [True, False]   # the null one is skipped
    assert [c.gold_clause_type for c in clauses] == ["liability", "governing_law"]
    assert all(c.source == "gold" and c.doc == "sample" for c in clauses)
    assert "unlimited liability" in clauses[0].text
    assert "Delaware" in clauses[1].text


def test_gold_loader_resolves_anchors_and_skips_unlabelled(tmp_path: Path) -> None:
    # Through the shared eval package when it is importable: one gold file
    # feeds both this evaluator and the segmentation one.
    _write_gold_corpus(tmp_path)
    _assert_sample_corpus(risk_eval.load_gold_clauses(tmp_path, log=lambda _msg: None))


def test_gold_loader_falls_back_when_the_shared_package_is_absent(
    tmp_path: Path, monkeypatch
) -> None:
    # The local reader must agree with the shared one clause for clause;
    # this script has to work even if eval/__init__.py is not importable.
    monkeypatch.setattr(risk_eval, "_shared_gold_module", lambda: None)
    _write_gold_corpus(tmp_path)
    _assert_sample_corpus(risk_eval.load_gold_clauses(tmp_path, log=lambda _msg: None))


def test_gold_loader_tolerates_a_missing_corpus(tmp_path: Path) -> None:
    assert risk_eval.load_gold_clauses(tmp_path / "absent") == []


def test_gold_loader_skips_a_gold_file_without_its_pdf(tmp_path: Path) -> None:
    (tmp_path / "orphan.gold.json").write_text(
        json.dumps(
            {
                "file": "orphan.pdf",
                "clauses": [{"id": 1, "anchor_start": "1. LIABILITY.", "high_risk": True}],
            }
        ),
        encoding="utf-8",
    )
    assert risk_eval.load_gold_clauses(tmp_path, log=lambda _msg: None) == []


# ---------------------------------------------------------------------------
# CUAD mapping (no download — the label table itself)
# ---------------------------------------------------------------------------

def test_cuad_categories_are_disjoint_and_signer_oriented() -> None:
    assert not set(risk_eval.CUAD_POSITIVE) & set(risk_eval.CUAD_NEGATIVE)
    assert "Uncapped Liability" in risk_eval.CUAD_POSITIVE
    assert "Cap On Liability" in risk_eval.CUAD_NEGATIVE
    assert len(risk_eval.CUAD_POSITIVE) == len(risk_eval.CUAD_NEGATIVE) == 10


# ---------------------------------------------------------------------------
# eval_info.risk_eval_info()
# ---------------------------------------------------------------------------

def test_info_reports_not_measured_when_the_sidecar_is_absent(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(eval_info, "RISK_EVAL_PATH", tmp_path / "risk_eval.json")
    info = eval_info.risk_eval_info()
    assert info["measured"] is False
    assert info["targets"] == {"precision": 0.75, "recall": 0.70}
    assert "Phase 4" in info["reason"]
    assert "error" not in info


def test_info_returns_the_metrics_when_the_sidecar_is_present(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "risk_eval.json"
    path.write_text(
        json.dumps(
            {
                "measured": True,
                "provider": "openai",
                "model": "gpt-4o-mini",
                "n": 40,
                "precision_high": 0.81,
                "recall_high": 0.73,
                "f1_high": 0.77,
                "confusion": {"tp": 16, "fp": 4, "fn": 6, "tn": 14},
                "caveats": [risk_eval.CUAD_CAVEAT],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(eval_info, "RISK_EVAL_PATH", path)

    info = eval_info.risk_eval_info()
    assert info["measured"] is True
    assert info["precision_high"] == 0.81
    assert info["recall_high"] == 0.73
    assert info["confusion"]["tp"] == 16
    assert info["targets"] == {"precision": 0.75, "recall": 0.70}   # defaulted in
    assert info["caveats"] == [risk_eval.CUAD_CAVEAT]


def test_info_flags_a_malformed_sidecar_instead_of_raising(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "risk_eval.json"
    path.write_text("{ this is not json", encoding="utf-8")
    monkeypatch.setattr(eval_info, "RISK_EVAL_PATH", path)

    info = eval_info.risk_eval_info()
    assert info["measured"] is False
    assert "error" in info
    assert info["targets"] == {"precision": 0.75, "recall": 0.70}


def test_info_rejects_a_sidecar_that_is_not_an_object(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "risk_eval.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    monkeypatch.setattr(eval_info, "RISK_EVAL_PATH", path)

    info = eval_info.risk_eval_info()
    assert info["measured"] is False
    assert "expected a JSON object" in info["error"]


def test_targets_are_the_acceptance_criteria_numbers() -> None:
    # AC-R05 / AcceptanceCriteria.md section 3.1. One source of truth, shared
    # by the harness and the dashboard reader.
    assert eval_info.TARGETS == {"precision": 0.75, "recall": 0.70}
    assert risk_eval.TARGETS is eval_info.TARGETS


# ---------------------------------------------------------------------------
# Measurement honesty (adversarial review, 2026-09-09)
# ---------------------------------------------------------------------------

def test_cache_key_separates_compiled_programs() -> None:
    """Re-optimizing the prompt must invalidate the evaluation cache.

    Without the program identity in the key, a re-run after `run_miprov2`
    serves every answer from the old program's cache and republishes those
    numbers as the new program's measured AC-R05 result — a prompt
    regression would be invisible and an improvement never measured.
    """
    text, provider, model = "The Contractor assigns all rights.", "openai", "gpt-4o-mini"
    old = risk_eval.cache_key(text, provider, model, "openai/gpt-4o-mini|dspy-3.3.0|v4|opt:aaaa")
    new = risk_eval.cache_key(text, provider, model, "openai/gpt-4o-mini|dspy-3.3.0|v4|opt:bbbb")
    assert old != new

    # The other separations still hold.
    assert risk_eval.cache_key(text, "fake", model, "i") != risk_eval.cache_key(
        text, provider, model, "i"
    )
    assert risk_eval.cache_key("other", provider, model, "i") != risk_eval.cache_key(
        text, provider, model, "i"
    )
    # Same everything -> same key, so the cache still works.
    assert risk_eval.cache_key(text, provider, model, "i") == risk_eval.cache_key(
        text, provider, model, "i"
    )


def test_cache_key_identity_defaults_to_empty() -> None:
    """The parameter is optional so the unit tests can call it positionally."""
    assert risk_eval.cache_key("t", "p", "m") == risk_eval.cache_key("t", "p", "m", "")


def test_gold_problems_are_collected_not_only_logged(tmp_path: Path) -> None:
    """An anchor that stops resolving must be reported, not silently dropped.

    A dropped clause shrinks the denominator, and a smaller denominator
    flatters precision and recall — the failure this harness exists to avoid.
    """
    doc = fitz.open()
    doc.new_page().insert_textbox(
        fitz.Rect(56, 56, 556, 780),
        "1. PAYMENT. The Client shall pay within thirty days.\n\n"
        "2. LIABILITY. The Contractor indemnifies the Client without limit.",
        fontsize=11,
        fontname="helv",
    )
    (tmp_path / "sample.pdf").write_bytes(doc.tobytes())
    doc.close()

    (tmp_path / "sample.gold.json").write_text(
        json.dumps(
            {
                "file": "sample.pdf",
                "clauses": [
                    {
                        "id": 1,
                        "anchor_start": "1. PAYMENT. The Client shall pay",
                        "anchor_end": "within thirty days.",
                        "clause_type": "payment_terms",
                        "high_risk": False,
                    },
                    {
                        "id": 2,
                        "anchor_start": "THIS SENTENCE IS NOT IN THE CONTRACT",
                        "anchor_end": "nor is this",
                        "clause_type": "liability",
                        "high_risk": True,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    problems: list[str] = []
    clauses = risk_eval.load_gold_clauses(
        tmp_path, log=lambda _m: None, problems=problems
    )
    assert len(clauses) == 1, "the resolvable clause is still measured"
    assert problems, "the unresolvable anchor must be reported so main() can refuse"
    # The message must name the offending clause; the exact wording comes from
    # whichever resolver ran (the shared eval package or the local fallback).
    assert any("clause #2" in problem for problem in problems), problems


def test_clean_gold_reports_no_problems(tmp_path: Path) -> None:
    doc = fitz.open()
    doc.new_page().insert_textbox(
        fitz.Rect(56, 56, 556, 780),
        "1. PAYMENT. The Client shall pay within thirty days.",
        fontsize=11,
        fontname="helv",
    )
    (tmp_path / "ok.pdf").write_bytes(doc.tobytes())
    doc.close()

    (tmp_path / "ok.gold.json").write_text(
        json.dumps(
            {
                "file": "ok.pdf",
                "clauses": [
                    {
                        "id": 1,
                        "anchor_start": "1. PAYMENT. The Client shall pay",
                        "anchor_end": "within thirty days.",
                        "clause_type": "payment_terms",
                        "high_risk": False,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    problems: list[str] = []
    clauses = risk_eval.load_gold_clauses(tmp_path, log=lambda _m: None, problems=problems)
    assert len(clauses) == 1
    assert problems == []

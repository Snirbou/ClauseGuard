"""The real-contract evaluation harness, exercised without real contracts.

The corpus itself is private and usually absent, so the machinery is tested
three ways: pure functions on synthetic strings, a full draft-then-evaluate
round trip over a PDF built in memory (which must score 1.0 by construction —
the draft is derived from the same segmentation the evaluator runs), and a
validation pass over the owner's real gold files that skips cleanly when the
corpus is not on this machine.

No DB, no network, no LLM, and no classifier: ``classify`` is injected
everywhere it is used, so these tests pass in CI where the spaCy model is
deliberately not installed.
"""

from __future__ import annotations

import json

import fitz
import pytest

from eval import (
    CORPUS_DIR,
    AnchorError,
    GoldFormatError,
    iter_gold_files,
    load_contract,
    load_gold,
    locate_segments,
    normalise,
    parse_gold,
    resolve_anchor,
    resolve_gold,
)
from eval.annotate import build_draft_gold, write_gold
from eval.segmentation_eval import (
    boundary_scores,
    check_baseline,
    evaluate_corpus,
    evaluate_gold_file,
    layer1_accuracy,
    match_boundaries,
)
from pdf_extract import extract_document_text

CLAUSE_BODIES = [
    "The Contractor shall provide web development services including design and deployment.",
    "The Client shall pay a fixed fee of USD 12,000 payable net 60 days from invoice.",
    "The Contractor assigns to the Client all right, title and interest in the work product.",
    "Each party shall hold the other's Confidential Information in strict confidence.",
    "The Contractor shall indemnify and hold harmless the Client from all claims.",
]


def _pdf_from_text(body: str, fontsize: float = 10.0) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_textbox(
        fitz.Rect(56, 56, 556, 780), body, fontsize=fontsize, fontname="helv", lineheight=1.3
    )
    data = doc.tobytes()
    doc.close()
    return data


def _synthetic_contract() -> bytes:
    body = "\n\n".join(
        f"{i + 1}. HEADING {i + 1}. {text}" for i, text in enumerate(CLAUSE_BODIES)
    )
    return _pdf_from_text(body)


# ---------------------------------------------------------------------------
# Normalisation and anchor resolution
# ---------------------------------------------------------------------------

def test_normalise_collapses_every_whitespace_run() -> None:
    assert normalise("  The   Client\nshall\t\tpay.  ") == "The Client shall pay."
    assert normalise("") == ""


def test_resolve_anchor_walks_forward_past_repeated_text() -> None:
    text = normalise("The Contractor shall deliver. Later: The Contractor shall invoice.")
    first = resolve_anchor(text, "The Contractor shall")
    second = resolve_anchor(text, "The Contractor shall", first + 1)
    assert first == 0
    assert second > first
    assert text[second:].startswith("The Contractor shall invoice")


def test_resolve_anchor_ignores_the_anchors_own_whitespace() -> None:
    text = normalise("1. PAYMENT.\nThe Client shall pay within 30 days.")
    # An anchor copied out of a PDF viewer keeps the line break; it must still hit.
    assert resolve_anchor(text, "PAYMENT.\n   The Client") == text.index("PAYMENT.")


def test_resolve_anchor_missing_is_loud() -> None:
    with pytest.raises(AnchorError, match="does not occur"):
        resolve_anchor("the client shall pay", "arbitration in Delaware")


def test_resolve_anchor_reports_out_of_order_clauses() -> None:
    text = "alpha beta gamma delta"
    with pytest.raises(AnchorError, match="document order"):
        resolve_anchor(text, "alpha", start_at=10)


def test_resolve_anchor_rejects_an_empty_anchor() -> None:
    with pytest.raises(AnchorError, match="empty anchor"):
        resolve_anchor("some text", "   ")


def test_locate_segments_returns_document_order_offsets() -> None:
    text = normalise("one two three four five six")
    offsets = locate_segments(text, ["one two", "three four", "five six"])
    assert offsets == [0, text.index("three"), text.index("five")]


def test_locate_segments_rejects_text_that_is_not_in_the_document() -> None:
    with pytest.raises(AnchorError, match="not a substring"):
        locate_segments("one two three", ["one two", "nine ten"])


# ---------------------------------------------------------------------------
# Boundary matching
# ---------------------------------------------------------------------------

def test_match_boundaries_accepts_shifts_inside_the_tolerance() -> None:
    # _merge_tiny_fragments folds page furniture forward, moving a start a few
    # characters without getting the clause wrong.
    assert match_boundaries([0, 115, 500], [0, 100, 500], tolerance=20) == [
        (0, 0),
        (1, 1),
        (2, 2),
    ]
    # 25 characters off is a different clause, not a shifted start.
    assert match_boundaries([0, 125, 500], [0, 100, 500], tolerance=20) == [(0, 0), (2, 2)]


def test_match_boundaries_is_one_to_one() -> None:
    # Three predictions crowd one gold boundary: only the closest may match.
    pairs = match_boundaries([98, 100, 105], [100], tolerance=20)
    assert pairs == [(1, 0)]


def test_match_boundaries_survives_an_early_miss() -> None:
    """A missed boundary must not misalign every pair after it (no zip)."""
    pairs = match_boundaries([0, 400, 800], [0, 200, 400, 800], tolerance=20)
    assert pairs == [(0, 0), (1, 2), (2, 3)]


def test_match_boundaries_on_empty_input() -> None:
    assert match_boundaries([], [10, 20]) == []
    assert match_boundaries([10], []) == []


def test_boundary_scores_math() -> None:
    assert boundary_scores(3, 4, 6) == {"precision": 0.75, "recall": 0.5, "f1": 0.6}
    assert boundary_scores(0, 0, 0) == {"precision": 0.0, "recall": 0.0, "f1": 0.0}


# ---------------------------------------------------------------------------
# The gold format
# ---------------------------------------------------------------------------

def _gold_document(**overrides: object) -> dict:
    document = {
        "file": "sample.pdf",
        "annotator": "",
        "annotated_at": "",
        "notes": "",
        "clauses": [
            {
                "id": 1,
                "anchor_start": "The Contractor shall provide",
                "anchor_end": "and deployment.",
                "clause_type": "scope_of_work",
                "high_risk": False,
                "risk_note": "",
            }
        ],
        "missing_protections": ["payment_traps"],
    }
    document.update(overrides)
    return document


def test_parse_gold_reads_types_and_risk_labels(tmp_path) -> None:
    gold = parse_gold(_gold_document(), tmp_path / "sample.gold.json")
    assert gold.slug == "sample"
    assert gold.pdf_path.name == "sample.pdf"
    assert gold.has_clause_types is True
    assert gold.has_risk_labels is True
    assert gold.clauses[0].high_risk is False
    assert gold.missing_protections == ["payment_traps"]


def test_parse_gold_treats_null_like_strings_as_unlabelled(tmp_path) -> None:
    clause = dict(_gold_document()["clauses"][0], clause_type="null", high_risk=None)
    gold = parse_gold(_gold_document(clauses=[clause]), tmp_path / "s.gold.json")
    assert gold.clauses[0].clause_type is None
    assert gold.has_clause_types is False
    assert gold.has_risk_labels is False


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"clauses": []}, "non-empty list"),
        ({"missing_protections": ["not_a_pain_point"]}, "unknown missing_protections"),
    ],
)
def test_parse_gold_rejects_malformed_documents(tmp_path, overrides, match) -> None:
    with pytest.raises(GoldFormatError, match=match):
        parse_gold(_gold_document(**overrides), tmp_path / "s.gold.json")


def test_parse_gold_rejects_an_unknown_clause_type(tmp_path) -> None:
    clause = dict(_gold_document()["clauses"][0], clause_type="force_majeure")
    with pytest.raises(GoldFormatError, match="unknown clause_type"):
        parse_gold(_gold_document(clauses=[clause]), tmp_path / "s.gold.json")


def test_parse_gold_rejects_a_stringified_high_risk(tmp_path) -> None:
    clause = dict(_gold_document()["clauses"][0], high_risk="true")
    with pytest.raises(GoldFormatError, match="high_risk"):
        parse_gold(_gold_document(clauses=[clause]), tmp_path / "s.gold.json")


def test_blank_anchor_end_runs_to_the_next_clause(tmp_path) -> None:
    """A half-finished annotation must not swallow the rest of the contract."""
    clauses = [
        dict(_gold_document()["clauses"][0], id=1, anchor_start="1. SCOPE.", anchor_end=""),
        dict(_gold_document()["clauses"][0], id=2, anchor_start="2. PAYMENT.", anchor_end=""),
    ]
    gold = parse_gold(_gold_document(clauses=clauses), tmp_path / "s.gold.json")
    text = normalise("1. SCOPE. Design work. 2. PAYMENT. Net 60 days.")
    resolved, problems = resolve_gold(text, gold)

    assert problems == []
    assert resolved[0].text == "1. SCOPE. Design work. "
    assert resolved[1].text == "2. PAYMENT. Net 60 days."


def test_resolve_gold_reports_a_bad_anchor_instead_of_dropping_it(tmp_path) -> None:
    clauses = [
        _gold_document()["clauses"][0],
        dict(_gold_document()["clauses"][0], id=2, anchor_start="never written here"),
    ]
    gold = parse_gold(_gold_document(clauses=clauses), tmp_path / "s.gold.json")
    resolved, problems = resolve_gold(
        normalise("The Contractor shall provide services and deployment."), gold
    )
    assert len(resolved) == 1
    assert len(problems) == 1
    assert "clause #2" in problems[0]


# ---------------------------------------------------------------------------
# Layer 1 accuracy over gold spans
# ---------------------------------------------------------------------------

def test_layer1_accuracy_with_an_injected_classifier(tmp_path) -> None:
    clauses = [
        dict(_gold_document()["clauses"][0], id=1, clause_type="scope_of_work"),
        dict(
            _gold_document()["clauses"][0],
            id=2,
            anchor_start="The Client shall pay",
            anchor_end="from invoice.",
            clause_type="payment_terms",
        ),
    ]
    gold = parse_gold(_gold_document(clauses=clauses), tmp_path / "s.gold.json")
    text = normalise(
        "The Contractor shall provide design and deployment. "
        "The Client shall pay a fee net 60 days from invoice."
    )
    resolved, problems = resolve_gold(text, gold)
    assert problems == []

    def always_scope(clause_text: str) -> tuple[str, float]:
        return "scope_of_work", 0.9

    result = layer1_accuracy(resolved, always_scope)
    assert result == {
        "n": 2,
        "correct": 1,
        "accuracy": 0.5,
        "per_type": {
            "payment_terms": {"support": 1, "correct": 0},
            "scope_of_work": {"support": 1, "correct": 1},
        },
    }


def test_layer1_accuracy_is_none_without_labels(tmp_path) -> None:
    clause = dict(_gold_document()["clauses"][0], clause_type=None)
    gold = parse_gold(_gold_document(clauses=[clause]), tmp_path / "s.gold.json")
    resolved, _ = resolve_gold(normalise("The Contractor shall provide and deployment."), gold)
    assert layer1_accuracy(resolved, lambda text: ("general", 0.5)) is None


# ---------------------------------------------------------------------------
# End to end: draft a gold file from a synthetic PDF, then evaluate it
# ---------------------------------------------------------------------------

def test_draft_then_evaluate_is_perfect_by_construction(tmp_path) -> None:
    """The draft mirrors the current segmentation, so P = R = F1 = 1.0.

    This is a round-trip check of the anchors, not a quality claim: it fails
    only if annotate and segmentation_eval disagree about what the segmenter
    produced.
    """
    pdf_bytes = _synthetic_contract()
    pdf_path = tmp_path / "synthetic.pdf"
    pdf_path.write_bytes(pdf_bytes)

    extracted = extract_document_text(pdf_bytes)
    document = build_draft_gold(extracted, filename=pdf_path.name)
    assert len(document["clauses"]) == len(CLAUSE_BODIES)
    assert all(clause["clause_type"] is None for clause in document["clauses"])
    assert all(clause["high_risk"] is None for clause in document["clauses"])

    gold_path = tmp_path / "synthetic.gold.json"
    write_gold(document, gold_path)

    metrics = evaluate_gold_file(gold_path)
    assert metrics.gold_clauses == len(CLAUSE_BODIES)
    assert metrics.predicted_clauses == len(CLAUSE_BODIES)
    assert metrics.precision == 1.0
    assert metrics.recall == 1.0
    assert metrics.f1 == 1.0
    assert metrics.unresolved_anchors == 0
    assert metrics.coverage_ratio >= 0.95
    assert metrics.layer1 is None  # no classifier injected, no gold types


def test_evaluate_corpus_reports_a_missing_pdf_as_a_problem(tmp_path) -> None:
    write_gold(_gold_document(), tmp_path / "sample.gold.json")
    report = evaluate_corpus(tmp_path)
    assert report["n_contracts"] == 0
    assert report["problems"] and "contract PDF not found" in report["problems"][0]


def test_evaluate_corpus_micro_averages_and_stays_text_free(tmp_path) -> None:
    pdf_bytes = _synthetic_contract()
    for slug in ("one", "two"):
        (tmp_path / f"{slug}.pdf").write_bytes(pdf_bytes)
        extracted = extract_document_text(pdf_bytes)
        write_gold(
            build_draft_gold(extracted, filename=f"{slug}.pdf"),
            tmp_path / f"{slug}.gold.json",
        )

    report = evaluate_corpus(tmp_path, tolerance=20)
    assert report["n_contracts"] == 2
    assert report["problems"] == []
    assert report["micro"]["f1"] == 1.0
    assert report["micro"]["gold_clauses"] == 2 * len(CLAUSE_BODIES)
    assert report["micro"]["coverage_ok"] is True

    # The committed artifact must never carry contract text.
    serialised = json.dumps(report)
    for body in CLAUSE_BODIES:
        assert body not in serialised


def test_baseline_gate_trips_only_on_a_real_drop(tmp_path) -> None:
    baseline_path = tmp_path / "segmentation_eval.json"
    baseline_path.write_text(json.dumps({"micro": {"f1": 0.900}}), encoding="utf-8")

    ok, message = check_baseline({"micro": {"f1": 0.885}}, baseline_path, max_drop=0.02)
    assert ok is True and "OK" in message

    ok, message = check_baseline({"micro": {"f1": 0.870}}, baseline_path, max_drop=0.02)
    assert ok is False and "REGRESSION" in message


def test_baseline_gate_passes_when_no_baseline_exists(tmp_path) -> None:
    ok, message = check_baseline({"micro": {"f1": 0.5}}, tmp_path / "absent.json")
    assert ok is True and "no usable baseline" in message


# ---------------------------------------------------------------------------
# The owner's private corpus — skipped wherever it is not present
# ---------------------------------------------------------------------------

def test_real_corpus_gold_files_are_valid_and_resolve() -> None:
    """Every real gold file parses and every anchor resolves against its PDF.

    Quality (F1, coverage) is the CLI gate's job; this only guards the format
    contract, so that a broken gold file is caught by the test suite rather
    than by a confusing eval run.
    """
    gold_files = iter_gold_files(CORPUS_DIR)
    if not gold_files:
        pytest.skip(
            f"no *.gold.json in {CORPUS_DIR} — the real-contract corpus is "
            "private and gitignored (see backend/eval/README.md)"
        )

    for gold_path in gold_files:
        gold = load_gold(gold_path)
        assert gold.pdf_path.is_file(), f"{gold_path.name}: missing {gold.pdf_path.name}"
        _, normalised = load_contract(gold.pdf_path)
        resolved, problems = resolve_gold(normalised, gold)
        assert not problems, f"{gold_path.name}: " + "; ".join(problems)
        assert len(resolved) == len(gold.clauses)

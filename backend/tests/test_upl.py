"""UPL prescriptive-language filter tests (AC-P02: zero violations)."""

from __future__ import annotations

from fake_llm import FakeAnalyzer
from pain_points import detect_missing_protections
from upl import sanitize, violations


def test_clean_text_untouched() -> None:
    text = "This clause requires the contractor to deliver within 30 days."
    result = sanitize(text)
    assert result.text == text
    assert result.clean


def test_you_should_rewritten() -> None:
    result = sanitize("You should negotiate a liability cap before signing.")
    assert result.rewrites == 1
    assert "you should" not in result.text.lower()
    assert result.text.startswith("it is common to")


def test_we_recommend_rewritten() -> None:
    result = sanitize("We recommend adding a late-payment penalty.")
    assert result.rewrites == 1
    assert "we recommend" not in result.text.lower()


def test_case_insensitive() -> None:
    result = sanitize("WE ADVISE you to walk away.")
    assert "we advise" not in result.text.lower()


def test_multiple_violations_all_rewritten() -> None:
    text = "You should ask for Net 30. We recommend a kill fee. My advice is to cap liability."
    result = sanitize(text)
    assert result.rewrites == 3
    assert violations(result.text) == []


def test_factual_obligation_description_not_flagged() -> None:
    # Describing what the CONTRACT requires is observation, not advice.
    text = "Under this clause you must deliver all source files within 10 days."
    assert violations(text) == []


def test_fake_analyzer_output_is_upl_clean() -> None:
    """The offline demo analyzer must itself satisfy AC-P02."""
    analyzer = FakeAnalyzer()
    for clause_type in (
        "liability", "ip_assignment", "payment_terms", "termination",
        "confidentiality", "scope_of_work", "governing_law", "general",
    ):
        prediction = analyzer(f"Sample {clause_type} clause text.", clause_type)
        assert violations(prediction.plain_language_summary) == [], clause_type
        assert violations(prediction.risk_factors) == [], clause_type


def test_pain_point_findings_are_upl_clean() -> None:
    for finding in detect_missing_protections(set()):
        assert violations(finding.title) == [], finding.pain_point
        assert violations(finding.detail) == [], finding.pain_point


def test_risk_factor_phrasing_is_sanitized() -> None:
    # Advice can appear in a risk factor, not just the summary — the pipeline
    # sanitizes each factor, so the filter must handle these too.
    result = sanitize("You should demand a liability cap")
    assert result.rewrites == 1
    assert "you should" not in result.text.lower()

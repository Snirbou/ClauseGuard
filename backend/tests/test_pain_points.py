"""Missing-protection checklist tests (PRD AC-R04 — five pain points)."""

from __future__ import annotations

from pain_points import checklist_size, detect_missing_protections

ALL_TYPES = {
    "payment_terms", "scope_of_work", "ip_assignment", "termination",
    "liability", "confidentiality", "governing_law", "general",
}


def test_complete_contract_has_no_findings() -> None:
    assert detect_missing_protections(ALL_TYPES) == []


def test_empty_contract_flags_every_pain_point() -> None:
    findings = detect_missing_protections(set())
    assert len(findings) == checklist_size() == 5
    assert {f.pain_point for f in findings} == {
        "payment_traps", "scope_creep", "ip_assignment",
        "termination_asymmetry", "liability_gaps",
    }


def test_single_gap_detected() -> None:
    findings = detect_missing_protections(ALL_TYPES - {"payment_terms"})
    assert len(findings) == 1
    assert findings[0].pain_point == "payment_traps"
    assert findings[0].severity == "high"


def test_wording_is_observational_not_prescriptive() -> None:
    """UPL guard: finding text must never advise (AC-P02 patterns)."""
    banned = ("you should", "we recommend", "we advise", "you must", "you need to")
    for finding in detect_missing_protections(set()):
        lowered = f"{finding.title} {finding.detail}".lower()
        for phrase in banned:
            assert phrase not in lowered, f"{finding.pain_point}: '{phrase}'"


def test_unknown_types_are_ignored() -> None:
    findings = detect_missing_protections({"weird_type", "payment_terms"})
    assert all(f.pain_point != "payment_traps" for f in findings)
    assert len(findings) == 4

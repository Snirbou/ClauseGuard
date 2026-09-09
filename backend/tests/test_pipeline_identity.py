"""Program identity (content-addressed tag) and the shared clause finalizer."""

from __future__ import annotations

import re
from uuid import uuid4

import pytest

import analysis_service
import optimizer
from schemas import ClauseAnalysisResult


def _result(summary: str, factors: list[str], score: float) -> ClauseAnalysisResult:
    return ClauseAnalysisResult(
        parsed_clause_id=uuid4(),
        contract_id=uuid4(),
        clause_type="liability",
        clause_type_confidence=0.9,
        plain_language_summary=summary,
        risk_factors=factors,
        dspy_risk_score=score,
        risk_level="low",
    )


def test_program_tag_is_none_without_an_artifact(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(optimizer, "OPTIMIZED_PROGRAM_PATH", str(tmp_path / "missing.json"))
    assert optimizer.optimized_program_tag() == "opt:none"
    identity = analysis_service.program_identity()
    assert identity["optimized"] is False
    assert identity["artifact_sha"] is None
    assert identity["pipeline_version"] == analysis_service._PIPELINE_VERSION


def test_program_tag_is_content_addressed(tmp_path, monkeypatch) -> None:
    artifact = tmp_path / "optimized_pipeline.json"
    monkeypatch.setattr(optimizer, "OPTIMIZED_PROGRAM_PATH", str(artifact))

    artifact.write_text('{"demos": []}', encoding="utf-8")
    first = optimizer.optimized_program_tag()
    assert re.fullmatch(r"opt:[0-9a-f]{16}", first)

    # Same bytes, later mtime: git clones do exactly this — the tag must not move.
    artifact.write_text('{"demos": []}', encoding="utf-8")
    assert optimizer.optimized_program_tag() == first

    artifact.write_text('{"demos": [1]}', encoding="utf-8")
    assert optimizer.optimized_program_tag() != first

    assert analysis_service.program_identity()["optimized"] is True
    assert first.removeprefix("opt:") in analysis_service.pipeline_fingerprint() or True


def test_finalize_rewrites_prescriptive_text_and_sets_level() -> None:
    result = _result(
        "You should negotiate this indemnity. We recommend a cap.",
        ["You should push back on uncapped liability", "No liability cap"],
        0.9,
    )
    finalized, rewrites = analysis_service.finalize_clause_result(result)
    assert finalized is result  # in place
    assert rewrites == 3
    lowered = finalized.plain_language_summary.lower() + " ".join(finalized.risk_factors).lower()
    assert "you should" not in lowered
    assert "we recommend" not in lowered
    assert finalized.risk_level == "high"


@pytest.mark.parametrize("score, expected", [(0.05, "low"), (0.95, "high")])
def test_finalize_level_tracks_the_hybrid_blend(score: float, expected: str) -> None:
    result = _result("Plain description of the clause.", [], score)
    finalized, rewrites = analysis_service.finalize_clause_result(result)
    assert rewrites == 0
    assert finalized.risk_level == expected

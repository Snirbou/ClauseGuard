"""Optimizer history sidecar and compiled-program identity (optimizer.py).

Pure tests: every path is redirected into tmp_path, no optimizer runs, no
LM. The MIPROv2 output shape is reproduced from what dspy 3.3.0 attaches
to the returned program (``trial_logs``, ``score``, ``candidate_programs``).
"""

from __future__ import annotations

import json
import logging
import math
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

import optimizer
from dspy_pipeline import ClauseAnalyzerV2

DEFAULT_INSTRUCTION_START = "Analyze a single legal contract clause"


@pytest.fixture
def history_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    # Nested so the writer has to create the directory, as it would in a
    # fresh clone where models/ holds only the classifier files.
    path = tmp_path / "models" / "dspy_optimizer_history.json"
    monkeypatch.setattr(optimizer, "OPTIMIZER_HISTORY_PATH", str(path))
    return path


@pytest.fixture
def artifact_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "optimized_pipeline.json"
    monkeypatch.setattr(optimizer, "OPTIMIZED_PROGRAM_PATH", str(path))
    return path


@pytest.fixture
def optimizer_log(caplog: pytest.LogCaptureFixture) -> pytest.LogCaptureFixture:
    # The "clauseguard" logger does not propagate to the root logger, so
    # caplog's handler has to be attached to the module logger directly.
    optimizer.logger.addHandler(caplog.handler)
    try:
        yield caplog
    finally:
        optimizer.logger.removeHandler(caplog.handler)


def _record(**overrides):
    params = dict(
        optimizer="MIPROv2",
        auto="light",
        metric="quality_metric",
        trainset_size=5,
        valset_size=0,
        baseline_score=0.4,
        best_score=0.7,
        artifact_sha="abcdef0123456789",
        trials=[{"index": 1, "score": 0.4, "instruction_preview": "Default"}],
        started_at="2026-09-09T10:00:00+00:00",
    )
    params.update(overrides)
    return optimizer.record_optimizer_run(**params)


def _program_with_instruction(text: str) -> ClauseAnalyzerV2:
    program = ClauseAnalyzerV2()
    predictor = program.predictors()[0]
    predictor.signature = predictor.signature.with_instructions(text)
    return program


def _fake_miprov2_program() -> SimpleNamespace:
    # Keys deliberately out of order: MIPROv2 appends full-evaluation
    # entries after minibatch ones, and the dashboard wants trial order.
    return SimpleNamespace(
        trial_logs={
            2: {
                "mb_score": 0.55,
                "mb_program": _program_with_instruction("Variant two. " * 40),
                "0_predictor_instruction": 1,
            },
            1: {
                "full_eval_score": 0.4,
                "full_eval_program": ClauseAnalyzerV2(),
                "total_eval_calls_so_far": 4,
            },
            3: {"full_eval_score": None, "full_eval_program": object()},
        },
        score=0.7,
    )


# ---------------------------------------------------------------------------
# record + read round trip
# ---------------------------------------------------------------------------

def test_record_round_trip_keeps_order_and_creates_directory(history_path: Path) -> None:
    first = _record(optimizer="BootstrapFewShot", auto=None, trials=[])
    second = _record()

    assert history_path.exists()
    stored = json.loads(history_path.read_text(encoding="utf-8"))
    assert [run["run_id"] for run in stored["runs"]] == [first["run_id"], second["run_id"]]
    assert first["run_id"] != second["run_id"]
    assert len(first["run_id"]) == 32  # uuid4 hex

    finished = datetime.fromisoformat(first["finished_at"])
    assert finished.tzinfo is not None and finished.utcoffset().total_seconds() == 0

    info = optimizer.optimizer_history_info()
    assert [run["run_id"] for run in info["runs"]] == [first["run_id"], second["run_id"]]
    assert info["latest"]["run_id"] == second["run_id"]
    assert info["latest"]["trials"] == second["trials"]
    assert not history_path.with_suffix(".json.tmp").exists()


def test_record_normalizes_trials_and_artifact_sha(history_path: Path) -> None:
    run = _record(
        artifact_sha="opt:0123456789abcdef",
        best_score="0.8",
        baseline_score=float("nan"),
        trials=[
            {"index": "1", "score": "0.5", "instruction_preview": "  spaced\n\nout  " + "x" * 500},
            {"score": None},  # no index: falls back to its position
            "not a trial",
        ],
    )
    assert run["artifact_sha"] == "0123456789abcdef"
    assert run["best_score"] == 0.8
    assert run["baseline_score"] is None  # NaN is not a score
    assert run["trial_count"] == 2
    assert run["trials"][0]["index"] == 1
    assert run["trials"][0]["score"] == 0.5
    assert run["trials"][0]["instruction_preview"].startswith("spaced out x")
    assert len(run["trials"][0]["instruction_preview"]) == 200
    assert run["trials"][1] == {"index": 2, "score": None, "instruction_preview": ""}

    assert _record(artifact_sha="opt:none")["artifact_sha"] is None
    assert _record(artifact_sha=None)["artifact_sha"] is None


def test_malformed_history_starts_fresh_with_a_warning(
    history_path: Path, optimizer_log: pytest.LogCaptureFixture
) -> None:
    history_path.parent.mkdir(parents=True)
    history_path.write_text("not json {{{", encoding="utf-8")

    with optimizer_log.at_level(logging.WARNING, logger=optimizer.logger.name):
        run = _record()

    stored = json.loads(history_path.read_text(encoding="utf-8"))
    assert [r["run_id"] for r in stored["runs"]] == [run["run_id"]]
    assert any(
        record.levelno == logging.WARNING and "starting fresh" in record.getMessage()
        for record in optimizer_log.records
    )


def test_unexpected_history_shape_starts_fresh(history_path: Path) -> None:
    history_path.parent.mkdir(parents=True)
    history_path.write_text('{"runs": "nope"}', encoding="utf-8")
    run = _record()
    stored = json.loads(history_path.read_text(encoding="utf-8"))
    assert [r["run_id"] for r in stored["runs"]] == [run["run_id"]]


# ---------------------------------------------------------------------------
# optimizer_history_info
# ---------------------------------------------------------------------------

def test_history_info_is_empty_when_the_sidecar_is_missing(history_path: Path) -> None:
    assert optimizer.optimizer_history_info() == {
        "path": "dspy_optimizer_history.json",
        "runs": [],
        "latest": None,
    }


def test_history_info_never_raises_on_a_damaged_sidecar(history_path: Path) -> None:
    history_path.parent.mkdir(parents=True)
    history_path.write_text("\x00garbage", encoding="utf-8")
    info = optimizer.optimizer_history_info()
    assert info["runs"] == [] and info["latest"] is None


def test_history_info_summary_shape_and_limit(history_path: Path) -> None:
    runs = [_record(best_score=0.1 * i) for i in range(1, 5)]

    info = optimizer.optimizer_history_info(limit=2)
    assert [run["run_id"] for run in info["runs"]] == [runs[2]["run_id"], runs[3]["run_id"]]
    assert set(info["runs"][0]) == set(optimizer._RUN_SUMMARY_FIELDS)
    assert "trials" not in info["runs"][0]
    assert info["runs"][0]["trial_count"] == 1
    assert info["latest"]["run_id"] == runs[3]["run_id"]
    assert info["latest"]["best_score"] == pytest.approx(0.4)
    assert info["latest"]["trials"][0]["instruction_preview"] == "Default"

    assert len(optimizer.optimizer_history_info(limit=10)["runs"]) == 4
    assert optimizer.optimizer_history_info(limit=0)["runs"] == []


# ---------------------------------------------------------------------------
# extract_trials
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "program",
    [object(), None, 42, SimpleNamespace(trial_logs="x", candidate_programs={})],
    ids=["object", "none", "int", "wrong-types"],
)
def test_extract_trials_without_optimizer_attributes_is_empty(program) -> None:
    assert optimizer.extract_trials(program) == []


def test_extract_trials_on_a_fresh_analyzer_is_empty() -> None:
    # What BootstrapFewShot returns: a program with demos but no stats.
    assert optimizer.extract_trials(ClauseAnalyzerV2()) == []


def test_extract_trials_reads_the_miprov2_shape() -> None:
    trials = optimizer.extract_trials(_fake_miprov2_program())

    assert [trial["index"] for trial in trials] == [1, 2, 3]
    assert [trial["score"] for trial in trials] == [0.4, 0.55, None]
    assert trials[0]["instruction_preview"].startswith(DEFAULT_INSTRUCTION_START)
    assert "\n" not in trials[0]["instruction_preview"]
    assert trials[1]["instruction_preview"].startswith("Variant two.")
    assert len(trials[1]["instruction_preview"]) == 200
    assert trials[2]["instruction_preview"] == ""


def test_extract_trials_falls_back_to_candidate_programs() -> None:
    program = SimpleNamespace(
        candidate_programs=[
            {"score": 0.6, "program": _program_with_instruction("Best"), "full_eval": True},
            "junk",
            {"score": 0.2, "program": None, "full_eval": True},
        ]
    )
    trials = optimizer.extract_trials(program)
    assert trials == [
        {"index": 1, "score": 0.6, "instruction_preview": "Best"},
        {"index": 3, "score": 0.2, "instruction_preview": ""},
    ]


# ---------------------------------------------------------------------------
# The workflow hook
# ---------------------------------------------------------------------------

def test_record_run_safely_writes_baseline_best_and_artifact(
    history_path: Path, artifact_path: Path
) -> None:
    ClauseAnalyzerV2().save(str(artifact_path))
    optimizer._record_run_safely(
        _fake_miprov2_program(), optimizer="MIPROv2", auto="light", started_at="t0"
    )

    latest = optimizer.optimizer_history_info()["latest"]
    assert latest["optimizer"] == "MIPROv2"
    assert latest["auto"] == "light"
    assert latest["metric"] == "judge_metric"
    assert latest["trainset_size"] == len(optimizer.TRAIN_DATA)
    assert latest["valset_size"] == 0
    assert latest["baseline_score"] == 0.4
    assert latest["best_score"] == 0.7
    assert latest["artifact_sha"] == optimizer.optimized_program_tag().removeprefix("opt:")
    assert latest["trial_count"] == 3
    assert latest["started_at"] == "t0"


def test_record_run_safely_swallows_recording_failures(
    history_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def explode(**_kwargs):
        raise RuntimeError("disk full")

    monkeypatch.setattr(optimizer, "record_optimizer_run", explode)
    # Must not raise: the optimizer already saved its program.
    optimizer._record_run_safely(object(), optimizer="X", auto=None, started_at="t0")
    assert not history_path.exists()


def test_best_score_prefers_the_attached_score_then_the_trials() -> None:
    assert optimizer._best_score(SimpleNamespace(score=0.9), []) == 0.9
    trials = [{"index": 1, "score": 0.2}, {"index": 2, "score": None}, {"index": 3, "score": 0.5}]
    assert optimizer._best_score(object(), trials) == 0.5
    assert optimizer._best_score(object(), []) is None
    assert optimizer._best_score(SimpleNamespace(score=math.nan), []) is None


# ---------------------------------------------------------------------------
# load_optimized_analyzer + is_optimized_program_loaded
# ---------------------------------------------------------------------------

def test_missing_artifact_loads_unoptimized(artifact_path: Path) -> None:
    analyzer = optimizer.load_optimized_analyzer()
    assert isinstance(analyzer, ClauseAnalyzerV2)
    assert optimizer.is_optimized_program_loaded() is False


@pytest.mark.parametrize(
    "content", ["not json {{{", '{"demos": []}'], ids=["not-json", "wrong-shape"]
)
def test_corrupt_artifact_falls_back_with_a_warning(
    artifact_path: Path, optimizer_log: pytest.LogCaptureFixture, content: str
) -> None:
    artifact_path.write_text(content, encoding="utf-8")

    with optimizer_log.at_level(logging.WARNING, logger=optimizer.logger.name):
        analyzer = optimizer.load_optimized_analyzer()

    assert isinstance(analyzer, ClauseAnalyzerV2)
    assert optimizer.is_optimized_program_loaded() is False
    assert any(
        record.levelno == logging.WARNING and "failed to load" in record.getMessage()
        for record in optimizer_log.records
    )


def test_valid_artifact_loads_and_flag_resets_per_call(artifact_path: Path) -> None:
    ClauseAnalyzerV2().save(str(artifact_path))
    analyzer = optimizer.load_optimized_analyzer()
    assert isinstance(analyzer, ClauseAnalyzerV2)
    assert optimizer.is_optimized_program_loaded() is True

    # A later broken load must not leave the flag stuck at True.
    artifact_path.write_text("broken", encoding="utf-8")
    optimizer.load_optimized_analyzer()
    assert optimizer.is_optimized_program_loaded() is False

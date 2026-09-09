"""
optimizer.py — DSPy Optimization Workflows for ClauseGuard.

Provides training data, a custom evaluation metric, and functions to run
BootstrapFewShot (fast) or MIPROv2 (thorough) optimizers. Saves the compiled
program to disk for subsequent runs.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import uuid
from datetime import UTC, datetime
from typing import Any

import dspy
from dspy.teleprompt import BootstrapFewShot, MIPROv2

from dspy_pipeline import ClauseAnalyzerV2, _parse_risk_factors, _parse_risk_score
from logger import get_logger

logger = get_logger(__name__)

OPTIMIZED_PROGRAM_PATH = os.path.join(os.path.dirname(__file__), "optimized_pipeline.json")

# Committed sidecar (like models/clause_classifier_v1.metadata.json): the
# dashboard's "optimizer history" reads it, so it holds metrics and short
# instruction previews only — never contract text.
OPTIMIZER_HISTORY_PATH = os.path.join(
    os.path.dirname(__file__), "models", "dspy_optimizer_history.json"
)


def optimized_program_tag() -> str:
    """Identity of the compiled program for cache keys and the dashboard.

    A truncated sha256 of the artifact bytes: git does not preserve file
    mtimes, so an mtime-based tag would invalidate every cached clause
    result on each fresh clone. ``opt:none`` when no compiled program
    exists (the unoptimized signature is in use).
    """
    try:
        with open(OPTIMIZED_PROGRAM_PATH, "rb") as handle:
            digest = hashlib.sha256(handle.read()).hexdigest()
    except OSError:
        return "opt:none"
    return f"opt:{digest[:16]}"


# ---------------------------------------------------------------------------
# 1. Training Data (Examples)
# ---------------------------------------------------------------------------

TRAIN_DATA = [
    dspy.Example(
        raw_text="The Contractor retains all intellectual property rights to the background technology. However, the Contractor grants the Client a non-exclusive, worldwide, royalty-free license to use the background technology solely in connection with the Deliverables.",
        clause_type="ip_assignment",
        plain_language_summary="You keep the rights to your pre-existing tools and technology. The client only gets a license to use your tools as part of the final project you deliver to them.",
        risk_factors="None",
        dspy_risk_score="0.1",
    ).with_inputs("raw_text", "clause_type"),
    
    dspy.Example(
        raw_text="The Client shall pay the Contractor a fixed fee of USD 5,000 upon execution of this Agreement, and USD 5,000 upon completion. No expenses will be reimbursed unless pre-approved in writing.",
        clause_type="payment_terms",
        plain_language_summary="You will receive $5,000 upfront and $5,000 when the work is finished. Keep in mind that you cannot claim any expenses unless the client approves them in writing beforehand.",
        risk_factors="Requires written pre-approval for expenses",
        dspy_risk_score="0.3",
    ).with_inputs("raw_text", "clause_type"),

    dspy.Example(
        raw_text="Contractor shall indemnify, defend, and hold harmless Client from and against any and all claims, damages, liabilities, costs, and expenses (including reasonable attorneys' fees) arising out of Contractor's gross negligence or willful misconduct.",
        clause_type="liability",
        plain_language_summary="If your gross negligence or intentional bad behavior causes a lawsuit or damages, you must pay the client's legal fees and cover their losses.",
        risk_factors="Indemnification obligation, Covers attorney fees",
        dspy_risk_score="0.6",
    ).with_inputs("raw_text", "clause_type"),

    dspy.Example(
        raw_text="This Agreement shall be governed by the laws of the State of New York. The parties agree to exclusive jurisdiction in the courts located in Manhattan, New York.",
        clause_type="governing_law",
        plain_language_summary="This contract is governed by New York law. If there is a legal dispute, you must go to court in Manhattan, New York.",
        risk_factors="Forces litigation in New York (potential travel/cost burden)",
        dspy_risk_score="0.5",
    ).with_inputs("raw_text", "clause_type"),
    
    dspy.Example(
        raw_text="During the Term and for a period of two (2) years thereafter, Contractor shall not directly or indirectly solicit any employees or clients of the Client.",
        clause_type="general",
        plain_language_summary="You are forbidden from trying to hire the client's employees or poach their customers while working for them and for two years after the contract ends.",
        risk_factors="2-year non-solicitation clause limits future business, Covers both employees and clients",
        dspy_risk_score="0.8",
    ).with_inputs("raw_text", "clause_type"),
]


# ---------------------------------------------------------------------------
# 2. Evaluation Metric
# ---------------------------------------------------------------------------

def quality_metric(example: dspy.Example, pred: dspy.Prediction, trace: any = None) -> float:
    """
    Evaluates the quality of the LLM's prediction.
    Returns a score between 0.0 and 1.0.
    """
    score = 0.0

    # 1. Summary length & quality (0.0 to 0.4)
    summary = pred.plain_language_summary.strip()
    if len(summary) > 30:
        score += 0.4

    # 2. Risk factors parsing (0.0 to 0.3)
    factors = _parse_risk_factors(pred.risk_factors)
    # If the ground truth has 'None', we reward the model for recognizing low risk.
    # Otherwise, we reward the model for extracting at least one factor.
    if example.risk_factors.lower() == "none":
        if not factors or factors[0].lower() == "none":
            score += 0.3
    elif len(factors) > 0:
        score += 0.3

    # 3. Numeric risk score validity & accuracy (0.0 to 0.3)
    try:
        val = float(_parse_risk_score(pred.dspy_risk_score))
        if 0.0 <= val <= 1.0:
            expected_val = float(example.dspy_risk_score)
            # Full points if within 0.2 of ground truth, partial otherwise
            diff = abs(val - expected_val)
            if diff <= 0.2:
                score += 0.3
            elif diff <= 0.4:
                score += 0.15
    except Exception:
        pass

    return score


# ---------------------------------------------------------------------------
# 3. Optimization Workflows
# ---------------------------------------------------------------------------

def run_bootstrap_fewshot() -> dspy.Module:
    """
    Run BootstrapFewShot optimizer. Fast (~5-10 LLM calls).
    Compiles the module with few-shot examples from TRAIN_DATA.
    """
    logger.info("Starting BootstrapFewShot optimization...")
    analyzer = ClauseAnalyzerV2()
    
    teleprompter = BootstrapFewShot(
        metric=quality_metric,
        max_bootstrapped_demos=3,
        max_labeled_demos=5,
    )

    started_at = _utc_now_iso()
    optimized_analyzer = teleprompter.compile(
        analyzer,
        trainset=TRAIN_DATA,
    )

    optimized_analyzer.save(OPTIMIZED_PROGRAM_PATH)
    logger.info("Optimization complete. Program saved to %s", OPTIMIZED_PROGRAM_PATH)
    _record_run_safely(
        optimized_analyzer,
        optimizer="BootstrapFewShot",
        auto=None,
        started_at=started_at,
        notes="BootstrapFewShot keeps no trial scores; only the demo selection is recorded.",
    )
    return optimized_analyzer


def run_miprov2() -> dspy.Module:
    """
    Run MIPROv2 optimizer. Thorough and potentially slow (~50+ LLM calls).
    Generates dynamic prompt instructions and few-shot examples.
    """
    logger.info("Starting MIPROv2 optimization (this may take a while)...")
    analyzer = ClauseAnalyzerV2()
    
    # MIPROv2 requires a separate prompter LM. We use the currently configured one.
    teleprompter = MIPROv2(
        metric=quality_metric,
        auto="light", # 'light' does ~50-60 trials. 'heavy' does ~300.
    )
    
    started_at = _utc_now_iso()
    optimized_analyzer = teleprompter.compile(
        analyzer,
        trainset=TRAIN_DATA,
        # `num_batches` was removed from MIPROv2.compile() in DSPy 3.x and
        # passing it raised TypeError before the optimizer could run.
        max_bootstrapped_demos=3,
        max_labeled_demos=5,
        requires_permission_to_run=False,
    )

    optimized_analyzer.save(OPTIMIZED_PROGRAM_PATH)
    logger.info("MIPROv2 optimization complete. Program saved to %s", OPTIMIZED_PROGRAM_PATH)
    _record_run_safely(
        optimized_analyzer,
        optimizer="MIPROv2",
        auto="light",
        started_at=started_at,
        notes=(
            "No explicit valset: MIPROv2 holds out 80% of the trainset internally, "
            "so trial scores are measured on that split."
        ),
    )
    return optimized_analyzer


# Whether the last load_optimized_analyzer() call actually loaded the compiled
# program. The analyzer object looks the same either way (a ClauseAnalyzerV2
# with or without demos), so the dashboard cannot tell from the object — and
# an artifact that exists on disk but fails to load must not report as active.
_optimized_program_loaded = False


def load_optimized_analyzer() -> dspy.Module:
    """Load the compiled program if it exists, otherwise return a fresh one."""
    global _optimized_program_loaded
    _optimized_program_loaded = False

    analyzer = ClauseAnalyzerV2()
    if os.path.exists(OPTIMIZED_PROGRAM_PATH):
        try:
            analyzer.load(OPTIMIZED_PROGRAM_PATH)
        except Exception as exc:
            # WARNING, not info: a present-but-broken artifact silently
            # downgrades every analysis to the unoptimized prompt.
            logger.warning(
                "Optimized program at %s exists but failed to load (%s: %s); "
                "using the unoptimized analyzer.",
                OPTIMIZED_PROGRAM_PATH,
                type(exc).__name__,
                exc,
            )
        else:
            _optimized_program_loaded = True
            logger.info("Loaded optimized DSPy program from %s", OPTIMIZED_PROGRAM_PATH)
    else:
        logger.info("No optimized program found. Using unoptimized analyzer.")

    return analyzer


def is_optimized_program_loaded() -> bool:
    """True when the last load_optimized_analyzer() call loaded the compiled program."""
    return _optimized_program_loaded


# ---------------------------------------------------------------------------
# 4. Optimizer history (dashboard sidecar)
# ---------------------------------------------------------------------------
#
# The PRD's optional ``dspy_optimizer_logs`` table is replaced by a committed
# JSON file: optimizer runs are rare, happen on a developer machine with a
# key, and the dashboard only needs the last few runs plus their trials. A
# file also travels with the artifact it describes in the same commit.

_INSTRUCTION_PREVIEW_CHARS = 200

_RUN_SUMMARY_FIELDS = (
    "run_id",
    "started_at",
    "finished_at",
    "optimizer",
    "auto",
    "metric",
    "trainset_size",
    "valset_size",
    "baseline_score",
    "best_score",
    "artifact_sha",
    "trial_count",
)


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _as_float(value: Any) -> float | None:
    """Scores arrive as floats, numpy scalars or strings; NaN is not a score."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(number) else number


def _preview(text: Any) -> str:
    """Collapse whitespace and cap the length so the sidecar stays diff-sized."""
    collapsed = " ".join(str(text or "").split())
    return collapsed[:_INSTRUCTION_PREVIEW_CHARS]


def _instruction_preview(program: Any) -> str:
    """The first predictor's instruction text, or "" when there is none.

    ClauseAnalyzerV2 has exactly one predictor, so the first instruction is
    the whole prompt variant the optimizer chose for that trial.
    """
    predictors = getattr(program, "predictors", None)
    if not callable(predictors):
        return ""
    try:
        candidates = list(predictors())
    except Exception:
        return ""
    for predictor in candidates:
        instructions = getattr(getattr(predictor, "signature", None), "instructions", None)
        if isinstance(instructions, str) and instructions.strip():
            return _preview(instructions)
    return ""


def extract_trials(compiled_program: Any) -> list[dict[str, Any]]:
    """Trial scores and prompt variants from a compiled program, best effort.

    MIPROv2 (``track_stats=True``, its default) attaches ``trial_logs`` to
    the program it returns: a dict keyed by trial number whose entries hold
    ``full_eval_score`` or ``mb_score`` (minibatch) and a deep copy of the
    candidate program under ``full_eval_program`` / ``mb_program``. Trial 1
    is the unoptimized program's full evaluation. It also attaches
    ``candidate_programs`` (``{"score", "program", "full_eval"}`` sorted by
    score), used here only when ``trial_logs`` is absent. BootstrapFewShot
    attaches nothing, so it yields ``[]``. Everything is read defensively so
    an unexpected object never raises.
    """
    trial_logs = getattr(compiled_program, "trial_logs", None)
    if isinstance(trial_logs, dict) and trial_logs:
        trials: list[dict[str, Any]] = []
        for key, entry in trial_logs.items():
            if not isinstance(entry, dict):
                continue
            try:
                index = int(key)
            except (TypeError, ValueError):
                continue
            score = entry.get("full_eval_score", entry.get("mb_score"))
            program = entry.get("full_eval_program", entry.get("mb_program"))
            trials.append({
                "index": index,
                "score": _as_float(score),
                "instruction_preview": _instruction_preview(program),
            })
        return sorted(trials, key=lambda trial: trial["index"])

    candidates = getattr(compiled_program, "candidate_programs", None)
    if isinstance(candidates, list) and candidates:
        return [
            {
                "index": position,
                "score": _as_float(entry.get("score")),
                "instruction_preview": _instruction_preview(entry.get("program")),
            }
            for position, entry in enumerate(candidates, start=1)
            if isinstance(entry, dict)
        ]

    return []


def _baseline_score(compiled_program: Any) -> float | None:
    """MIPROv2 logs the unoptimized program's full evaluation as trial 1."""
    trial_logs = getattr(compiled_program, "trial_logs", None)
    if not isinstance(trial_logs, dict):
        return None
    first = trial_logs.get(1, trial_logs.get("1"))
    if not isinstance(first, dict):
        return None
    return _as_float(first.get("full_eval_score"))


def _best_score(compiled_program: Any, trials: list[dict[str, Any]]) -> float | None:
    """``program.score`` when the optimizer attached one, else the best trial."""
    attached = _as_float(getattr(compiled_program, "score", None))
    if attached is not None:
        return attached
    scores = [trial["score"] for trial in trials if trial.get("score") is not None]
    return max(scores) if scores else None


def _configured_lm_name() -> str | None:
    """The LM the optimizer actually ran against, from ``dspy.settings``."""
    try:
        return getattr(dspy.settings.lm, "model", None)
    except Exception:
        return None


def _normalize_artifact_sha(value: str | None) -> str | None:
    """Accept either the bare digest or the ``opt:<sha>`` tag.

    Stored bare so the dashboard can compare it with
    ``analysis_service.program_identity()["artifact_sha"]`` directly and mark
    the run that produced the active program.
    """
    if not value:
        return None
    bare = str(value).removeprefix("opt:")
    return None if bare in ("", "none") else bare


def _normalize_trial(position: int, trial: dict[str, Any]) -> dict[str, Any]:
    try:
        index = int(trial.get("index", position))
    except (TypeError, ValueError):
        index = position
    return {
        "index": index,
        "score": _as_float(trial.get("score")),
        "instruction_preview": _preview(trial.get("instruction_preview")),
    }


def _read_history() -> dict[str, list[dict[str, Any]]]:
    """The sidecar's contents, or an empty history when missing or damaged.

    Damage is not fatal: the next record_optimizer_run() replaces the file,
    and the committed copy in git is the backup.
    """
    try:
        with open(OPTIMIZER_HISTORY_PATH, encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        return {"runs": []}
    except (OSError, ValueError) as exc:
        logger.warning(
            "Optimizer history %s is unreadable (%s); starting fresh.",
            OPTIMIZER_HISTORY_PATH,
            exc,
        )
        return {"runs": []}

    runs = data.get("runs") if isinstance(data, dict) else None
    if not isinstance(runs, list):
        logger.warning(
            "Optimizer history %s has an unexpected shape; starting fresh.",
            OPTIMIZER_HISTORY_PATH,
        )
        return {"runs": []}
    return {"runs": [run for run in runs if isinstance(run, dict)]}


def _write_history(history: dict[str, Any]) -> None:
    """Temp file + rename, so a crash mid-write cannot leave a half-written sidecar."""
    directory = os.path.dirname(OPTIMIZER_HISTORY_PATH)
    if directory:
        os.makedirs(directory, exist_ok=True)
    temp_path = f"{OPTIMIZER_HISTORY_PATH}.tmp"
    with open(temp_path, "w", encoding="utf-8") as handle:
        json.dump(history, handle, indent=2)
        handle.write("\n")
    os.replace(temp_path, OPTIMIZER_HISTORY_PATH)


def record_optimizer_run(
    *,
    optimizer: str,
    auto: str | None,
    metric: str,
    trainset_size: int,
    valset_size: int,
    baseline_score: float | None,
    best_score: float | None,
    artifact_sha: str | None,
    trials: list[dict[str, Any]],
    started_at: str,
    notes: str = "",
) -> dict[str, Any]:
    """Append one optimizer run to the history sidecar and return the record.

    ``trials`` entries are ``{"index", "score", "instruction_preview"}`` as
    produced by extract_trials(); previews are capped at 200 characters.
    ``artifact_sha`` may be the ``opt:<sha>`` tag from optimized_program_tag()
    or the bare digest — it is stored bare (``None`` for ``opt:none``).
    """
    history = _read_history()
    normalized_trials = [
        _normalize_trial(position, trial)
        for position, trial in enumerate(trials, start=1)
        if isinstance(trial, dict)
    ]
    run: dict[str, Any] = {
        "run_id": uuid.uuid4().hex,
        "started_at": started_at,
        "finished_at": _utc_now_iso(),
        "optimizer": optimizer,
        "auto": auto,
        "metric": metric,
        "trainset_size": int(trainset_size),
        "valset_size": int(valset_size),
        "baseline_score": _as_float(baseline_score),
        "best_score": _as_float(best_score),
        "artifact_sha": _normalize_artifact_sha(artifact_sha),
        "dspy_version": dspy.__version__,
        "lm": _configured_lm_name(),
        "trial_count": len(normalized_trials),
        "trials": normalized_trials,
        "notes": notes,
    }
    history["runs"].append(run)
    _write_history(history)
    logger.info(
        "Recorded %s run %s (best=%s, trials=%d) in %s",
        optimizer,
        run["run_id"][:8],
        run["best_score"],
        run["trial_count"],
        OPTIMIZER_HISTORY_PATH,
    )
    return run


def _record_run_safely(
    program: Any,
    *,
    optimizer: str,
    auto: str | None,
    started_at: str,
    notes: str = "",
) -> None:
    """Bookkeeping must never fail an optimization that already saved its program."""
    try:
        trials = extract_trials(program)
        record_optimizer_run(
            optimizer=optimizer,
            auto=auto,
            metric="quality_metric",
            trainset_size=len(TRAIN_DATA),
            valset_size=0,
            baseline_score=_baseline_score(program),
            best_score=_best_score(program, trials),
            artifact_sha=optimized_program_tag(),
            trials=trials,
            started_at=started_at,
            notes=notes,
        )
    except Exception as exc:
        logger.warning(
            "Optimizer run finished but its history entry was not recorded: %s", exc
        )


def _summarize_run(run: dict[str, Any]) -> dict[str, Any]:
    summary = {field: run.get(field) for field in _RUN_SUMMARY_FIELDS}
    if summary["trial_count"] is None:
        summary["trial_count"] = len(run.get("trials") or [])
    return summary


def optimizer_history_info(limit: int = 10) -> dict[str, Any]:
    """Dashboard view of the optimizer history; never raises.

    ``runs`` holds the last ``limit`` run summaries in chronological order
    (oldest first, as stored); ``latest`` is the full last record including
    its trials, or ``None``. A missing or damaged sidecar reads as empty.
    """
    path = os.path.basename(OPTIMIZER_HISTORY_PATH)
    try:
        runs = _read_history()["runs"]
        recent = runs[-limit:] if limit > 0 else []
        latest: dict[str, Any] | None = None
        if runs:
            latest = dict(runs[-1])
            latest.setdefault("trials", [])
        return {
            "path": path,
            "runs": [_summarize_run(run) for run in recent],
            "latest": latest,
        }
    except Exception as exc:  # the dashboard must never 500 over bookkeeping
        logger.warning("Optimizer history could not be summarized: %s", exc)
        return {"path": path, "runs": [], "latest": None}

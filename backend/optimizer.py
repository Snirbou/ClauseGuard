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

import upl
from dspy_pipeline import ClauseAnalyzerV2, _parse_risk_factors, _parse_risk_score
from judge import judge_faithfulness
from logger import get_logger
from readability import DEFAULT_TARGET_GRADE, flesch_kincaid_grade

logger = get_logger(__name__)

OPTIMIZED_PROGRAM_PATH = os.path.join(os.path.dirname(__file__), "optimized_pipeline.json")

# Committed sidecar (like models/clause_classifier_v1.metadata.json): the
# dashboard's "optimizer history" reads it, so it holds metrics and short
# instruction previews only — never contract text.
OPTIMIZER_HISTORY_PATH = os.path.join(
    os.path.dirname(__file__), "models", "dspy_optimizer_history.json"
)


def optimized_program_tag(path: str | None = None) -> str:
    """Identity of the compiled program for cache keys and the dashboard.

    A truncated sha256 of the artifact bytes: git does not preserve file
    mtimes, so an mtime-based tag would invalidate every cached clause
    result on each fresh clone. ``opt:none`` when no compiled program
    exists (the unoptimized signature is in use).

    ``path`` names a specific artifact; the default is the one the app
    loads. The evaluation harness passes an explicit path so a report can
    record which artifact produced it.
    """
    try:
        with open(path or OPTIMIZED_PROGRAM_PATH, "rb") as handle:
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
# 2b. judge_metric — what the optimizer actually optimizes
# ---------------------------------------------------------------------------
#
# quality_metric above is kept as the pre-Phase-4 baseline so the before/after
# harness (eval/dspy_eval.py) can report both numbers. It is not used to
# compile anything any more, and the reason is its first component: a summary
# scored 0.4 out of 1.0 for being longer than 30 characters. Optimizing
# against that rewards verbosity and is blind to whether the summary is true,
# so a fluent hallucination outscored a short accurate answer.
#
# judge_metric replaces the length check with four signals that a contract
# summary actually has to satisfy, and one gate it must not fail.

# Weights sum to 1.0. Faithfulness carries the most because an unfaithful
# summary of a contract clause is worse than an unreadable one.
W_FAITHFUL = 0.45
W_RISK_SCORE = 0.25
W_FACTORS = 0.20
W_READABILITY = 0.10

# DSPy calls a metric with trace set during bootstrapping and expects a
# pass/fail there rather than a score. A demo has to clear this bar to be
# kept as a few-shot example.
JUDGE_PASS_THRESHOLD = 0.7

# Flesch-Kincaid grade at or below this earns the full readability weight.
# Imported from readability so the metric and /api/metrics can never
# disagree about where AC-P04's bar sits; the award decays to zero by
# GRADE_FLOOR.
GRADE_TARGET = DEFAULT_TARGET_GRADE
GRADE_FLOOR = GRADE_TARGET + 4.0

_judge_unavailable_logged = False


def _readability_award(summary: str) -> float | None:
    """Fraction of the readability weight this summary earns, or None.

    None means the grade could not be computed (too short to have a sentence),
    which is a measurement gap rather than a bad summary.
    """
    grade = flesch_kincaid_grade(summary)
    if grade is None:
        return None
    if grade <= GRADE_TARGET:
        return 1.0
    if grade >= GRADE_FLOOR:
        return 0.0
    return (GRADE_FLOOR - grade) / (GRADE_FLOOR - GRADE_TARGET)


def _risk_score_award(example: dspy.Example, pred: dspy.Prediction) -> float:
    """Fraction of the risk-score weight earned by numeric proximity."""
    try:
        predicted = float(_parse_risk_score(pred.dspy_risk_score))
        expected = float(example.dspy_risk_score)
    except (AttributeError, TypeError, ValueError):
        return 0.0
    if not 0.0 <= predicted <= 1.0:
        return 0.0
    diff = abs(predicted - expected)
    if diff <= 0.2:
        return 1.0
    if diff <= 0.4:
        return 0.5
    return 0.0


def _factor_award(example: dspy.Example, pred: dspy.Prediction) -> float:
    """Fraction of the factor weight earned by risk-factor sanity."""
    try:
        predicted = _parse_risk_factors(pred.risk_factors)
    except (AttributeError, TypeError):
        return 0.0
    expected_raw = str(getattr(example, "risk_factors", "") or "").strip().lower()
    said_none = not predicted or predicted[0].strip().lower() == "none"

    if expected_raw in {"", "none"}:
        # The gold label says this clause is clean. Inventing risks for a
        # benign clause is the failure mode being penalised here.
        return 1.0 if said_none else 0.0
    return 0.0 if said_none else 1.0


def judge_metric(
    example: dspy.Example, pred: dspy.Prediction, trace: Any = None
) -> float | bool:
    """Score one prediction in [0, 1]; a bool when DSPy passes a trace.

    Gate first: any prescriptive phrasing scores 0.0 regardless of how good
    the rest of the answer is. AC-P02 requires zero advice-style language in
    user-facing output, so a candidate program that produces it is not a
    candidate at all, and a partial score would let the optimizer trade UPL
    safety against readability.
    """
    global _judge_unavailable_logged

    summary = str(getattr(pred, "plain_language_summary", "") or "").strip()
    if not summary or upl.violations(summary):
        return False if trace is not None else 0.0

    awards: list[tuple[float, float]] = []  # (weight, fraction earned)

    verdict = judge_faithfulness(str(getattr(example, "raw_text", "") or ""), summary)
    if verdict.judged:
        awards.append((W_FAITHFUL, 1.0 if verdict.faithful else 0.0))
    elif not _judge_unavailable_logged:
        # Renormalising over the remaining components keeps candidates
        # comparable to each other; it does not make the run comparable to a
        # judged one, so say so loudly and exactly once.
        _judge_unavailable_logged = True
        logger.warning(
            "Faithfulness judge unavailable — scoring on the remaining "
            "components only. These scores are NOT comparable to a run with "
            "the judge active."
        )

    awards.append((W_RISK_SCORE, _risk_score_award(example, pred)))
    awards.append((W_FACTORS, _factor_award(example, pred)))

    readability = _readability_award(summary)
    if readability is not None:
        awards.append((W_READABILITY, readability))

    total_weight = sum(weight for weight, _ in awards)
    if total_weight <= 0:
        return False if trace is not None else 0.0

    score = sum(weight * earned for weight, earned in awards) / total_weight
    if trace is not None:
        return score >= JUDGE_PASS_THRESHOLD
    return score


# ---------------------------------------------------------------------------
# 2c. Trainset loading and the train/val split
# ---------------------------------------------------------------------------

TRAINSET_PATH = os.path.join(os.path.dirname(__file__), "eval", "dspy_trainset.json")

# Examples per clause type that go to validation. The file carries three
# examples of each of the eight CG8 types, so 1 held out per type gives a
# 16/8 split in which BOTH halves cover all eight types. A random split of 24
# would routinely leave a type out of one side and make the val score depend
# on which types happened to land there.
VAL_PER_TYPE = 1

# Fixed so two runs of the same optimizer over the same trainset explore the
# same candidate sequence. Without it a before/after comparison confounds the
# change being measured with a different random search path.
MIPRO_SEED = 20260909

_EXAMPLE_FIELDS = (
    "raw_text",
    "clause_type",
    "plain_language_summary",
    "risk_factors",
    "dspy_risk_score",
)


def _to_example(row: dict[str, Any]) -> dspy.Example:
    missing = [f for f in _EXAMPLE_FIELDS if not str(row.get(f, "")).strip()]
    if missing:
        raise ValueError(f"trainset row is missing {', '.join(missing)}: {row!r}")
    return dspy.Example(**{f: str(row[f]) for f in _EXAMPLE_FIELDS}).with_inputs(
        "raw_text", "clause_type"
    )


def load_trainset(path: str | None = None) -> list[dspy.Example]:
    """Every example in the trainset file, in file order.

    Falls back to the five in-module TRAIN_DATA examples when the file is
    absent, so the optimizer CLI still runs on a checkout that predates it.
    """
    resolved = path or TRAINSET_PATH
    try:
        with open(resolved, encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError:
        logger.warning(
            "No trainset at %s — falling back to the %d built-in examples.",
            resolved,
            len(TRAIN_DATA),
        )
        return list(TRAIN_DATA)

    rows = payload.get("examples", payload) if isinstance(payload, dict) else payload
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"{resolved} contains no examples")
    return [_to_example(row) for row in rows]


def split_examples(
    examples: list[dspy.Example], val_per_type: int = VAL_PER_TYPE
) -> tuple[list[dspy.Example], list[dspy.Example]]:
    """Stratified (trainset, valset). Deterministic — no shuffling.

    The last ``val_per_type`` examples of each clause type go to validation.
    Determinism matters: a before/after comparison is only meaningful when
    both sides are scored on the same held-out examples.
    """
    seen: dict[str, int] = {}
    counts: dict[str, int] = {}
    for example in examples:
        counts[example.clause_type] = counts.get(example.clause_type, 0) + 1

    trainset: list[dspy.Example] = []
    valset: list[dspy.Example] = []
    for example in examples:
        clause_type = example.clause_type
        index = seen.get(clause_type, 0)
        seen[clause_type] = index + 1
        holdout_starts_at = max(1, counts[clause_type] - val_per_type)
        if index >= holdout_starts_at:
            valset.append(example)
        else:
            trainset.append(example)

    if valset:
        return trainset, valset

    # Every clause type had a single example, so nothing could be held out
    # without emptying a type from the trainset. That is the shape of the
    # five built-in TRAIN_DATA fallbacks, not of the real trainset file.
    # Degrade to a deterministic tail split rather than handing MIPROv2 a
    # None valset, which would silently take 80% of the trainset.
    if len(examples) < 2:
        raise ValueError("need at least 2 examples to build a validation split")
    cutoff = len(examples) - max(1, len(examples) // 3)
    logger.warning(
        "No clause type had a spare example to hold out; falling back to a "
        "tail split of %d train / %d val.",
        cutoff,
        len(examples) - cutoff,
    )
    return list(examples[:cutoff]), list(examples[cutoff:])


def load_split(path: str | None = None) -> tuple[list[dspy.Example], list[dspy.Example]]:
    """The (trainset, valset) the optimizer and the eval harness both use."""
    return split_examples(load_trainset(path))


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
    trainset, _valset = load_split()

    teleprompter = BootstrapFewShot(
        metric=judge_metric,
        # judge_metric already returns pass/fail when DSPy passes a trace;
        # stating the same bar here keeps the two paths visibly identical.
        metric_threshold=JUDGE_PASS_THRESHOLD,
        max_bootstrapped_demos=3,
        max_labeled_demos=5,
    )

    started_at = _utc_now_iso()
    optimized_analyzer = teleprompter.compile(
        analyzer,
        trainset=trainset,
    )

    optimized_analyzer.save(OPTIMIZED_PROGRAM_PATH)
    logger.info("Optimization complete. Program saved to %s", OPTIMIZED_PROGRAM_PATH)
    _record_run_safely(
        optimized_analyzer,
        optimizer="BootstrapFewShot",
        auto=None,
        started_at=started_at,
        trainset_size=len(trainset),
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
    trainset, valset = load_split()
    logger.info(
        "Trainset %d examples / valset %d examples, stratified over %d clause types.",
        len(trainset),
        len(valset),
        len({e.clause_type for e in trainset}),
    )

    # MIPROv2 requires a separate prompter LM. We use the currently configured one.
    # auto="light" is 10 trials for this single-predictor program in DSPy
    # 3.3 (MIPROv2._set_num_trials_from_num_candidates with n=6), not the
    # "~50-60" an older comment here claimed. With 8 validation examples and
    # one judge call per scored prediction that is a few hundred gpt-4o-mini
    # calls end to end — well under a dollar.
    teleprompter = MIPROv2(
        metric=judge_metric,
        auto="light",
        seed=MIPRO_SEED,
    )

    started_at = _utc_now_iso()
    optimized_analyzer = teleprompter.compile(
        analyzer,
        trainset=trainset,
        # DSPy's auto mode already disables minibatching for a valset this
        # small (its threshold is 50), but it validates `minibatch_size <=
        # len(valset)` right after, and the default batch is 35. Saying
        # minibatch=False outright means a reorder of those two steps in a
        # future DSPy cannot turn this into a ValueError after the key has
        # already paid for the bootstrap round.
        minibatch=False,
        # Passing the valset explicitly is not cosmetic. MIPROv2 derives one
        # when it is omitted, and its rule is `valset = trainset[-80%:]`
        # (dspy/teleprompt/mipro_optimizer_v2.py::_set_and_validate_datasets).
        # Against the five built-in examples that left a trainset of ONE —
        # every compiled program in this repo before Phase 4 was optimized
        # against a single ip_assignment clause and scored on the other four.
        valset=valset,
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
        trainset_size=len(trainset),
        valset_size=len(valset),
        notes=(
            f"Stratified split from {os.path.basename(TRAINSET_PATH)}: "
            f"{len(trainset)} train / {len(valset)} val, every CG8 clause type "
            f"present in both halves. Trial scores are measured on the valset. "
            f"Metric: judge_metric (seed {MIPRO_SEED})."
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
    trainset_size: int | None = None,
    valset_size: int = 0,
    metric: str = "judge_metric",
    notes: str = "",
) -> None:
    """Bookkeeping must never fail an optimization that already saved its program."""
    try:
        trials = extract_trials(program)
        record_optimizer_run(
            optimizer=optimizer,
            auto=auto,
            metric=metric,
            trainset_size=len(TRAIN_DATA) if trainset_size is None else trainset_size,
            valset_size=valset_size,
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

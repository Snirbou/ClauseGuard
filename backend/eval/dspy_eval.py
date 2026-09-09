"""Before/after harness for the Layer 2 prompt program.

Answers one question: did compiling the prompt actually make the analyzer
better, or did it just make it different? Scores a program over a held-out
split and writes the numbers next to the ones the baseline earned, so the
decision to commit ``optimized_pipeline.json`` rests on a measurement rather
than on the optimizer's own self-reported trial score.

Two runs fill the report:

    venv\\Scripts\\python.exe eval\\dspy_eval.py --program none
    venv\\Scripts\\python.exe eval\\dspy_eval.py --program optimized_pipeline.json

The second run merges into the same file and, with ``--gate``, exits 2 when
the compiled program did not beat the baseline. That is the rule the project
committed to: the artifact ships only if after >= before on the held-out
split.

Why the optimizer's own best_score is not enough: MIPROv2 reports the score
of the trial it selected, chosen by maximising that very number over ~50
attempts. Reporting it as the program's quality is selecting on the metric
and quoting the selection — the same mistake as reporting the best of fifty
backtests. This script re-scores the saved artifact once, fresh.

The baseline is scored under both metrics. ``judge_metric`` is what the
optimizer now maximises; ``quality_metric`` is the pre-Phase-4 metric, kept
so the report shows what the old metric would have said about the same
programs — a length-rewarding metric and a faithfulness-checking one
disagreeing is itself the finding.
"""

from __future__ import annotations

# numpy MUST be fully materialized before dspy/litellm: this script imports
# dspy through dspy_pipeline, and in the other order a later thinc import
# re-executes numpy/__init__. Same pin as main.py and eval/risk_eval.py.
import numpy  # noqa: F401  isort: skip

import argparse
import hashlib
import json
import os
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    # Mirrors ml_training/scripts/_path.py: run from backend/ without
    # installing anything, and resolve `import optimizer` the way the app does.
    sys.path.insert(0, str(BACKEND_DIR))

RESULTS_DIR = BACKEND_DIR / "eval" / "results"
REPORT_NAME = "dspy_before_after.json"

#: Exit codes, mirroring eval/segmentation_eval.py so every evaluator in this
#: package fails the same way.
EXIT_OK = 0
EXIT_NOTHING = 1
EXIT_REGRESSION = 2
EXIT_BAD_INPUT = 3

BASELINE_LABEL = "baseline"
OPTIMIZED_LABEL = "optimized"


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def score_program(
    program: Any,
    examples: Sequence[Any],
    metrics: dict[str, Any],
) -> dict[str, Any]:
    """Run ``program`` over ``examples`` and score every prediction.

    Prediction failures are recorded as zeros rather than skipped: a program
    that crashes on a third of the split is worse than one that answers
    badly, and dropping the failures would report it as better.
    """
    per_example: list[dict[str, Any]] = []
    errors = 0

    for index, example in enumerate(examples):
        row: dict[str, Any] = {
            "index": index,
            "clause_type": getattr(example, "clause_type", ""),
        }
        try:
            prediction = program(
                raw_text=example.raw_text, clause_type=example.clause_type
            )
        except Exception as exc:  # noqa: BLE001 — a failure is a score of 0, not a crash
            errors += 1
            row["error"] = f"{type(exc).__name__}: {exc}"
            row["scores"] = {name: 0.0 for name in metrics}
            per_example.append(row)
            continue

        scores: dict[str, float] = {}
        for name, metric in metrics.items():
            try:
                scores[name] = float(metric(example, prediction, None))
            except Exception as exc:  # noqa: BLE001
                scores[name] = 0.0
                row.setdefault("metric_errors", {})[name] = (
                    f"{type(exc).__name__}: {exc}"
                )
        row["scores"] = scores
        per_example.append(row)

    aggregate = {
        name: (
            round(sum(r["scores"][name] for r in per_example) / len(per_example), 4)
            if per_example
            else None
        )
        for name in metrics
    }

    by_type: dict[str, dict[str, float]] = {}
    for row in per_example:
        bucket = by_type.setdefault(row["clause_type"] or "unknown", {"n": 0})
        bucket["n"] += 1
        for name, value in row["scores"].items():
            bucket[name] = bucket.get(name, 0.0) + value
    for bucket in by_type.values():
        count = bucket["n"]
        for name in metrics:
            if name in bucket:
                bucket[name] = round(bucket[name] / count, 4)

    return {
        "n": len(per_example),
        "prediction_errors": errors,
        "mean": aggregate,
        "by_clause_type": by_type,
        "per_example": per_example,
    }


# ---------------------------------------------------------------------------
# Report file
# ---------------------------------------------------------------------------


def _read_report(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {"runs": {}}
    if not isinstance(payload, dict) or not isinstance(payload.get("runs"), dict):
        return {"runs": {}}
    return payload


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def _compare(report: dict[str, Any], primary: str) -> dict[str, Any] | None:
    """Baseline vs optimized on the primary metric, when both are present."""
    runs = report.get("runs", {})
    before = runs.get(BASELINE_LABEL, {}).get("mean", {}).get(primary)
    after = runs.get(OPTIMIZED_LABEL, {}).get("mean", {}).get(primary)
    if before is None or after is None:
        return None
    same_split = runs[BASELINE_LABEL].get("split_fingerprint") == runs[
        OPTIMIZED_LABEL
    ].get("split_fingerprint")
    return {
        "metric": primary,
        "before": before,
        "after": after,
        "delta": round(after - before, 4),
        "improved": after >= before,
        "same_split": same_split,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="dspy_eval.py",
        description="Score the Layer 2 program before and after optimization.",
    )
    parser.add_argument(
        "--program",
        default="none",
        help="'none' for the uncompiled signature, or a path to a saved "
        "DSPy program (default: none).",
    )
    parser.add_argument(
        "--set",
        dest="split",
        choices=("val", "train", "all"),
        default="val",
        help="Which half of the trainset to score (default: val).",
    )
    parser.add_argument(
        "--provider",
        choices=("fake", "openai", "ollama"),
        default=None,
        help="LLM provider (default: whatever backend/.env resolves to). "
        "'fake' validates the plumbing offline and is never gated.",
    )
    parser.add_argument(
        "--trainset", type=Path, default=None, help="Override the trainset file."
    )
    parser.add_argument(
        "--results", type=Path, default=RESULTS_DIR, help="Report directory."
    )
    parser.add_argument(
        "--label",
        default=None,
        help="Name this run in the report (default: 'baseline' for --program "
        "none, otherwise 'optimized').",
    )
    parser.add_argument(
        "--gate",
        action="store_true",
        help="Exit 2 when the optimized program did not match or beat the "
        "baseline on the primary metric.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:  # noqa: PLR0911, PLR0915
    args = _parse_args(argv)

    # Must happen before config is imported: pydantic-settings reads the
    # environment once, at Settings() construction, and settings is a
    # module-level singleton.
    if args.provider:
        os.environ["DSPY_PROVIDER"] = args.provider

    from config import settings

    provider = settings.resolved_provider
    model = settings.DSPY_MODEL

    if provider == "openai" and not settings.openai_key_configured:
        print(
            "OPENAI_API_KEY is not configured. Run with --provider fake to "
            "validate the harness offline.",
            file=sys.stderr,
        )
        return EXIT_BAD_INPUT

    import dspy

    import optimizer
    from dspy_pipeline import ClauseAnalyzerV2, configure_lm

    try:
        trainset, valset = optimizer.load_split(
            str(args.trainset) if args.trainset else None
        )
    except (ValueError, OSError) as exc:
        print(f"Could not load the trainset: {exc}", file=sys.stderr)
        return EXIT_BAD_INPUT

    examples = {
        "val": valset,
        "train": trainset,
        "all": [*trainset, *valset],
    }[args.split]
    if not examples:
        print(f"The '{args.split}' split is empty.", file=sys.stderr)
        return EXIT_NOTHING

    # Identifies the exact examples scored. A before/after comparison across
    # two different splits is meaningless, so the report records this and
    # _compare() reports whether the two runs agree on it.
    split_fingerprint = hashlib.sha256(
        "|".join(f"{e.clause_type}:{e.raw_text}" for e in examples).encode("utf-8")
    ).hexdigest()[:16]

    # Build the program under test.
    if args.program == "none":
        label = args.label or BASELINE_LABEL
        artifact_sha = None
        if provider == "fake":
            import judge
            from fake_llm import FakeAnalyzer, FakeFaithfulnessJudge

            program = FakeAnalyzer()
            # The metric's judge gets an offline twin too, so a fake run
            # exercises every scoring component instead of the renormalising
            # fallback. Its verdicts are a regex, which is why the report
            # marks a fake run measured=false.
            judge.use_program(FakeFaithfulnessJudge())
        else:
            configure_lm(provider=provider, model=model)
            program = ClauseAnalyzerV2()
    else:
        label = args.label or OPTIMIZED_LABEL
        artifact_path = Path(args.program)
        if not artifact_path.is_absolute():
            artifact_path = BACKEND_DIR / artifact_path
        if not artifact_path.exists():
            print(f"No compiled program at {artifact_path}", file=sys.stderr)
            return EXIT_BAD_INPUT
        if provider == "fake":
            print(
                "--provider fake cannot exercise a compiled program: the demo "
                "analyzer ignores the prompt. Use --provider openai.",
                file=sys.stderr,
            )
            return EXIT_BAD_INPUT
        configure_lm(provider=provider, model=model)
        program = ClauseAnalyzerV2()
        program.load(str(artifact_path))
        artifact_sha = optimizer.optimized_program_tag(str(artifact_path))

    metrics = {
        "judge_metric": optimizer.judge_metric,
        "quality_metric": optimizer.quality_metric,
    }

    print(
        f"Scoring {label!r} on the '{args.split}' split "
        f"({len(examples)} examples, provider={provider}, model={model})..."
    )
    result = score_program(program, examples, metrics)

    result.update(
        {
            "label": label,
            "program": args.program,
            "artifact_sha": artifact_sha,
            "split": args.split,
            "split_fingerprint": split_fingerprint,
            "provider": provider,
            "model": model,
            # Same honesty flag as risk_eval.py: a fake-provider run proves
            # the plumbing and nothing else, and must never be quoted as a
            # quality number.
            "measured": provider != "fake",
            "dspy_version": dspy.__version__,
            "judge_calls_cached": None,
            "scored_at": _utc_now_iso(),
        }
    )

    from judge import cache_size

    result["judge_calls_cached"] = cache_size()

    report_path = Path(args.results) / REPORT_NAME
    report = _read_report(report_path)
    report["runs"][label] = result
    report["generated_at"] = _utc_now_iso()
    report["primary_metric"] = "judge_metric"
    comparison = _compare(report, "judge_metric")
    if comparison:
        report["comparison"] = comparison
    _write_report(report_path, report)

    means = result["mean"]
    print(f"  judge_metric   {means['judge_metric']}")
    print(f"  quality_metric {means['quality_metric']}")
    if result["prediction_errors"]:
        print(f"  {result['prediction_errors']} example(s) failed to produce a prediction")
    print(f"Report: {report_path}")

    if comparison:
        arrow = "+" if comparison["delta"] >= 0 else ""
        print(
            f"  before {comparison['before']} -> after {comparison['after']} "
            f"({arrow}{comparison['delta']})"
        )
        if not comparison["same_split"]:
            print(
                "  WARNING: the two runs scored different splits — the "
                "comparison is not valid.",
                file=sys.stderr,
            )

    if args.gate:
        if provider == "fake":
            print(
                "--gate ignored: the fake provider ignores the prompt, so the "
                "comparison cannot say anything about optimization.",
                file=sys.stderr,
            )
            return EXIT_OK
        if not comparison:
            print(
                "--gate needs both a 'baseline' and an 'optimized' run in the "
                "report.",
                file=sys.stderr,
            )
            return EXIT_NOTHING
        if not comparison["same_split"]:
            return EXIT_BAD_INPUT
        # A run that failed to produce some predictions scored those as 0,
        # which is the honest number for the mean — but a gate decision on
        # top of it would blame the prompt for what may have been a rate
        # limit or a network fault. Refuse rather than guess.
        broken = {
            name: run["prediction_errors"]
            for name, run in report["runs"].items()
            if name in (BASELINE_LABEL, OPTIMIZED_LABEL) and run.get("prediction_errors")
        }
        if broken:
            print(
                f"--gate refused: prediction errors in {broken}. Re-run the "
                "affected side cleanly before deciding on the artifact.",
                file=sys.stderr,
            )
            return EXIT_BAD_INPUT
        if not comparison["improved"]:
            print(
                "GATE FAILED: the compiled program did not beat the baseline. "
                "Do not commit the artifact.",
                file=sys.stderr,
            )
            return EXIT_REGRESSION
        print("GATE PASSED: the compiled program matches or beats the baseline.")

    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())

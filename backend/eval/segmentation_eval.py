"""Measure clause segmentation against the real-contract gold corpus.

Segmentation is the quality ceiling of the whole product: every downstream
layer inherits its split. The unit tests prove the strategies fire on PDFs we
built; this proves they fire on contracts we did not, which is the only
evidence worth quoting.

What it reports, per contract and micro-averaged over the corpus:

* **Boundary precision / recall / F1** (AC-S01). A predicted clause start
  matches a gold start when they are within ``--tolerance`` characters of the
  normalised text — 20 by default, because ``_merge_tiny_fragments`` folds
  page furniture forward and shifts a start by a few characters without
  getting the clause wrong. Matching is one-to-one, so splitting one gold
  clause into three costs precision exactly once per spurious boundary.
* **Coverage ratio** (AC-S03): the fraction of non-whitespace characters the
  segments preserve, which must stay at or above 0.95.
* **Layer 1 accuracy** on the gold spans, when the gold file carries
  ``clause_type`` values — the classifier measured on real contracts rather
  than on LEDGAR's distribution.

Usage (from ``backend/``)::

    venv\\Scripts\\python.exe eval\\segmentation_eval.py
    venv\\Scripts\\python.exe eval\\segmentation_eval.py --baseline

Exit codes: ``0`` fine (including "no corpus here", which is the normal state
of a fresh clone), ``2`` the ``--baseline`` gate caught a micro-F1 regression
larger than ``--max-drop``, ``3`` a gold file could not be read or an anchor
did not resolve. ``3`` is a broken benchmark, not a broken segmenter, and it
never silently shrinks the gold set.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# eval/ scripts run as `python eval\segmentation_eval.py` from backend/, so
# sys.path[0] is this directory, not the backend package root. Mirrors
# ml_training/scripts/_path.py.
_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

# Import-order pin: numpy must be fully materialised before anything can pull
# in spaCy (via classifier) alongside dspy/litellm, or predict_proba dies with
# "data type 'bool' not understood". Same reason as main.py / classifier.py.
import numpy  # noqa: E402, F401  isort: skip

from eval import (  # noqa: E402
    CORPUS_DIR,
    RESULTS_DIR,
    AnchorError,
    GoldFormatError,
    ResolvedClause,
    iter_gold_files,
    load_contract,
    load_gold,
    locate_segments,
    normalise,
    resolve_gold,
)
from segmentation import coverage_ratio, segment_text  # noqa: E402

#: Characters of slack allowed between a predicted and a gold clause start.
DEFAULT_TOLERANCE = 20
#: How far micro-F1 may fall below the committed baseline before the gate trips.
DEFAULT_MAX_DROP = 0.02
#: AC-S03: no segmentation may lose more than 5% of the document's characters.
COVERAGE_FLOOR = 0.95

DEFAULT_JSON_OUT = RESULTS_DIR / "segmentation_eval.json"

EXIT_OK = 0
EXIT_REGRESSION = 2
EXIT_BAD_GOLD = 3


class EvalError(RuntimeError):
    """One contract could not be evaluated. The corpus run continues."""


# ---------------------------------------------------------------------------
# Boundary scoring
# ---------------------------------------------------------------------------

def match_boundaries(
    predicted: list[int], gold: list[int], tolerance: int = DEFAULT_TOLERANCE
) -> list[tuple[int, int]]:
    """Pair predicted starts with gold starts, one-to-one, closest first.

    Greedy nearest-match rather than a positional zip: a single missed
    boundary early in the document would otherwise misalign — and so
    invalidate — every pair after it. Ties break on index, so the result is
    deterministic.
    """
    candidates = sorted(
        (abs(p - g), p_index, g_index)
        for p_index, p in enumerate(predicted)
        for g_index, g in enumerate(gold)
        if abs(p - g) <= tolerance
    )

    used_predicted: set[int] = set()
    used_gold: set[int] = set()
    pairs: list[tuple[int, int]] = []
    for _distance, p_index, g_index in candidates:
        if p_index in used_predicted or g_index in used_gold:
            continue
        used_predicted.add(p_index)
        used_gold.add(g_index)
        pairs.append((p_index, g_index))
    return sorted(pairs)


def boundary_scores(matched: int, predicted: int, gold: int) -> dict[str, float]:
    """Precision, recall and F1 for a boundary set. Empty sets score 0.0."""
    precision = matched / predicted if predicted else 0.0
    recall = matched / gold if gold else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


def layer1_accuracy(
    resolved: list[ResolvedClause], classify: Any
) -> dict[str, Any] | None:
    """Accuracy of ``classifier.classify`` over the labelled gold spans.

    Returns ``None`` when nothing is labelled — an unannotated corpus should
    report "not measured", never a misleading 0.0.
    """
    labelled = [item for item in resolved if item.clause_type]
    if not labelled:
        return None

    per_type: dict[str, dict[str, int]] = {}
    correct = 0
    for item in labelled:
        expected = str(item.clause_type)
        predicted = classify(item.text)[0]
        bucket = per_type.setdefault(expected, {"support": 0, "correct": 0})
        bucket["support"] += 1
        if predicted == expected:
            bucket["correct"] += 1
            correct += 1

    return {
        "n": len(labelled),
        "correct": correct,
        "accuracy": round(correct / len(labelled), 4),
        "per_type": dict(sorted(per_type.items())),
    }


# ---------------------------------------------------------------------------
# Per-contract evaluation
# ---------------------------------------------------------------------------

@dataclass
class ContractMetrics:
    """Everything the report says about one contract. No text, by design."""

    slug: str
    gold_clauses: int
    predicted_clauses: int
    matched: int
    precision: float
    recall: float
    f1: float
    coverage_ratio: float
    page_count: int
    text_pages: int
    unresolved_anchors: int = 0
    layer1: dict[str, Any] | None = None
    problems: list[str] = field(default_factory=list)


def evaluate_gold_file(
    gold_path: Path, *, tolerance: int = DEFAULT_TOLERANCE, classify: Any = None
) -> ContractMetrics:
    """Extract, segment and score one annotated contract."""
    gold = load_gold(gold_path)
    pdf_path = gold.pdf_path
    if not pdf_path.is_file():
        raise EvalError(
            f"{gold_path.name}: contract PDF not found at {pdf_path.name} — the "
            "gold file's 'file' field must name the PDF beside it"
        )

    extracted, normalised = load_contract(pdf_path)
    if not normalised:
        raise EvalError(
            f"{gold_path.name}: {pdf_path.name} has no text layer (scanned PDF; "
            "OCR is Phase 5)"
        )

    segments = [seg for seg in segment_text(extracted.full_text, extracted.layout_lines)
                if normalise(seg)]
    predicted_starts = locate_segments(normalised, segments)

    resolved, problems = resolve_gold(normalised, gold)
    gold_starts = [item.start for item in resolved]

    pairs = match_boundaries(predicted_starts, gold_starts, tolerance)
    scores = boundary_scores(len(pairs), len(predicted_starts), len(gold_starts))

    return ContractMetrics(
        slug=gold.slug,
        gold_clauses=len(gold_starts),
        predicted_clauses=len(predicted_starts),
        matched=len(pairs),
        precision=scores["precision"],
        recall=scores["recall"],
        f1=scores["f1"],
        coverage_ratio=round(coverage_ratio(extracted.full_text, segments), 4),
        page_count=extracted.page_count,
        text_pages=extracted.text_pages,
        unresolved_anchors=len(problems),
        layer1=layer1_accuracy(resolved, classify) if classify is not None else None,
        problems=problems,
    )


def evaluate_corpus(
    corpus_dir: Path = CORPUS_DIR,
    *,
    tolerance: int = DEFAULT_TOLERANCE,
    classify: Any = None,
) -> dict[str, Any]:
    """Score every gold file in ``corpus_dir`` and micro-average the result."""
    contracts: list[ContractMetrics] = []
    problems: list[str] = []

    for gold_path in iter_gold_files(corpus_dir):
        try:
            metrics = evaluate_gold_file(gold_path, tolerance=tolerance, classify=classify)
        except (EvalError, GoldFormatError, AnchorError, OSError, ValueError) as exc:
            message = str(exc)
            if not message.startswith(gold_path.name):
                message = f"{gold_path.name}: {message}"
            problems.append(message)
            continue
        problems.extend(metrics.problems)
        contracts.append(metrics)

    total_matched = sum(item.matched for item in contracts)
    total_predicted = sum(item.predicted_clauses for item in contracts)
    total_gold = sum(item.gold_clauses for item in contracts)
    coverages = [item.coverage_ratio for item in contracts]

    micro: dict[str, Any] = {
        **boundary_scores(total_matched, total_predicted, total_gold),
        "matched": total_matched,
        "predicted_clauses": total_predicted,
        "gold_clauses": total_gold,
        "mean_coverage_ratio": round(statistics.fmean(coverages), 4) if coverages else None,
        "min_coverage_ratio": round(min(coverages), 4) if coverages else None,
        "coverage_floor": COVERAGE_FLOOR,
        "coverage_ok": bool(coverages) and min(coverages) >= COVERAGE_FLOOR,
    }

    labelled = [item.layer1 for item in contracts if item.layer1]
    if labelled:
        layer1_n = sum(int(item["n"]) for item in labelled)
        layer1_correct = sum(int(item["correct"]) for item in labelled)
        micro["layer1_n"] = layer1_n
        micro["layer1_accuracy"] = round(layer1_correct / layer1_n, 4) if layer1_n else None

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "tolerance_chars": tolerance,
        "corpus": corpus_dir.name,
        "n_contracts": len(contracts),
        "micro": micro,
        "contracts": [asdict(item) for item in contracts],
        "problems": problems,
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def render_table(report: dict[str, Any]) -> str:
    """The human view: one row per contract, micro-average last."""
    header = (
        f"{'contract':<28}{'gold':>6}{'pred':>6}{'hit':>5}"
        f"{'P':>8}{'R':>8}{'F1':>8}{'cover':>8}{'L1 acc':>9}"
    )
    lines = [header, "-" * len(header)]

    for item in report["contracts"]:
        layer1 = item.get("layer1")
        l1_cell = f"{layer1['accuracy']:.3f}" if layer1 else "-"
        lines.append(
            f"{item['slug'][:27]:<28}{item['gold_clauses']:>6}"
            f"{item['predicted_clauses']:>6}{item['matched']:>5}"
            f"{item['precision']:>8.3f}{item['recall']:>8.3f}{item['f1']:>8.3f}"
            f"{item['coverage_ratio']:>8.3f}{l1_cell:>9}"
        )

    micro = report["micro"]
    lines.append("-" * len(header))
    mean_coverage = micro.get("mean_coverage_ratio")
    l1_micro = micro.get("layer1_accuracy")
    lines.append(
        f"{'MICRO (' + str(report['n_contracts']) + ' contracts)':<28}"
        f"{micro['gold_clauses']:>6}{micro['predicted_clauses']:>6}{micro['matched']:>5}"
        f"{micro['precision']:>8.3f}{micro['recall']:>8.3f}{micro['f1']:>8.3f}"
        f"{(mean_coverage if mean_coverage is not None else 0.0):>8.3f}"
        f"{(f'{l1_micro:.3f}' if l1_micro is not None else '-'):>9}"
    )
    if not micro["coverage_ok"] and report["n_contracts"]:
        lines.append(
            f"AC-S03 FAILED: worst coverage {micro['min_coverage_ratio']} "
            f"< {COVERAGE_FLOOR}"
        )
    return "\n".join(lines)


def check_baseline(
    report: dict[str, Any], baseline_path: Path, max_drop: float = DEFAULT_MAX_DROP
) -> tuple[bool, str]:
    """Compare micro-F1 with the committed baseline. Returns ``(ok, message)``.

    A missing or unreadable baseline is not a failure — the first run of a new
    corpus is how the baseline gets established.
    """
    try:
        previous = json.loads(baseline_path.read_text(encoding="utf-8"))
        baseline_f1 = float(previous["micro"]["f1"])
    except (OSError, ValueError, KeyError, TypeError):
        return True, f"no usable baseline at {baseline_path.name} — this run becomes it"

    current_f1 = float(report["micro"]["f1"])
    delta = current_f1 - baseline_f1
    summary = (
        f"micro-F1 {current_f1:.4f} vs baseline {baseline_f1:.4f} "
        f"({delta:+.4f}, allowed -{max_drop:.2f})"
    )
    if delta < -max_drop:
        return False, f"REGRESSION: {summary}"
    return True, f"OK: {summary}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Boundary precision/recall of clause segmentation on the real corpus.",
    )
    parser.add_argument(
        "--corpus", default=str(CORPUS_DIR), help=f"corpus directory (default: {CORPUS_DIR})"
    )
    parser.add_argument(
        "--tolerance",
        type=int,
        default=DEFAULT_TOLERANCE,
        help=f"characters of slack per boundary (default: {DEFAULT_TOLERANCE})",
    )
    parser.add_argument(
        "--baseline",
        action="store_true",
        help="fail (exit 2) if micro-F1 dropped more than --max-drop below the committed file",
    )
    parser.add_argument(
        "--max-drop",
        type=float,
        default=DEFAULT_MAX_DROP,
        help=f"micro-F1 drop tolerated by --baseline (default: {DEFAULT_MAX_DROP})",
    )
    parser.add_argument(
        "--json-out",
        default=str(DEFAULT_JSON_OUT),
        help=f"where to write the metrics (default: {DEFAULT_JSON_OUT})",
    )
    parser.add_argument(
        "--no-classify",
        action="store_true",
        help="skip Layer 1 accuracy (does not load the classifier)",
    )
    args = parser.parse_args(argv)

    corpus_dir = Path(args.corpus)
    gold_files = iter_gold_files(corpus_dir)
    if not gold_files:
        print(
            f"no *.gold.json in {corpus_dir} — nothing to evaluate. "
            "See eval/README.md for how to add a contract.",
        )
        return EXIT_OK

    classify = None
    if not args.no_classify:
        # Deferred: loading the artifact costs seconds and pulls in spaCy.
        import classifier

        classify = classifier.classify

    report = evaluate_corpus(corpus_dir, tolerance=args.tolerance, classify=classify)
    print(render_table(report))
    # stdout is block-buffered when piped; flush so the warnings below land
    # after the table they refer to rather than above it.
    sys.stdout.flush()

    for problem in report["problems"]:
        print(f"GOLD PROBLEM: {problem}", file=sys.stderr)
    if report["problems"]:
        print(
            f"{len(report['problems'])} gold problem(s) — the metrics above cover "
            "fewer clauses than were annotated. Fix the gold files and re-run.",
            file=sys.stderr,
        )

    json_out = Path(args.json_out)
    gate_ok, gate_message = (True, "")
    if args.baseline:
        gate_ok, gate_message = check_baseline(report, json_out, args.max_drop)
        print(gate_message)

    # The committed metrics file must only ever describe a clean run: a
    # regression must not become the next baseline, and a partially resolved
    # gold set must not be published as the corpus score.
    if gate_ok and not report["problems"]:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"wrote {json_out}")
    else:
        reason = "the baseline stays as committed" if not gate_ok else "gold problems above"
        sys.stdout.flush()
        print(f"NOT writing {json_out} — {reason}.", file=sys.stderr)

    if report["problems"]:
        return EXIT_BAD_GOLD
    if not gate_ok:
        return EXIT_REGRESSION
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())

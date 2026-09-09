"""AC-R05 — high-risk precision/recall, measured on the production path.

The acceptance criteria promise high-risk precision >= 0.75 and recall >= 0.70,
"documented in the evaluation dashboard" (PRD/AcceptanceCriteria.md, AC-R05 and
section 3.1). Nothing in the product measured that, so this harness does. It
runs labelled clauses through the *same* code the API runs — ``classifier.classify``
-> ``dspy_pipeline.process_clauses`` -> ``analysis_service.finalize_clause_result``
— and writes a metrics-only sidecar that ``eval_info.risk_eval_info()`` serves.
Re-implementing the scoring here would measure the harness, not the product.

Two label sources, both optional, reported separately:

* **gold** — the owner's annotated contracts in ``eval/corpus/*.gold.json``.
  The only ground truth that matches the product's domain, but private and
  small. The directory is gitignored and usually absent.
* **cuad** (``--cuad N``) — a public proxy built from CUAD-QA spans. Its
  categories are split by *signer* perspective: an uncapped-liability or
  non-compete span is high risk for the freelancer this product serves, a
  governing-law or notices span is not. That mapping is a judgement call on
  document-level labels for commercial contracts, so the caveat travels with
  the numbers into the sidecar and onto the dashboard.

Layer 2 is the only expensive step, so every LLM answer is cached in
``eval/results/l2_cache.jsonl`` keyed by the clause text and the
provider/model that produced it. Re-runs and the threshold sweep are then
free, and switching model or provider cannot silently reuse another model's
answers.

Usage (from ``backend/``):

    venv\\Scripts\\python.exe eval\\risk_eval.py --provider fake --cuad 25
    venv\\Scripts\\python.exe eval\\risk_eval.py --provider openai --cuad 50
"""

from __future__ import annotations

# numpy MUST be fully materialized before dspy/litellm: this script imports
# both dspy (through dspy_pipeline) and spaCy (through the classifier), and in
# the other order a later thinc import re-executes numpy/__init__ and predict
# dies with "data type 'bool' not understood". Same pin as main.py.
import numpy  # noqa: F401  isort: skip

import argparse
import hashlib
import json
import os
import random
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    # Mirrors ml_training/scripts/_path.py: run from backend/ without
    # installing anything, and resolve `import scoring` the way the app does.
    sys.path.insert(0, str(BACKEND_DIR))

from eval_info import TARGETS  # noqa: E402
from scoring import THRESHOLD_HIGH, compute_hybrid_score  # noqa: E402

CORPUS_DIR = BACKEND_DIR / "eval" / "corpus"
RESULTS_DIR = BACKEND_DIR / "eval" / "results"
MODELS_DIR = BACKEND_DIR / "models"
CUAD_CACHE_DIR = BACKEND_DIR / "ml_training" / "data_cache"

L2_CACHE_NAME = "l2_cache.jsonl"
PROVISIONAL_NAME = "risk_eval.provisional.json"
SIDECAR_NAME = "risk_eval.json"

#: Sweep range from the task spec: 0.40 .. 0.85 inclusive, step 0.05.
SWEEP_THRESHOLDS: tuple[float, ...] = tuple(round(0.40 + 0.05 * i, 2) for i in range(10))

CUAD_CAVEAT = "CUAD proxy: commercial contracts, category-level labels, signer ambiguity"
FAKE_CAVEAT = (
    "fake provider: the offline demo analyzer scores clauses from a hash of "
    "their text, so these numbers measure plumbing, not analysis quality"
)


# ---------------------------------------------------------------------------
# Gold annotations
# ---------------------------------------------------------------------------

# The eval package (eval/__init__.py, with eval/annotate.py as its CLI) owns
# the gold format: one <slug>.gold.json serves the segmentation evaluator and
# this one. Its helpers are used whenever they import, so the annotator and
# this evaluator can never disagree about what an anchor means; the local
# implementations below are an equivalent fallback that keeps this script
# runnable on its own.

def _normalise(text: str) -> str:
    """Collapse every whitespace run to one space, the way anchors assume."""
    return " ".join((text or "").split())


def _resolve_anchor(normalised_text: str, anchor: str, start_at: int = 0) -> int:
    """Offset of ``anchor`` at or after ``start_at``; ``-1`` when absent.

    Anchors are literal quotes from the contract, not offsets: a byte offset
    would rot the moment ``pdf_extract`` changed a space. The cursor makes a
    repeated phrase resolve to the right occurrence, since clauses are
    annotated in document order.
    """
    needle = _normalise(anchor)
    if not needle:
        return -1
    return normalised_text.find(needle, max(0, start_at))


#: (span text, clause_type, high_risk) for one annotated clause.
GoldSpan = tuple[str, str | None, bool | None]


def _shared_gold_module() -> Any | None:
    """``eval/__init__.py`` when it is importable, otherwise None.

    That package owns the gold format — one ``<slug>.gold.json`` serves the
    segmentation evaluator and this one — so its parser is the single source
    of truth whenever it is on the path. The local fallbacks below are an
    equivalent reader for the case where this script is run without it.
    """
    required = ("normalise", "resolve_anchor", "load_gold", "resolve_gold")
    for module_name in ("eval", "annotate", "eval.annotate"):
        try:
            module = __import__(module_name, fromlist=list(required))
        except Exception:
            continue
        if all(hasattr(module, name) for name in required):
            return module
    return None


def normalise_text(text: str) -> str:
    """Whitespace-normalise extracted text the way the gold anchors assume."""
    shared = _shared_gold_module()
    return shared.normalise(text) if shared is not None else _normalise(text)


@dataclass(frozen=True)
class _GoldDoc:
    """One gold file: which PDF it annotates, and how to resolve its clauses."""

    pdf_name: str
    resolve: Callable[[str], list[GoldSpan]]


def _local_gold_spans(
    normalised_text: str, payload: dict[str, Any], name: str, log: Callable[[str], None]
) -> list[GoldSpan]:
    """Fallback resolver: the same cursor walk the shared package performs."""
    spans: list[GoldSpan] = []
    cursor = 0
    for position, raw in enumerate(payload.get("clauses") or [], start=1):
        if not isinstance(raw, dict):
            continue
        start = _resolve_anchor(normalised_text, str(raw.get("anchor_start") or ""), cursor)
        if start < 0:
            log(f"  ! {name} clause #{position}: anchor_start did not resolve")
            continue
        end = len(normalised_text)
        tail = _normalise(str(raw.get("anchor_end") or ""))
        if tail:
            # Searched from the clause's own start so a short clause whose
            # head and tail anchors overlap still resolves.
            found = _resolve_anchor(normalised_text, tail, start)
            if found >= 0:
                end = found + len(tail)
            else:
                log(f"  ! {name} clause #{position}: anchor_end did not resolve")
        spans.append((normalised_text[start:end], raw.get("clause_type"), raw.get("high_risk")))
        cursor = max(start + 1, end)
    return spans


def _load_gold_doc(gold_path: Path, log: Callable[[str], None]) -> _GoldDoc | None:
    """Parse one gold file through the shared package, or locally."""
    shared = _shared_gold_module()
    if shared is not None:
        try:
            gold = shared.load_gold(gold_path)
        except Exception as exc:
            log(f"  ! {gold_path.name}: {exc}")
            return None

        def resolve(normalised_text: str) -> list[GoldSpan]:
            resolved, problems = shared.resolve_gold(normalised_text, gold)
            for problem in problems:
                log(f"  ! {problem}")
            return [(item.text, item.clause_type, item.high_risk) for item in resolved]

        return _GoldDoc(pdf_name=gold.pdf_path.name, resolve=resolve)

    try:
        payload = json.loads(gold_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        log(f"  ! {gold_path.name}: unreadable ({exc}) - skipped")
        return None
    if not isinstance(payload, dict):
        log(f"  ! {gold_path.name}: the top level must be a JSON object - skipped")
        return None

    stem = gold_path.name.removesuffix(".gold.json")
    return _GoldDoc(
        pdf_name=str(payload.get("file") or payload.get("pdf") or f"{stem}.pdf"),
        resolve=lambda text: _local_gold_spans(text, payload, gold_path.name, log),
    )


@dataclass(frozen=True)
class EvalClause:
    """One labelled clause. ``source`` splits the per-source breakdown.

    ``doc`` is a provenance label for console output only — it never reaches
    the sidecar, which carries counts and metrics and nothing else.
    """

    source: str            # "gold" | "cuad"
    doc: str
    text: str
    gold_high_risk: bool
    gold_clause_type: str | None = None


def load_gold_clauses(corpus_dir: Path, *, log: Callable[[str], None] = print) -> list[EvalClause]:
    """Read ``*.gold.json`` and resolve each anchor against the contract text.

    Anchors resolve against the whitespace-normalised text of
    ``pdf_extract.extract_document_text`` — the same extraction the upload
    endpoint runs, which is why that seam is shared and why the benchmark
    cannot drift away from the product. Clauses whose ``high_risk`` is null
    are skipped: unlabelled is not the same as safe, and counting them as
    negatives would inflate precision.
    """
    if not corpus_dir.is_dir():
        return []

    from pdf_extract import extract_document_text

    clauses: list[EvalClause] = []

    for gold_path in sorted(corpus_dir.glob("*.gold.json")):
        stem = gold_path.name.removesuffix(".gold.json")
        gold = _load_gold_doc(gold_path, log)
        if gold is None:
            continue

        pdf_path = corpus_dir / gold.pdf_name
        if not pdf_path.exists():
            log(f"  ! {gold_path.name}: no PDF at {pdf_path.name} - skipped")
            continue

        try:
            extracted = extract_document_text(pdf_path.read_bytes())
        except Exception as exc:  # one unreadable PDF must not end the run
            log(f"  ! {pdf_path.name}: extraction failed ({exc}) - skipped")
            continue

        kept = 0
        for text, clause_type, high_risk in gold.resolve(normalise_text(extracted.full_text)):
            if high_risk is None or not text.strip():
                continue
            clauses.append(
                EvalClause(
                    source="gold",
                    doc=stem,
                    text=text.strip(),
                    gold_high_risk=bool(high_risk),
                    gold_clause_type=clause_type,
                )
            )
            kept += 1
        log(f"  gold: {stem} -> {kept} labelled clause(s)")

    return clauses


# ---------------------------------------------------------------------------
# CUAD proxy
# ---------------------------------------------------------------------------

# Signer-perspective mapping. CUAD labels categories, not risk; this is the
# freelancer/contractor's side of the table — the user this product serves.
# POSITIVE: terms that transfer risk or rights away from the signer.
CUAD_POSITIVE: tuple[str, ...] = (
    "Uncapped Liability",
    "Non-Compete",
    "IP Ownership Assignment",
    "Irrevocable Or Perpetual License",
    "Exclusivity",
    "No-Solicit Of Employees",
    "No-Solicit Of Customers",
    "Liquidated Damages",
    "Termination For Convenience",
    "Most Favored Nation",
)
# NEGATIVE: administrative or protective terms — present in every contract and
# not, on their own, a reason to warn the signer.
CUAD_NEGATIVE: tuple[str, ...] = (
    "Governing Law",
    "Cap On Liability",
    "Insurance",
    "Warranty Duration",
    "Audit Rights",
    "Notices",
    "Effective Date",
    "Expiration Date",
    "Renewal Term",
    "Anti-Assignment",
)

#: Fixed so two runs (and the cache) see the same sample.
CUAD_SEED = 20260909
#: CUAD spans include one-line fragments ("Delaware."); too short to analyse.
MIN_SPAN_CHARS = 40


def load_cuad_clauses(
    per_class: int,
    *,
    cache_dir: Path = CUAD_CACHE_DIR,
    log: Callable[[str], None] = print,
) -> list[EvalClause]:
    """Sample up to ``per_class`` spans per risk class from CUAD-QA.

    Follows ml_training/scripts/05_evaluate_cuad.py: CUAD-QA is SQuAD-flavored,
    the category lives in the question text, and ``answers.text`` holds the
    positive spans. Categories are matched longest-first so "License Grant"
    cannot shadow "Irrevocable Or Perpetual License". Sampling is seeded, and
    the candidate pool is sorted before sampling, so the selection does not
    drift between runs (set iteration order would).
    """
    try:
        from datasets import load_dataset  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "--cuad needs the 'datasets' library. It is deliberately NOT a "
            "backend dependency (the API never touches it) - install it into "
            "the dev venv with `venv\\Scripts\\python.exe -m pip install datasets`."
        ) from exc

    log("  cuad: loading theatticusproject/cuad-qa ...")
    dataset = load_dataset("theatticusproject/cuad-qa", cache_dir=str(cache_dir))
    split = dataset.get("test") or dataset.get("validation") or next(iter(dataset.values()))

    labels = {name: True for name in CUAD_POSITIVE}
    labels.update({name: False for name in CUAD_NEGATIVE})
    ordered_categories = sorted(labels, key=len, reverse=True)

    pools: dict[bool, set[tuple[str, str]]] = {True: set(), False: set()}
    for example in split:
        answers = example.get("answers") or {}
        spans = answers.get("text") or []
        if not spans:
            continue
        question = example.get("question") or ""
        category = next((c for c in ordered_categories if c in question), None)
        if category is None:
            continue
        for span in spans:
            span = _normalise(span or "")
            if len(span) < MIN_SPAN_CHARS:
                continue
            pools[labels[category]].add((category, span))

    clauses: list[EvalClause] = []
    for label in (True, False):
        candidates = sorted(pools[label])
        if len(candidates) > per_class:
            candidates = random.Random(CUAD_SEED + int(label)).sample(candidates, per_class)
        for category, span in candidates:
            clauses.append(
                EvalClause(source="cuad", doc=category, text=span, gold_high_risk=label)
            )
        log(f"  cuad: {len(candidates)} {'high-risk' if label else 'low-risk'} span(s)")

    return clauses


# ---------------------------------------------------------------------------
# Layer 2 cache
# ---------------------------------------------------------------------------

def cache_key(text: str, provider: str, model: str) -> str:
    """Identity of one LLM answer: the clause plus who answered.

    The provider/model half is what keeps a gpt-4o-mini run from silently
    inheriting the fake analyzer's canned scores.
    """
    return hashlib.sha256(f"{text}|{provider}/{model}".encode()).hexdigest()


def load_l2_cache(path: Path) -> dict[str, dict[str, Any]]:
    """Read the JSONL cache; a truncated tail (killed run) is dropped."""
    cache: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return cache
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            key = row.get("key")
            if isinstance(key, str):
                cache[key] = row
    return cache


def append_l2_cache(path: Path, key: str, payload: dict[str, Any]) -> None:
    """Append one answer. JSONL and flushed per line so a crashed run keeps
    everything it already paid for."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"key": key, **payload}, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# The pipeline under test
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Prediction:
    """What the production path returned for one labelled clause."""

    clause: EvalClause
    clause_type: str
    clause_type_confidence: float
    dspy_risk_score: float
    num_risk_factors: int
    risk_level: str
    cached: bool

    @property
    def predicted_high(self) -> bool:
        return self.risk_level == "high"

    @property
    def hybrid_score(self) -> float:
        """The Layer 3 score behind ``risk_level`` — what the sweep re-buckets."""
        return compute_hybrid_score(
            clause_type=self.clause_type,
            clause_type_confidence=self.clause_type_confidence,
            dspy_risk_score=self.dspy_risk_score,
            num_risk_factors=self.num_risk_factors,
        )


def run_pipeline(
    clauses: Sequence[EvalClause],
    *,
    provider: str,
    model: str,
    cache_path: Path,
    log: Callable[[str], None] = print,
) -> list[Prediction]:
    """Push every clause through the real path and collect the verdicts.

    Imports are local: this module must stay importable (for the unit tests)
    without dragging in DSPy or the spaCy classifier. The analyzer is built
    once — ``_build_analyzer`` configures the global DSPy LM, which is
    single-owner per process.
    """
    from analysis_service import _build_analyzer, finalize_clause_result
    from classifier import classify
    from dspy_pipeline import process_clauses
    from schemas import ClauseAnalysisResult, ClauseInput

    cache = load_l2_cache(cache_path)
    analyzer = None
    # Synthetic ids: the harness never touches the database, but ClauseInput
    # and ClauseAnalysisResult are the production schemas and want real UUIDs.
    contract_id = uuid4()
    predictions: list[Prediction] = []

    for index, clause in enumerate(clauses, start=1):
        clause_type, confidence = classify(clause.text)
        key = cache_key(clause.text, provider, model)
        cached_l2 = cache.get(key)

        if cached_l2 is None:
            if analyzer is None:
                analyzer = _build_analyzer()
            results = process_clauses(
                [
                    ClauseInput(
                        parsed_clause_id=uuid4(),
                        contract_id=contract_id,
                        raw_text=clause.text,
                        clause_type=clause_type,
                        clause_type_confidence=confidence,
                    )
                ],
                analyzer=analyzer,
            )
            if not results:
                log(f"  ! [{index}/{len(clauses)}] {clause.source}/{clause.doc}: L2 failed - skipped")
                continue
            raw = results[0]
            cached_l2 = {
                "plain_language_summary": raw.plain_language_summary,
                "risk_factors": list(raw.risk_factors),
                "dspy_risk_score": float(raw.dspy_risk_score),
            }
            append_l2_cache(cache_path, key, cached_l2)
            cache[key] = cached_l2
            was_cached = False
        else:
            was_cached = True

        # Rebuild the L2 result and run the production post-processing (UPL
        # rewrite + Layer 3 blend) so a cache hit is measured exactly like a
        # fresh call: only the LLM round-trip is skipped, never the scoring.
        result = ClauseAnalysisResult(
            parsed_clause_id=uuid4(),
            contract_id=contract_id,
            clause_type=clause_type,
            clause_type_confidence=confidence,
            plain_language_summary=cached_l2["plain_language_summary"],
            risk_factors=list(cached_l2["risk_factors"]),
            dspy_risk_score=float(cached_l2["dspy_risk_score"]),
            risk_level="low",  # overwritten by finalize_clause_result
        )
        result, _rewrites = finalize_clause_result(result)

        predictions.append(
            Prediction(
                clause=clause,
                clause_type=result.clause_type,
                clause_type_confidence=result.clause_type_confidence,
                dspy_risk_score=result.dspy_risk_score,
                num_risk_factors=len(result.risk_factors),
                risk_level=result.risk_level,
                cached=was_cached,
            )
        )
        if index % 10 == 0 or index == len(clauses):
            hits = sum(1 for p in predictions if p.cached)
            log(f"  [{index}/{len(clauses)}] analyzed ({hits} from cache)")

    return predictions


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def binary_metrics(y_true: Sequence[bool], y_pred: Sequence[bool]) -> dict[str, Any]:
    """Precision/recall/F1 of the positive ("high") class, plus the confusion.

    Zero-division follows sklearn's ``zero_division=0``: a run that predicts no
    high-risk clause scores 0.0 precision rather than 1.0. A detector that
    never fires must not look perfect on the dashboard.
    """
    if len(y_true) != len(y_pred):
        raise ValueError("y_true and y_pred must be the same length")

    tp = sum(1 for truth, pred in zip(y_true, y_pred, strict=True) if truth and pred)
    fp = sum(1 for truth, pred in zip(y_true, y_pred, strict=True) if not truth and pred)
    fn = sum(1 for truth, pred in zip(y_true, y_pred, strict=True) if truth and not pred)
    tn = sum(1 for truth, pred in zip(y_true, y_pred, strict=True) if not truth and not pred)

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    return {
        "n": len(y_true),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
    }


def threshold_sweep(
    rows: Sequence[tuple[float, bool]],
    *,
    current: float = THRESHOLD_HIGH,
    thresholds: Sequence[float] = SWEEP_THRESHOLDS,
) -> list[dict[str, Any]]:
    """Re-bucket the same hybrid scores at every candidate THRESHOLD_HIGH.

    ``rows`` are ``(hybrid_score, gold_high_risk)`` pairs. Nothing is re-run:
    the Layer 3 threshold is the one knob that can be retuned from cached
    Layer 2 output, which is exactly why it is worth showing next to the
    targets before anyone changes ``scoring.THRESHOLD_HIGH``.
    """
    truths = [truth for _, truth in rows]
    sweep: list[dict[str, Any]] = []
    for threshold in thresholds:
        metrics = binary_metrics(truths, [score >= threshold for score, _ in rows])
        sweep.append({"threshold": threshold, "current": abs(threshold - current) < 1e-9, **metrics})
    return sweep


def build_payload(
    predictions: Sequence[Prediction],
    *,
    measured: bool,
    provider: str,
    model: str,
    threshold_high: float = THRESHOLD_HIGH,
    caveats: Sequence[str] = (),
) -> dict[str, Any]:
    """Assemble the sidecar. Counts and metrics only — never clause text."""
    truths = [p.clause.gold_high_risk for p in predictions]
    overall = binary_metrics(truths, [p.predicted_high for p in predictions])

    dataset: dict[str, int] = {}
    per_source: dict[str, dict[str, Any]] = {}
    for source in sorted({p.clause.source for p in predictions}):
        subset = [p for p in predictions if p.clause.source == source]
        dataset[source] = len(subset)
        per_source[source] = binary_metrics(
            [p.clause.gold_high_risk for p in subset], [p.predicted_high for p in subset]
        )

    return {
        "measured": measured,
        "provider": provider,
        "model": model,
        "dataset": dataset,
        "n": overall["n"],
        "precision_high": overall["precision"],
        "recall_high": overall["recall"],
        "f1_high": overall["f1"],
        "confusion": overall["confusion"],
        "per_source": per_source,
        "threshold_high": threshold_high,
        "sweep": threshold_sweep(
            [(p.hybrid_score, p.clause.gold_high_risk) for p in predictions],
            current=threshold_high,
        ),
        "targets": dict(TARGETS),
        "meets_targets": (
            overall["precision"] >= TARGETS["precision"]
            and overall["recall"] >= TARGETS["recall"]
        ),
        "caveats": list(caveats),
        "generated_at": datetime.now(UTC).isoformat(),
    }


# ---------------------------------------------------------------------------
# Output gate
# ---------------------------------------------------------------------------

def write_report(
    payload: dict[str, Any],
    *,
    provider: str,
    results_dir: Path = RESULTS_DIR,
    models_dir: Path = MODELS_DIR,
) -> Path:
    """Write the report to the file the provider has earned.

    ``fake`` gets ``eval/results/risk_eval.provisional.json`` and nothing else:
    the demo analyzer derives its score from a hash of the clause text, so its
    precision/recall describe the plumbing. Publishing that as a measured
    result on the dashboard would be a lie about the product, so the committed
    sidecar is refused outright rather than written and flagged.
    """
    if provider == "fake":
        results_dir.mkdir(parents=True, exist_ok=True)
        path = results_dir / PROVISIONAL_NAME
        path.write_text(
            json.dumps({**payload, "measured": False, "provisional": True}, indent=2) + "\n",
            encoding="utf-8",
        )
        return path

    models_dir.mkdir(parents=True, exist_ok=True)
    path = models_dir / SIDECAR_NAME
    path.write_text(
        json.dumps({**payload, "measured": True, "provisional": False}, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="risk_eval.py",
        description="AC-R05: high-risk precision/recall on the production path.",
    )
    parser.add_argument(
        "--provider",
        choices=("fake", "openai"),
        default=None,
        help="LLM provider (default: whatever backend/.env resolves to).",
    )
    parser.add_argument(
        "--cuad",
        type=int,
        default=0,
        metavar="N",
        help="Add up to N CUAD spans per risk class (0 = gold corpus only).",
    )
    parser.add_argument("--corpus", type=Path, default=CORPUS_DIR, help="Gold corpus directory.")
    parser.add_argument("--results", type=Path, default=RESULTS_DIR, help="Provisional output dir.")
    parser.add_argument("--models", type=Path, default=MODELS_DIR, help="Committed sidecar dir.")
    parser.add_argument(
        "--limit", type=int, default=0, metavar="N", help="Analyze at most N clauses (smoke runs)."
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
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
            "[risk_eval] --provider openai needs a real OPENAI_API_KEY in "
            "backend/.env (the placeholder does not count). Run with "
            "--provider fake for a plumbing check.",
            file=sys.stderr,
        )
        return 1
    if provider not in ("fake", "openai"):
        print(
            f"[risk_eval] provider '{provider}' is not wired for AC-R05; "
            "pass --provider fake or --provider openai.",
            file=sys.stderr,
        )
        return 1

    print(f"[risk_eval] provider={provider} model={model}")

    clauses = load_gold_clauses(args.corpus)
    if not clauses:
        print(f"[risk_eval] no gold clauses under {args.corpus} (private, may be absent).")
    if args.cuad > 0:
        try:
            clauses = list(clauses) + load_cuad_clauses(args.cuad)
        except RuntimeError as exc:
            print(f"[risk_eval] {exc}", file=sys.stderr)
            return 1
    if not clauses:
        print(
            "[risk_eval] nothing to evaluate: add gold files to "
            f"{args.corpus} or pass --cuad N.",
            file=sys.stderr,
        )
        return 1
    if args.limit > 0:
        clauses = clauses[: args.limit]

    positives = sum(1 for c in clauses if c.gold_high_risk)
    print(f"[risk_eval] {len(clauses)} labelled clause(s), {positives} high-risk")

    predictions = run_pipeline(
        clauses,
        provider=provider,
        model=model,
        cache_path=args.results / L2_CACHE_NAME,
    )
    if not predictions:
        print("[risk_eval] every clause failed Layer 2 - nothing measured.", file=sys.stderr)
        return 1

    caveats: list[str] = []
    if any(p.clause.source == "cuad" for p in predictions):
        caveats.append(CUAD_CAVEAT)
    if provider == "fake":
        caveats.append(FAKE_CAVEAT)

    payload = build_payload(
        predictions, measured=provider != "fake", provider=provider, model=model, caveats=caveats
    )
    path = write_report(
        payload, provider=provider, results_dir=args.results, models_dir=args.models
    )

    if provider == "fake":
        banner = "!" * 78
        print(f"\n{banner}\n{FAKE_CAVEAT}.\nPROVISIONAL ONLY - the committed sidecar "
              f"({MODELS_DIR.name}/{SIDECAR_NAME}) was NOT written.\n{banner}", file=sys.stderr)

    verdict = "MEETS" if payload["meets_targets"] else "BELOW"
    print(
        f"[risk_eval] n={payload['n']} precision={payload['precision_high']:.3f} "
        f"recall={payload['recall_high']:.3f} f1={payload['f1_high']:.3f} "
        f"({verdict} targets p>={TARGETS['precision']} r>={TARGETS['recall']})"
    )
    print(f"[risk_eval] confusion={payload['confusion']} dataset={payload['dataset']}")
    print(f"[risk_eval] wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""spaCy model-size ablation for the *served* clause classifier.

The trained artifact (backend/models/clause_classifier_v1.joblib) never uses
word vectors — its features are lemmas, NER label counts, POS ratios, modal
verbs and lengths — so a smaller spaCy pipeline may serve it at a fraction of
the memory. This script measures the cost: it evaluates the same artifact
with each pipeline in --models on the official LEDGAR **test** split
(coastalcph/lex_glue, config "ledgar"), which the training pipeline never
touched (03_dedup_minhash.py reads only "train"), and reports macro-F1 both
raw (argmax) and "as served" (classifier.py's low-confidence override to
"general").

Decision rule (--gate, default 0.01): the first model in --models order whose
served macro-F1 is within `gate` of en_core_web_lg's is the recommendation.

    backend/venv/Scripts/python backend/ml_training/scripts/07_spacy_model_ablation.py \
        --models en_core_web_sm en_core_web_md en_core_web_lg --export --sidecar

Runs in the **backend venv** (the production stack) with `datasets`, `psutil`
and the spaCy models installed; do NOT install ml_training/requirements-dev.txt
into that venv (it pins an older numpy/spaCy). Each model is evaluated in a
fresh subprocess so RSS and module state are clean.

Outputs
    ml_training/artifacts/spacy_ablation.json                (full, gitignored)
    backend/models/clause_classifier_v1.spacy_ablation.json  (--export, committed summary)
    backend/models/clause_classifier_v1.eval.json            (--sidecar, confusion matrix +
                                                              per-class P/R/F1 for the chosen model)
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import warnings
from datetime import UTC, datetime
from pathlib import Path

SCRIPT = Path(__file__).resolve()
ML_TRAINING_DIR = SCRIPT.parents[1]
BACKEND_DIR = SCRIPT.parents[2]
INFERENCE_ROOT = BACKEND_DIR / "ml_inference"
MODEL_PATH = BACKEND_DIR / "models" / "clause_classifier_v1.joblib"
META_PATH = BACKEND_DIR / "models" / "clause_classifier_v1.metadata.json"
ARTIFACTS_DIR = ML_TRAINING_DIR / "artifacts"
CACHE_DIR = ML_TRAINING_DIR / "data_cache"
EXPORT_PATH = BACKEND_DIR / "models" / "clause_classifier_v1.spacy_ablation.json"
SIDECAR_PATH = BACKEND_DIR / "models" / "clause_classifier_v1.eval.json"

DATASET = "coastalcph/lex_glue"
DATASET_CONFIG = "ledgar"
SPLIT = "test"
LOW_CONFIDENCE_THRESHOLD = 0.40   # mirrors backend/classifier.py
REFERENCE_MODEL = "en_core_web_lg"
CHUNK = 1000                      # < the inference Doc cache (2048) so both FeatureUnion branches hit it


# ---------------------------------------------------------------------------
# Worker: evaluate ONE model in a clean process
# ---------------------------------------------------------------------------

def _load_split(limit: int | None, seed: int) -> tuple[list[str], list[str]]:
    from datasets import load_dataset  # type: ignore

    ds = load_dataset(DATASET, DATASET_CONFIG, cache_dir=str(CACHE_DIR))[SPLIT]
    if limit is not None and limit < len(ds):
        ds = ds.shuffle(seed=seed).select(range(limit))
    label_names: list[str] = ds.features["label"].names

    # The pickle resolves `src.*` against backend/ml_inference; the same
    # package carries the LEDGAR -> CG8 map, so no second `src` is needed.
    from src.label_map import map_label  # type: ignore

    texts = [str(t) for t in ds["text"]]
    labels = [map_label(label_names[int(i)]) for i in ds["label"]]
    return texts, labels


def run_single(model: str, limit: int | None, seed: int, out: Path) -> int:
    os.environ["SPACY_MODEL"] = model
    if str(INFERENCE_ROOT) not in sys.path:
        sys.path.insert(0, str(INFERENCE_ROOT))

    import numpy  # noqa: F401, I001  isort: skip — numpy must load before spaCy/thinc

    import joblib  # type: ignore
    import src.nlp_singleton as nlp_singleton  # type: ignore
    from sklearn.metrics import (  # type: ignore
        classification_report,
        confusion_matrix,
        f1_score,
    )

    nlp_singleton._MODEL_NAME = model
    nlp_singleton._NLP = None
    nlp_singleton.clear_cache()

    texts, y_true = _load_split(limit, seed)
    labels_sorted = sorted(set(y_true))

    with warnings.catch_warnings():
        # Pickled by sklearn 1.5.2, loaded by a newer one: the same
        # InconsistentVersionWarning classifier.py silences; the predictions
        # below are the real compatibility check.
        warnings.simplefilter("ignore")
        pipeline = joblib.load(MODEL_PATH)
    classes = [str(c) for c in pipeline.classes_]

    # Warm the model (first parse pays the spaCy load) before timing.
    pipeline.predict_proba([texts[0]])
    nlp = nlp_singleton.get_nlp()
    spacy_meta = {
        "name": f"{nlp.meta.get('lang', '')}_{nlp.meta.get('name', '')}".strip("_"),
        "version": str(nlp.meta.get("version", "unknown")),
        "vectors": int(nlp.meta.get("vectors", {}).get("keys", 0) or 0),
    }

    y_raw: list[str] = []
    y_served: list[str] = []
    overridden = 0
    started = time.perf_counter()
    for start in range(0, len(texts), CHUNK):
        chunk = texts[start:start + CHUNK]
        probs = pipeline.predict_proba(chunk)
        nlp_singleton.clear_cache()
        for row in probs:
            idx = int(row.argmax())
            confidence = float(row[idx])
            predicted = classes[idx]
            y_raw.append(predicted)
            if confidence < LOW_CONFIDENCE_THRESHOLD:
                overridden += 1
                y_served.append("general")
            else:
                y_served.append(predicted)
    elapsed = time.perf_counter() - started

    report = classification_report(
        y_true, y_served, labels=labels_sorted, output_dict=True, zero_division=0
    )
    matrix = confusion_matrix(y_true, y_served, labels=labels_sorted).tolist()

    rss_mb: float | None = None
    try:
        import psutil  # type: ignore

        rss_mb = round(psutil.Process().memory_info().rss / (1024 * 1024), 1)
    except Exception:  # noqa: BLE001
        pass

    result = {
        "model": model,
        "spacy": spacy_meta,
        "n": len(texts),
        "raw_macro_f1": float(f1_score(y_true, y_raw, average="macro")),
        "served_macro_f1": float(f1_score(y_true, y_served, average="macro")),
        "low_confidence_rate": overridden / max(len(texts), 1),
        "ms_per_clause": round(1000.0 * elapsed / max(len(texts), 1), 2),
        "rss_mb": rss_mb,
        "labels": labels_sorted,
        "per_class": {
            label: {
                "precision": float(report[label]["precision"]),
                "recall": float(report[label]["recall"]),
                "f1": float(report[label]["f1-score"]),
                "support": int(report[label]["support"]),
            }
            for label in labels_sorted
        },
        "confusion_matrix": matrix,
    }
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(
        f"[07_ablation] {model}: raw macro-F1 {result['raw_macro_f1']:.4f}, "
        f"served {result['served_macro_f1']:.4f}, {result['ms_per_clause']} ms/clause, "
        f"RSS {rss_mb} MB (n={len(texts)})"
    )
    return 0


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def _evaluate_in_subprocess(model: str, limit: int | None, seed: int) -> dict:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    out = ARTIFACTS_DIR / f"spacy_ablation_{model}.json"
    cmd = [sys.executable, str(SCRIPT), "--single", model, "--out", str(out), "--seed", str(seed)]
    if limit is not None:
        cmd += ["--limit", str(limit)]
    completed = subprocess.run(cmd, check=False)
    if completed.returncode != 0 or not out.exists():
        raise RuntimeError(f"evaluation of {model} failed (exit {completed.returncode})")
    return json.loads(out.read_text(encoding="utf-8"))


def _decide(results: dict[str, dict], order: list[str], gate: float) -> dict:
    reference = results.get(REFERENCE_MODEL)
    if reference is None:
        return {"rule": f"served macro-F1 within {gate} of {REFERENCE_MODEL}", "chosen": None,
                "reason": f"{REFERENCE_MODEL} was not evaluated"}
    ref_f1 = reference["served_macro_f1"]
    for model in order:
        delta = ref_f1 - results[model]["served_macro_f1"]
        if delta < gate:
            return {
                "rule": f"first model (in --models order) whose served macro-F1 is within {gate} of {REFERENCE_MODEL}",
                "chosen": model,
                "delta_vs_reference": round(delta, 4),
            }
    return {"rule": f"served macro-F1 within {gate} of {REFERENCE_MODEL}", "chosen": REFERENCE_MODEL,
            "delta_vs_reference": 0.0}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--models", nargs="+",
                        default=["en_core_web_sm", "en_core_web_md", "en_core_web_lg"],
                        help="spaCy pipelines, smallest first")
    parser.add_argument("--limit", type=int, default=None, help="evaluate a random subset of the split")
    parser.add_argument("--seed", type=int, default=13)
    parser.add_argument("--gate", type=float, default=0.01, help="max served macro-F1 drop vs en_core_web_lg")
    parser.add_argument("--export", action="store_true", help=f"write {EXPORT_PATH.name}")
    parser.add_argument("--sidecar", action="store_true", help=f"write {SIDECAR_PATH.name} for the chosen model")
    parser.add_argument("--sidecar-model", default=None, help="override which model's matrix goes in the sidecar")
    # worker mode
    parser.add_argument("--single", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--out", default=None, help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.single:
        return run_single(args.single, args.limit, args.seed, Path(args.out))

    if not MODEL_PATH.exists():
        print(f"[07_ablation] Missing {MODEL_PATH}", file=sys.stderr)
        return 1

    results: dict[str, dict] = {}
    for model in args.models:
        results[model] = _evaluate_in_subprocess(model, args.limit, args.seed)

    decision = _decide(results, args.models, args.gate)
    ref_f1 = results.get(REFERENCE_MODEL, {}).get("served_macro_f1")

    print("\nmodel             raw F1   served F1  delta(lg)  ms/clause  RSS MB   vectors")
    for model in args.models:
        r = results[model]
        delta = (ref_f1 - r["served_macro_f1"]) if ref_f1 is not None else float("nan")
        print(f"{model:<17} {r['raw_macro_f1']:.4f}   {r['served_macro_f1']:.4f}     "
              f"{delta:+.4f}   {r['ms_per_clause']:>7}   {str(r['rss_mb']):>6}   {r['spacy']['vectors']}")
    print(f"\ndecision: {decision}")

    generated_at = datetime.now(UTC).isoformat()
    meta = json.loads(META_PATH.read_text(encoding="utf-8")) if META_PATH.exists() else {}
    common = {
        "artifact": meta.get("artifact_name", "clause_classifier_v1"),
        "trained_with_spacy_model": meta.get("spacy_model"),
        "dataset": f"{DATASET}:{DATASET_CONFIG}",
        "split": SPLIT,
        "n": next(iter(results.values()))["n"],
        "low_confidence_threshold": LOW_CONFIDENCE_THRESHOLD,
        "generated_at": generated_at,
        "note": (
            "Official LEDGAR test split (never used in training); absolute numbers differ "
            "from the training-time holdout (different split, no 'general' cap). Only the "
            "delta between spaCy pipelines matters here."
        ),
    }

    full = {**common, "gate": args.gate, "decision": decision, "results": results}
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS_DIR / "spacy_ablation.json").write_text(json.dumps(full, indent=2), encoding="utf-8")

    if args.export:
        summary = {
            **common,
            "gate": args.gate,
            "decision": decision,
            "models": {
                model: {
                    "spacy_version": r["spacy"]["version"],
                    "word_vectors": r["spacy"]["vectors"],
                    "raw_macro_f1": round(r["raw_macro_f1"], 4),
                    "served_macro_f1": round(r["served_macro_f1"], 4),
                    "delta_vs_lg": round((ref_f1 - r["served_macro_f1"]), 4) if ref_f1 is not None else None,
                    "low_confidence_rate": round(r["low_confidence_rate"], 4),
                    "ms_per_clause": r["ms_per_clause"],
                    "rss_mb": r["rss_mb"],
                }
                for model, r in results.items()
            },
        }
        EXPORT_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"[07_ablation] wrote {EXPORT_PATH}")

    if args.sidecar:
        target = args.sidecar_model or decision.get("chosen") or REFERENCE_MODEL
        r = results[target]
        sidecar = {
            **common,
            "spacy_model": r["spacy"]["name"],
            "spacy_model_version": r["spacy"]["version"],
            "labels": r["labels"],
            "macro_f1": round(r["raw_macro_f1"], 4),
            "served_macro_f1": round(r["served_macro_f1"], 4),
            "per_class": r["per_class"],
            "confusion_matrix": r["confusion_matrix"],
            "confusion_matrix_orientation": "rows = true label, columns = predicted (served), in `labels` order",
        }
        SIDECAR_PATH.write_text(json.dumps(sidecar, indent=2), encoding="utf-8")
        print(f"[07_ablation] wrote {SIDECAR_PATH} ({target})")

    return 0


if __name__ == "__main__":
    sys.exit(main())

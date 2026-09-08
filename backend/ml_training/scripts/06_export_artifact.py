"""Promote artifacts/best_model.joblib to backend/models/clause_classifier_v1.joblib.

Also writes a sidecar metadata JSON. The future production wrapper validates
the sidecar's `labels` matches the 8 CG8 literals at load time.

    python backend/ml_training/scripts/06_export_artifact.py
"""
from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import _path  # noqa: F401
from src.label_map import CG8_TARGETS  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
ML_TRAINING_DIR = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = ML_TRAINING_DIR / "artifacts"
PRODUCTION_DIR = REPO_ROOT / "backend" / "models"
ARTIFACT_NAME = "clause_classifier_v1"
# Pipeline whose meta is recorded in the sidecar (the one this export ran with).
SPACY_MODEL_NAME = os.environ.get("SPACY_MODEL", "en_core_web_lg")


def main() -> int:
    try:
        import joblib  # type: ignore
        import sklearn  # type: ignore
        import spacy  # type: ignore
    except ImportError as exc:
        print(f"[06_export] Missing dependency: {exc}", file=sys.stderr)
        return 1

    src_path = ARTIFACTS_DIR / "best_model.joblib"
    if not src_path.exists():
        print(f"[06_export] Missing {src_path}. Run 04_train.py first.", file=sys.stderr)
        return 1

    pipeline = joblib.load(src_path)

    pipeline_classes = list(map(str, getattr(pipeline, "classes_", [])))
    if not pipeline_classes:
        print("[06_export] Loaded pipeline has no `classes_` attribute.", file=sys.stderr)
        return 1
    extra = set(pipeline_classes) - set(CG8_TARGETS)
    missing = set(CG8_TARGETS) - set(pipeline_classes)
    if extra or missing:
        print(
            f"[06_export] WARNING: pipeline.classes_ != CG8_TARGETS. "
            f"extra={sorted(extra)} missing={sorted(missing)}",
            file=sys.stderr,
        )

    test_metrics_path = ARTIFACTS_DIR / "test_metrics.json"
    test_metrics = json.loads(test_metrics_path.read_text()) if test_metrics_path.exists() else {}

    PRODUCTION_DIR.mkdir(parents=True, exist_ok=True)
    out_model = PRODUCTION_DIR / f"{ARTIFACT_NAME}.joblib"
    out_meta = PRODUCTION_DIR / f"{ARTIFACT_NAME}.metadata.json"

    joblib.dump(pipeline, out_model)

    try:
        spacy_model_meta = spacy.load(SPACY_MODEL_NAME).meta
        spacy_model_version = spacy_model_meta.get("version", "unknown")
    except Exception:  # noqa: BLE001
        spacy_model_version = "unknown"

    metadata = {
        "artifact_name": ARTIFACT_NAME,
        "trained_at_utc": datetime.now(UTC).isoformat(),
        "labels": pipeline_classes,
        "expected_labels": list(CG8_TARGETS),
        "labels_match_expected": not (extra or missing),
        "sklearn_version": sklearn.__version__,
        "spacy_version": spacy.__version__,
        "spacy_model": SPACY_MODEL_NAME,
        "spacy_model_version": spacy_model_version,
        "test_metrics": test_metrics,
    }
    out_meta.write_text(json.dumps(metadata, indent=2))

    print(f"[06_export] Wrote {out_model}")
    print(f"[06_export] Wrote {out_meta}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

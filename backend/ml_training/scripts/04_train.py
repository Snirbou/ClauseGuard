"""Train the Layer 1 classifier via GridSearchCV.

Inputs:
  artifacts/ledgar_train_deduped.parquet  (from 03_dedup_minhash.py)

Steps:
  1. Load deduped LEDGAR with cg8_label.
  2. Cap "general" at 1.5x the second-largest mapped class.
  3. Stratified 80/10/10 split.
  4. GridSearchCV(5-fold) over C in [0.1, 0.5, 1.0, 5.0] x two transformer
     weight choices, scoring=f1_macro.
  5. Refit on train+val with best params, evaluate on test.
  6. Write artifacts/best_model.joblib + artifacts/cv_results.json
     + artifacts/test_metrics.json.

    python backend/ml_training/scripts/04_train.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import _path  # noqa: F401
from src.pipeline import build_pipeline  # noqa: E402

ARTIFACTS_DIR = Path(__file__).resolve().parents[1] / "artifacts"
RANDOM_STATE = 42
GENERAL_CAP_MULTIPLIER = 1.5  # per approved refinement


def downsample_general(df, label_col: str = "cg8_label", random_state: int = RANDOM_STATE):
    """Cap the 'general' bucket at GENERAL_CAP_MULTIPLIER x the second-largest class."""
    counts = df[label_col].value_counts()
    if "general" not in counts.index or len(counts) < 2:
        return df

    non_general = counts.drop("general")
    second_largest = non_general.max()
    cap = int(GENERAL_CAP_MULTIPLIER * second_largest)

    general_count = int(counts["general"])
    if general_count <= cap:
        return df

    print(
        f"[04_train] Downsampling 'general' {general_count} -> {cap} "
        f"(cap = {GENERAL_CAP_MULTIPLIER}x second-largest = {second_largest})"
    )

    general_df = df[df[label_col] == "general"].sample(n=cap, random_state=random_state)
    other_df = df[df[label_col] != "general"]
    out = (
        __import__("pandas")
        .concat([other_df, general_df], ignore_index=True)
        .sample(frac=1.0, random_state=random_state)
        .reset_index(drop=True)
    )
    return out


def main() -> int:
    try:
        import joblib  # type: ignore
        import pandas as pd  # type: ignore
        from sklearn.metrics import classification_report, f1_score
        from sklearn.model_selection import GridSearchCV, StratifiedKFold, train_test_split
    except ImportError as exc:
        print(f"[04_train] Missing dependency: {exc}", file=sys.stderr)
        return 1

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    parquet_path = ARTIFACTS_DIR / "ledgar_train_deduped.parquet"
    if not parquet_path.exists():
        print(f"[04_train] Missing {parquet_path}; run 03_dedup_minhash.py first.", file=sys.stderr)
        return 1

    df = pd.read_parquet(parquet_path)
    print(f"[04_train] Loaded {len(df)} deduped rows.")

    df = downsample_general(df)
    print(f"[04_train] After cap: {len(df)} rows. Distribution:")
    print(df["cg8_label"].value_counts().to_string())

    X = df["text"].tolist()
    y = df["cg8_label"].tolist()

    X_trainval, X_test, y_trainval, y_test = train_test_split(
        X, y, test_size=0.10, stratify=y, random_state=RANDOM_STATE
    )

    pipeline = build_pipeline(C=1.0, inner_cv=3)
    param_grid = {
        "clf__estimator__C": [0.1, 0.5, 1.0, 5.0],
        "features__transformer_weights": [
            {"tfidf": 1.0, "legal": 1.0},
            {"tfidf": 1.0, "legal": 2.0},
        ],
    }
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    search = GridSearchCV(
        pipeline,
        param_grid=param_grid,
        cv=cv,
        scoring="f1_macro",
        n_jobs=1,
        verbose=2,
        refit=True,
    )

    print("[04_train] Starting GridSearchCV (this can take hours)...")
    search.fit(X_trainval, y_trainval)

    print(f"[04_train] Best params: {search.best_params_}")
    print(f"[04_train] Best CV macro-F1: {search.best_score_:.4f}")

    y_pred = search.predict(X_test)
    test_macro_f1 = f1_score(y_test, y_pred, average="macro")
    report = classification_report(y_test, y_pred, output_dict=True)
    per_class_f1 = {label: stats["f1-score"] for label, stats in report.items()
                    if isinstance(stats, dict) and "f1-score" in stats}

    print(f"[04_train] Test macro-F1: {test_macro_f1:.4f}")
    print("[04_train] Per-class F1:")
    for label, f1 in sorted(per_class_f1.items()):
        print(f"  {label:18s} {f1:.4f}")

    joblib.dump(search.best_estimator_, ARTIFACTS_DIR / "best_model.joblib")
    (ARTIFACTS_DIR / "cv_results.json").write_text(json.dumps({
        "best_params": {k: (v if not isinstance(v, dict) else v) for k, v in search.best_params_.items()},
        "best_cv_macro_f1": float(search.best_score_),
        "all_cv_results": {
            "mean_test_score": list(map(float, search.cv_results_["mean_test_score"])),
            "params": [{k: v for k, v in p.items()} for p in search.cv_results_["params"]],
        },
    }, indent=2, default=str))
    (ARTIFACTS_DIR / "test_metrics.json").write_text(json.dumps({
        "test_macro_f1": float(test_macro_f1),
        "per_class_f1": per_class_f1,
        "n_train": len(y_trainval),
        "n_test": len(y_test),
        "general_cap_multiplier": GENERAL_CAP_MULTIPLIER,
    }, indent=2))

    # Acceptance gate
    macro_ok = test_macro_f1 >= 0.85
    per_class_ok = all(f1 >= 0.75 for cls, f1 in per_class_f1.items() if cls in (
        "ip_assignment", "payment_terms", "termination", "liability",
        "confidentiality", "scope_of_work", "governing_law", "general",
    ))
    if not macro_ok:
        print(f"[04_train] WARNING: macro-F1 {test_macro_f1:.4f} < 0.85 acceptance gate.")
    if not per_class_ok:
        print("[04_train] WARNING: at least one per-class F1 < 0.75 acceptance floor.")
    return 0 if (macro_ok and per_class_ok) else 2


if __name__ == "__main__":
    sys.exit(main())

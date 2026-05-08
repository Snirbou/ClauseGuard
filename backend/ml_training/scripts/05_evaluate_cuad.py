"""Out-of-distribution evaluation on CUAD.

CUAD is NEVER used for training or hyperparameter selection. We map a subset
of CUAD's 41 categories to our 8 CG8 labels (best-effort) and report macro-F1
as a distribution-shift sanity check.

    python backend/ml_training/scripts/05_evaluate_cuad.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import _path  # noqa: F401

ARTIFACTS_DIR = Path(__file__).resolve().parents[1] / "artifacts"
CACHE_DIR = Path(__file__).resolve().parents[1] / "data_cache"

# CUAD category -> CG8 (partial; categories not listed are skipped, not "general").
CUAD_TO_CG8 = {
    "Governing Law": "governing_law",
    "Most Favored Nation": "general",
    "Non-Compete": "general",
    "Exclusivity": "general",
    "No-Solicit Of Customers": "general",
    "Competitive Restriction Exception": "general",
    "No-Solicit Of Employees": "general",
    "Non-Disparagement": "confidentiality",
    "Termination For Convenience": "termination",
    "ROFR/ROFO/ROFN": "general",
    "Change Of Control": "termination",
    "Anti-Assignment": "ip_assignment",
    "Revenue/Profit Sharing": "payment_terms",
    "Price Restrictions": "payment_terms",
    "Minimum Commitment": "payment_terms",
    "Volume Restriction": "scope_of_work",
    "IP Ownership Assignment": "ip_assignment",
    "Joint IP Ownership": "ip_assignment",
    "License Grant": "ip_assignment",
    "Non-Transferable License": "ip_assignment",
    "Affiliate License-Licensor": "ip_assignment",
    "Affiliate License-Licensee": "ip_assignment",
    "Unlimited/All-You-Can-Eat-License": "ip_assignment",
    "Irrevocable Or Perpetual License": "ip_assignment",
    "Source Code Escrow": "ip_assignment",
    "Post-Termination Services": "termination",
    "Audit Rights": "scope_of_work",
    "Uncapped Liability": "liability",
    "Cap On Liability": "liability",
    "Liquidated Damages": "liability",
    "Warranty Duration": "liability",
    "Insurance": "liability",
    "Covenant Not To Sue": "liability",
    "Third Party Beneficiary": "general",
}


def main() -> int:
    try:
        import joblib  # type: ignore
        from datasets import load_dataset  # type: ignore
        from sklearn.metrics import classification_report, f1_score
    except ImportError as exc:
        print(f"[05_evaluate_cuad] Missing dependency: {exc}", file=sys.stderr)
        return 1

    model_path = ARTIFACTS_DIR / "best_model.joblib"
    if not model_path.exists():
        print(f"[05_evaluate_cuad] Missing {model_path}; run 04_train.py first.", file=sys.stderr)
        return 1
    pipeline = joblib.load(model_path)

    print("[05_evaluate_cuad] Loading CUAD...")
    try:
        cuad = load_dataset("theatticusproject/cuad-qa", cache_dir=str(CACHE_DIR))
    except Exception as exc:  # noqa: BLE001
        print(f"[05_evaluate_cuad] Could not load CUAD: {exc}", file=sys.stderr)
        return 1

    test_split = cuad.get("test") or cuad.get("validation") or next(iter(cuad.values()))

    # CUAD-QA is SQuAD-flavored: each row has `question` (containing the clause
    # category in quotes) and `answers.text` (positive spans, empty if the
    # clause type is absent). Sort categories longest-first so substrings like
    # "License Grant" don't shadow "Non-Transferable License".
    sorted_categories = sorted(CUAD_TO_CG8.keys(), key=len, reverse=True)

    texts: list[str] = []
    labels: list[str] = []
    for ex in test_split:
        answers = ex.get("answers") or {}
        answer_texts = answers.get("text") or []
        if not answer_texts:
            continue
        question = ex.get("question") or ""
        matched_category = next((c for c in sorted_categories if c in question), None)
        if matched_category is None:
            continue
        cg8 = CUAD_TO_CG8[matched_category]
        for span in answer_texts:
            span = (span or "").strip()
            if not span:
                continue
            texts.append(span)
            labels.append(cg8)

    if not texts:
        print("[05_evaluate_cuad] No mappable CUAD examples found; check field names.", file=sys.stderr)
        return 1

    print(f"[05_evaluate_cuad] Evaluating on {len(texts)} CUAD examples.")
    y_pred = pipeline.predict(texts)
    macro = f1_score(labels, y_pred, average="macro")
    print(f"[05_evaluate_cuad] CUAD OOD macro-F1: {macro:.4f}")

    report = classification_report(labels, y_pred, output_dict=True)
    (ARTIFACTS_DIR / "cuad_eval.json").write_text(json.dumps({
        "ood_macro_f1": float(macro),
        "report": report,
        "n_examples": len(texts),
    }, indent=2, default=str))
    return 0 if macro >= 0.65 else 2


if __name__ == "__main__":
    sys.exit(main())

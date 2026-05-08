# Layer 1 — Classical ML Clause Classifier (Training Sandbox)

Isolated training sandbox for the ClauseGuard Layer 1 clause classifier. The
sandbox produces `backend/models/clause_classifier_v1.joblib`; a future
production wrapper will load it into [backend/classifier.py](../classifier.py).

**Isolation rule:** code in this directory must not be imported by anything in
`backend/` outside `backend/models/`. The only artifact crossing the boundary
is the joblib file under `backend/models/`.

## Layout

```
ml_training/
  src/                  # importable package: pipeline, features, preprocessing, label_map
  scripts/              # numbered, run sequentially
  tests/                # pytest smoke + unit tests
  notebooks/            # EDA, label-mapping audit, error analysis
  data_cache/           # gitignored — HuggingFace dataset cache
  artifacts/            # gitignored — intermediate models, CV results, parquet
```

## One-time setup

```powershell
# From repo root
pip install -r backend/ml_training/requirements-dev.txt
python backend/ml_training/scripts/00_setup.py     # downloads en_core_web_lg
```

## Run the full pipeline

```powershell
python backend/ml_training/scripts/01_download_datasets.py
python backend/ml_training/scripts/02_build_label_map.py
python backend/ml_training/scripts/03_dedup_minhash.py
python backend/ml_training/scripts/04_train.py
python backend/ml_training/scripts/05_evaluate_cuad.py     # OOD sanity check
python backend/ml_training/scripts/06_export_artifact.py   # promotes to backend/models/
```

`04_train.py` performs `GridSearchCV(5-fold)` over `C ∈ [0.1, 0.5, 1.0, 5.0]`
and two `transformer_weights` options, scoring `f1_macro`. Expect 3–6 hours on
an 8-core CPU at full LEDGAR scale.

## Smoke tests

```powershell
cd backend/ml_training
pytest tests/
```

Tests requiring `en_core_web_lg` skip cleanly when the model is missing.

## Acceptance gates (enforced in `04_train.py`)

- Holdout macro-F1 ≥ 0.85
- Every per-class F1 ≥ 0.75 (prevents macro from being inflated by strong classes while one underperforms)
- CUAD OOD macro-F1 ≥ 0.65 (`05_evaluate_cuad.py` exits 2 on miss)

## Design notes

- **No SMOTE.** Imbalance is handled exclusively via `class_weight="balanced"`. Interpolation in 80k-dim sparse TF-IDF space produces invalid synthetic clauses.
- **`general` cap = 1.5×** the second-largest mapped class. Tighter than 3× to prevent the heterogeneous "general" bucket from dragging macro-F1.
- **`StandardScaler(with_mean=False)`** on the dense branch keeps the FeatureUnion combined matrix sparse-compatible. Centering would force densification at 80k features × ~50k rows.
- **Single spaCy pass** via the [src/nlp_singleton.py](src/nlp_singleton.py) LRU cache. Both the dense feature extractor and the TF-IDF lemma tokenizer call `get_doc(text)`.
- **Inner `cv=3`** in `CalibratedClassifierCV` (Platt scaling), outer `cv=5` in `GridSearchCV`. ~40% wall-clock cut at negligible calibration-stability cost on this corpus size.
- **Windows note:** outer `n_jobs=-1`, inner `n_jobs=1`. Nested `loky` parallelism deadlocks on Windows.

## Production handoff

The joblib artifact is the **full fitted Pipeline** (normalize → FeatureUnion → CalibratedClassifierCV). The future wrapper in `backend/classifier.py` will:

```python
proba = pipeline.predict_proba([raw_text])[0]
idx = int(proba.argmax())
clause_type = pipeline.classes_[idx]
confidence = float(proba[idx])
if confidence < 0.4:
    return "general", confidence
return clause_type, confidence
```

The sidecar `clause_classifier_v1.metadata.json` lets the wrapper validate `pipeline.classes_` matches the 8 CG8 literals at load time.

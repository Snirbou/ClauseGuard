"""End-to-end smoke test: build pipeline, fit on synthetic data, predict.

Skipped if spaCy or en_core_web_lg is unavailable. Uses the 8 synthetic clauses
from conftest replicated to give every class enough samples for inner CV.
"""
from __future__ import annotations

import importlib.util

import pytest

spacy_available = importlib.util.find_spec("spacy") is not None
if spacy_available:
    try:
        import spacy
        spacy.load("en_core_web_lg")
        model_available = True
    except Exception:  # noqa: BLE001
        model_available = False
else:
    model_available = False

pytestmark = pytest.mark.skipif(
    not (spacy_available and model_available),
    reason="spaCy or en_core_web_lg not installed",
)


def test_pipeline_fits_and_predicts(synthetic_texts, synthetic_labels):
    from src.label_map import CG8_TARGETS
    from src.pipeline import build_pipeline

    # Replicate to give CalibratedClassifierCV(cv=3) enough samples per class.
    texts = synthetic_texts * 6
    labels = synthetic_labels * 6

    # min_df=1 because corpus is tiny; inner_cv=2 to stay light.
    pipeline = build_pipeline(C=1.0, inner_cv=2, tfidf_max_features=2000, tfidf_min_df=1)
    pipeline.fit(texts, labels)

    preds = pipeline.predict(synthetic_texts)
    assert len(preds) == len(synthetic_texts)
    for p in preds:
        assert p in CG8_TARGETS

    proba = pipeline.predict_proba(synthetic_texts)
    assert proba.shape[0] == len(synthetic_texts)
    assert proba.shape[1] == len(set(labels))
    # Each row sums to ~1.
    import numpy as np
    assert np.allclose(proba.sum(axis=1), 1.0, atol=1e-6)

"""Tests for src/features.py.

Skipped automatically if spaCy or `en_core_web_lg` is not installed.
"""
from __future__ import annotations

import importlib.util

import numpy as np
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


def test_extractor_output_shape(synthetic_texts):
    from src.features import FEATURE_NAMES, LegalFeatureExtractor

    extractor = LegalFeatureExtractor()
    out = extractor.fit_transform(synthetic_texts)
    assert isinstance(out, np.ndarray)
    assert out.shape == (len(synthetic_texts), len(FEATURE_NAMES))
    assert out.dtype == np.float64
    assert not np.isnan(out).any()


def test_extractor_inherits_both_mixins():
    from sklearn.base import BaseEstimator, TransformerMixin
    from src.features import LegalFeatureExtractor

    assert issubclass(LegalFeatureExtractor, BaseEstimator)
    assert issubclass(LegalFeatureExtractor, TransformerMixin)


def test_get_feature_names_out():
    from src.features import FEATURE_NAMES, LegalFeatureExtractor

    names = LegalFeatureExtractor().get_feature_names_out()
    assert tuple(names.tolist()) == FEATURE_NAMES


def test_deontic_modal_counts_distinguish_shall_vs_shall_not():
    from src.features import FEATURE_NAMES, LegalFeatureExtractor

    extractor = LegalFeatureExtractor()
    out = extractor.transform([
        "Contractor shall deliver all reports.",
        "Contractor shall not disclose confidential information.",
    ])
    idx_shall = FEATURE_NAMES.index("count_shall")
    idx_shall_not = FEATURE_NAMES.index("count_shall_not")
    assert out[0, idx_shall] == 1
    assert out[0, idx_shall_not] == 0
    assert out[1, idx_shall] == 0
    assert out[1, idx_shall_not] == 1

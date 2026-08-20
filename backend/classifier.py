"""Production Layer 1 clause classifier.

Loads the trained sklearn Pipeline (TF-IDF + dense legal features ->
CalibratedClassifierCV(LinearSVC)) once at module import. Serves
predict_proba per request and falls back to "general" when max class
probability is below LOW_CONFIDENCE_THRESHOLD.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# sys.path entry must run BEFORE joblib.load so the pickle's references to
# `src.pipeline.TextNormalizer`, `src.features.LegalFeatureExtractor`, and
# `src.nlp_singleton.lemma_tokenize` resolve to backend/ml_inference/src/*.
_INFERENCE_ROOT = Path(__file__).resolve().parent / "ml_inference"
if str(_INFERENCE_ROOT) not in sys.path:
    sys.path.insert(0, str(_INFERENCE_ROOT))

import joblib  # noqa: E402

LOW_CONFIDENCE_THRESHOLD: float = 0.40

_MODEL_PATH = Path(__file__).resolve().parent / "models" / "clause_classifier_v1.joblib"
_META_PATH = _MODEL_PATH.with_suffix(".metadata.json")

_pipeline = joblib.load(_MODEL_PATH)
_meta = json.loads(_META_PATH.read_text(encoding="utf-8"))

_classes = list(map(str, _pipeline.classes_))
if sorted(_classes) != sorted(_meta["expected_labels"]):
    raise RuntimeError(
        f"Classifier label mismatch: pipeline.classes_={_classes} "
        f"vs metadata.expected_labels={_meta['expected_labels']}"
    )

_CLASSES: list[str] = _classes


def classify(raw_text: str) -> tuple[str, float]:
    """Classify a clause segment.

    Returns (clause_type, confidence). clause_type is one of the 8 CG8 labels;
    confidence is the Platt-calibrated max class probability in [0, 1]. When
    confidence < LOW_CONFIDENCE_THRESHOLD, returns ("general", confidence).
    """
    probs = _pipeline.predict_proba([raw_text])[0]
    idx = int(probs.argmax())
    confidence = float(probs[idx])
    if confidence < LOW_CONFIDENCE_THRESHOLD:
        return ("general", confidence)
    return (_CLASSES[idx], confidence)

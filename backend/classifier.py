"""Layer 1 clause classifier.

Primary mode loads the trained sklearn Pipeline (TF-IDF + dense legal
features -> CalibratedClassifierCV(LinearSVC)) from
``models/clause_classifier_v1.joblib`` and serves Platt-calibrated
``predict_proba`` per clause, falling back to ``"general"`` when the max
class probability is below ``LOW_CONFIDENCE_THRESHOLD``.

The artifact was trained under Python 3.11 / scikit-learn 1.5.2; this
process may run a newer stack, so loading is defensive: any failure to
unpickle, validate, or predict flips the module to the rule-based keyword
classifier (the original Step 1 mock) instead of taking the API down.
``classifier_info()`` reports which mode is live — surfaced by
``GET /api/health`` and the evaluation dashboard.

Thread-safety: uploads classify on worker threads. spaCy ``Language``
objects are not safe for concurrent calls, so model predictions are
serialized behind a lock. Predictions are fast (~50ms warm); the lock is
not a throughput concern at this scale.
"""

from __future__ import annotations

# Fully materialize numpy before anything else this module pulls in. When
# dspy/litellm were imported first, a later spaCy/thinc import re-executed
# numpy/__init__ mid-flight and predict_proba crashed with "data type 'bool'
# not understood". Importing numpy at the top of every entry module that can
# reach the classifier pins the safe order regardless of who imports whom.
import numpy  # noqa: F401  isort: skip

import json
import os
import sys
import threading
import warnings
from pathlib import Path
from typing import Any

from config import settings
from logger import get_logger

logger = get_logger(__name__)

LOW_CONFIDENCE_THRESHOLD: float = 0.40

_BACKEND_DIR = Path(__file__).resolve().parent
_MODEL_PATH = _BACKEND_DIR / "models" / "clause_classifier_v1.joblib"
_META_PATH = _MODEL_PATH.with_suffix("").with_suffix(".metadata.json")

# The pickle references `src.pipeline.TextNormalizer`,
# `src.features.LegalFeatureExtractor` and `src.nlp_singleton.lemma_tokenize`;
# this sys.path entry must exist before joblib.load resolves them.
_INFERENCE_ROOT = _BACKEND_DIR / "ml_inference"

_lock = threading.Lock()
_pipeline: Any | None = None
_meta: dict[str, Any] = {}
_mode: str = "unloaded"          # "unloaded" | "model" | "mock"
_load_error: str | None = None
# spaCy pipeline actually serving the model ({"name", "version"}), read from
# nlp.meta after a successful load. May differ from the one used at training
# time (metadata "spacy_model") — see SPACY_MODEL in config.py.
_runtime_spacy: dict[str, str] = {}


# ---------------------------------------------------------------------------
# Rule-based fallback (the original Step 1 mock classifier)
# ---------------------------------------------------------------------------

_MOCK_RULES: list[tuple[list[str], str, float]] = [
    (
        ["intellectual property", "ip ", "ip,", "ownership of work",
         "work product", "inventions", "copyright assignment"],
        "ip_assignment",
        0.92,
    ),
    (
        ["payment", "invoice", "compensation", "fee", "remuneration",
         "net 30", "net 60", "billing"],
        "payment_terms",
        0.85,
    ),
    (
        ["terminat", "cancel", "expir", "end of term",
         "notice period", "wind down"],
        "termination",
        0.88,
    ),
    (
        ["liable", "liability", "indemnif", "damages",
         "limitation of liability", "hold harmless"],
        "liability",
        0.83,
    ),
    (
        ["confidential", "non-disclosure", "nda", "proprietary information",
         "trade secret"],
        "confidentiality",
        0.90,
    ),
    (
        ["scope of work", "deliverables", "services", "obligations",
         "responsibilities", "statement of work"],
        "scope_of_work",
        0.80,
    ),
    (
        ["governing law", "jurisdiction", "dispute resolution",
         "arbitration", "venue", "applicable law"],
        "governing_law",
        0.87,
    ),
]


def mock_classify(raw_text: str) -> tuple[str, float]:
    """Rule-based keyword classifier. Kept as the fallback and for tests."""
    text_lower = raw_text.lower()
    for keywords, clause_type, confidence in _MOCK_RULES:
        if any(kw in text_lower for kw in keywords):
            return clause_type, confidence
    return "general", 0.50


# ---------------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------------

def _load_model() -> None:
    """Attempt to load and validate the trained artifact. Sets module state."""
    global _pipeline, _meta, _mode, _load_error, _runtime_spacy

    try:
        if not _MODEL_PATH.exists():
            raise FileNotFoundError(f"artifact not found: {_MODEL_PATH.name}")

        # ml_inference/src/nlp_singleton.py reads the model name from the
        # process environment when the pickle first imports it; make the
        # backend/.env setting visible there without overriding an explicit
        # environment variable.
        os.environ.setdefault("SPACY_MODEL", settings.SPACY_MODEL)

        if str(_INFERENCE_ROOT) not in sys.path:
            sys.path.insert(0, str(_INFERENCE_ROOT))

        import joblib  # deferred: joblib/sklearn are optional in mock mode

        with warnings.catch_warnings():
            # The artifact was pickled by sklearn 1.5.2; running a newer
            # sklearn emits InconsistentVersionWarning per estimator. The
            # smoke prediction below is the real compatibility check.
            warnings.simplefilter("ignore")
            pipeline = joblib.load(_MODEL_PATH)

        meta: dict[str, Any] = {}
        if _META_PATH.exists():
            meta = json.loads(_META_PATH.read_text(encoding="utf-8"))
            expected = sorted(map(str, meta.get("expected_labels", [])))
            actual = sorted(map(str, pipeline.classes_))
            if expected and expected != actual:
                raise RuntimeError(
                    f"label mismatch: artifact={actual} metadata={expected}"
                )

        # Smoke prediction: proves the unpickled pipeline actually runs on
        # this interpreter/sklearn/spaCy stack (also warms the spaCy model).
        probs = pipeline.predict_proba(
            ["The Client shall pay the Contractor within thirty days."]
        )[0]
        if len(probs) != len(pipeline.classes_):
            raise RuntimeError("predict_proba shape mismatch")

        _pipeline = pipeline
        _meta = meta
        _mode = "model"
        _load_error = None

        # Informational only: which spaCy pipeline the features are computed
        # with in this process. Never fatal.
        try:
            from src.nlp_singleton import get_nlp  # resolved via _INFERENCE_ROOT

            nlp_meta = get_nlp().meta
            _runtime_spacy = {
                "name": f"{nlp_meta.get('lang', '')}_{nlp_meta.get('name', '')}".strip("_"),
                "version": str(nlp_meta.get("version", "unknown")),
            }
        except Exception:  # noqa: BLE001
            _runtime_spacy = {}

        logger.info(
            "Layer 1 classifier loaded: %s (macro-F1 %.3f, trained %s, spaCy %s %s)",
            _MODEL_PATH.name,
            float(meta.get("test_metrics", {}).get("test_macro_f1", 0.0)),
            meta.get("trained_at_utc", "unknown"),
            _runtime_spacy.get("name", "?"),
            _runtime_spacy.get("version", "?"),
        )
    except Exception as exc:
        _pipeline = None
        _runtime_spacy = {}
        _mode = "mock"
        _load_error = f"{type(exc).__name__}: {exc}"
        logger.warning(
            "Layer 1 model unavailable (%s) — using the keyword fallback. "
            "Classification quality is degraded; see backend/ml_training/README.md.",
            _load_error,
        )


def _ensure_loaded() -> None:
    if _mode == "unloaded":
        with _lock:
            if _mode == "unloaded":
                _load_model()


def warm_up() -> str:
    """Force model load (call off the event loop). Returns the live mode."""
    _ensure_loaded()
    return _mode


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify(raw_text: str) -> tuple[str, float]:
    """Classify a clause segment.

    Returns ``(clause_type, confidence)``. In model mode the confidence is
    the Platt-calibrated max class probability; below
    ``LOW_CONFIDENCE_THRESHOLD`` the type is overridden to ``"general"``
    (the probability is preserved). Any runtime failure of the model flips
    the module to mock mode permanently for this process.
    """
    global _mode, _load_error

    _ensure_loaded()

    if _mode == "model" and _pipeline is not None:
        try:
            with _lock:  # spaCy Language objects are not thread-safe
                probs = _pipeline.predict_proba([raw_text])[0]
            idx = int(probs.argmax())
            confidence = float(probs[idx])
            if confidence < LOW_CONFIDENCE_THRESHOLD:
                return "general", confidence
            return str(_pipeline.classes_[idx]), confidence
        except Exception as exc:
            _mode = "mock"
            _load_error = f"runtime: {type(exc).__name__}: {exc}"
            logger.exception(
                "Layer 1 model failed at predict time — switching to the "
                "keyword fallback for the rest of this process."
            )

    return mock_classify(raw_text)


def classifier_info() -> dict[str, Any]:
    """Live classifier status for /api/health and the evaluation dashboard."""
    info: dict[str, Any] = {
        "mode": _mode,
        "low_confidence_threshold": LOW_CONFIDENCE_THRESHOLD,
        "spacy_model_configured": settings.SPACY_MODEL,
    }
    if _load_error:
        info["load_error"] = _load_error
    if _runtime_spacy:
        info["spacy_model_runtime"] = _runtime_spacy["name"]
        info["spacy_model_version_runtime"] = _runtime_spacy["version"]
    if _meta:
        metrics = _meta.get("test_metrics", {})
        info.update(
            {
                "artifact": _meta.get("artifact_name"),
                "trained_at_utc": _meta.get("trained_at_utc"),
                "test_macro_f1": metrics.get("test_macro_f1"),
                "per_class_f1": metrics.get("per_class_f1"),
                "labels": _meta.get("labels"),
                "sklearn_version_trained": _meta.get("sklearn_version"),
                "spacy_model_trained": _meta.get("spacy_model"),
                "spacy_model_version_trained": _meta.get("spacy_model_version"),
            }
        )
    return info

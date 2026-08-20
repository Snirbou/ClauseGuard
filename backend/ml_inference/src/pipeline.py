"""Pipeline factory: preprocessing -> FeatureUnion(TF-IDF | dense) -> calibrated LinearSVC.

The full sklearn Pipeline is what gets pickled into
`backend/models/clause_classifier_v1.joblib`. The future production wrapper
will load it and call `pipeline.predict_proba` + `pipeline.classes_`.
"""

from __future__ import annotations

from collections.abc import Iterable

from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import LinearSVC

from .features import LegalFeatureExtractor
from .nlp_singleton import lemma_tokenize
from .preprocessing import (
    normalize_numbers,
    normalize_pdf_artifacts,
)


class TextNormalizer(BaseEstimator, TransformerMixin):
    """Pre-feature-extraction normalizer: PDF artifacts + number sentinels.

    Order: (a) normalize_pdf_artifacts, then (c) normalize_numbers. Step (b)
    NER extraction happens INSIDE LegalFeatureExtractor on the post-(a) text,
    BEFORE step (c) substitutes numbers — but because we operate per-document
    and reuse the spaCy Doc via the cache, the practical sequence is:

      1. Apply (a) here.
      2. (b) NER counts inside LegalFeatureExtractor — runs spaCy on
         post-(a) text (which still contains $/dates).
      3. (c) Number normalization inside this transformer's transform()
         is currently DISABLED here so it doesn't pre-empt NER. Instead we
         apply (a) only and hand off post-(a) text to BOTH branches; the
         TF-IDF branch's tokenizer handles negation-preserving stop-words and
         lemmas. To preserve number-sentinel features in TF-IDF, set
         `apply_number_norm=True` and ensure NER feature extraction has
         already cached the Doc on the original text.

    For the canonical 04_train.py flow we apply (a) here and (c) AFTER NER
    has cached Docs (see scripts/04_train.py).
    """

    def __init__(self, apply_number_norm: bool = False) -> None:
        self.apply_number_norm = apply_number_norm

    def fit(self, X: Iterable[str], y: object | None = None) -> TextNormalizer:  # noqa: N803
        return self

    def transform(self, X: Iterable[str]) -> list[str]:  # noqa: N803
        out: list[str] = []
        for text in X:
            t = normalize_pdf_artifacts(text)
            if self.apply_number_norm:
                t = normalize_numbers(t)
            out.append(t)
        return out


def build_features(
    tfidf_max_features: int = 80_000,
    tfidf_min_df: int = 2,
    tfidf_ngram_range: tuple[int, int] = (1, 3),
    transformer_weights: dict[str, float] | None = None,
) -> FeatureUnion:
    """Construct the FeatureUnion: TF-IDF (sparse) + LegalFeatureExtractor (dense+scaled)."""
    if transformer_weights is None:
        transformer_weights = {"tfidf": 1.0, "legal": 2.0}

    tfidf = TfidfVectorizer(
        sublinear_tf=True,
        ngram_range=tfidf_ngram_range,
        max_features=tfidf_max_features,
        min_df=tfidf_min_df,
        tokenizer=lemma_tokenize,
        token_pattern=None,         # silence sklearn warning when tokenizer is set
        lowercase=False,            # tokenizer already lowercases
        stop_words=None,            # stop-words handled inside tokenizer
    )

    dense = Pipeline(steps=[
        ("extract", LegalFeatureExtractor()),
        # with_mean=False keeps the dense matrix non-centered; combined hstack
        # in FeatureUnion stays sparse-compatible with the TF-IDF side.
        ("scale", StandardScaler(with_mean=False)),
    ])

    return FeatureUnion(
        transformer_list=[
            ("tfidf", tfidf),
            ("legal", dense),
        ],
        transformer_weights=transformer_weights,
    )


def build_pipeline(
    *,
    C: float = 1.0,
    inner_cv: int = 3,
    tfidf_max_features: int = 80_000,
    tfidf_min_df: int = 2,
    tfidf_ngram_range: tuple[int, int] = (1, 3),
    transformer_weights: dict[str, float] | None = None,
    random_state: int = 42,
) -> Pipeline:
    """Compose the full pipeline. Caller wraps in GridSearchCV for tuning."""
    base = LinearSVC(
        C=C,
        class_weight="balanced",
        dual="auto",
        max_iter=5000,
        random_state=random_state,
    )
    calibrated = CalibratedClassifierCV(
        estimator=base,
        method="sigmoid",
        cv=inner_cv,
        ensemble=True,
        n_jobs=1,  # avoid loky oversubscription on Windows under outer n_jobs=-1
    )

    return Pipeline(steps=[
        ("normalize", TextNormalizer(apply_number_norm=False)),
        ("features", build_features(
            tfidf_max_features=tfidf_max_features,
            tfidf_min_df=tfidf_min_df,
            tfidf_ngram_range=tfidf_ngram_range,
            transformer_weights=transformer_weights,
        )),
        ("clf", calibrated),
    ])

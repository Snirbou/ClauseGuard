"""LegalFeatureExtractor — the dense branch of the FeatureUnion.

Extracts ~12 hand-crafted features per document, intended to complement the
sparse TF-IDF signal:

  * Deontic modal counts: shall, may, must, shall not.
  * spaCy NER counts: MONEY, DATE, ORG, PERSON.
  * Syntactic features: avg sentence length, word count, passive-voice count,
    dependency-tree max depth, noun/verb POS ratio.

Inherits BOTH BaseEstimator and TransformerMixin so it composes inside sklearn
Pipelines / FeatureUnions and inherits a free `fit_transform`.

Output: dense float ndarray of shape (n_documents, N_FEATURES). The downstream
StandardScaler(with_mean=False) re-scales without densifying the FeatureUnion's
combined matrix any further.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin

from .nlp_singleton import get_doc

# ---------------------------------------------------------------------------
# Deontic modal regexes (case-insensitive, word-boundary)
# ---------------------------------------------------------------------------
_SHALL_NOT_RE = re.compile(r"\bshall\s+not\b", re.IGNORECASE)
_SHALL_RE = re.compile(r"\bshall\b", re.IGNORECASE)
_MAY_RE = re.compile(r"\bmay\b", re.IGNORECASE)
_MUST_RE = re.compile(r"\bmust\b", re.IGNORECASE)

# Tracked NER entity labels (en_core_web_lg defaults).
_NER_LABELS: tuple[str, ...] = ("MONEY", "DATE", "ORG", "PERSON")

FEATURE_NAMES: tuple[str, ...] = (
    "count_shall",
    "count_shall_not",
    "count_may",
    "count_must",
    "count_money",
    "count_date",
    "count_org",
    "count_person",
    "avg_sentence_len",
    "word_count",
    "passive_voice_count",
    "dep_tree_max_depth",
    "pos_ratio_noun_verb",
)


def _max_depth(token) -> int:
    """Max depth from `token` to any leaf in its dependency subtree."""
    children = list(token.children)
    if not children:
        return 1
    return 1 + max(_max_depth(c) for c in children)


class LegalFeatureExtractor(BaseEstimator, TransformerMixin):
    """Stateless dense-feature extractor.

    `fit` is a no-op; `transform` produces a (n, len(FEATURE_NAMES)) ndarray.
    Inherits BaseEstimator + TransformerMixin per the design spec — both are
    required (TransformerMixin gives free `fit_transform`; BaseEstimator gives
    `get_params`/`set_params` so GridSearchCV can introspect).
    """

    def __init__(self) -> None:
        # No hyperparameters; kept for sklearn convention.
        pass

    def fit(self, X: Iterable[str], y: object | None = None) -> LegalFeatureExtractor:  # noqa: D401, N803
        return self

    def transform(self, X: Iterable[str]) -> np.ndarray:  # noqa: N803
        texts = list(X)
        n = len(texts)
        out = np.zeros((n, len(FEATURE_NAMES)), dtype=np.float64)

        for i, text in enumerate(texts):
            # --- deontic modals (regex on raw text, cheap) -----------------
            shall_not = len(_SHALL_NOT_RE.findall(text))
            shall_total = len(_SHALL_RE.findall(text))
            shall_only = max(0, shall_total - shall_not)  # don't double-count
            may = len(_MAY_RE.findall(text))
            must = len(_MUST_RE.findall(text))

            # --- spaCy parse (cached) -------------------------------------
            doc = get_doc(text)

            # NER counts
            ner_counts = {label: 0 for label in _NER_LABELS}
            for ent in doc.ents:
                if ent.label_ in ner_counts:
                    ner_counts[ent.label_] += 1

            # Syntactic features
            sentences = list(doc.sents) or [doc[:]]
            non_space_tokens = [t for t in doc if not t.is_space]
            word_count = len(non_space_tokens)
            avg_sent_len = (
                sum(len([t for t in s if not t.is_space]) for s in sentences)
                / max(1, len(sentences))
            )

            passive_voice = sum(
                1 for t in doc if t.dep_ in ("auxpass", "nsubjpass", "csubjpass")
            )

            dep_depth = 0
            for sent in sentences:
                root = sent.root
                d = _max_depth(root)
                if d > dep_depth:
                    dep_depth = d

            n_noun = sum(1 for t in doc if t.pos_ in ("NOUN", "PROPN"))
            n_verb = sum(1 for t in doc if t.pos_ in ("VERB", "AUX"))
            pos_ratio = n_noun / n_verb if n_verb > 0 else float(n_noun)

            out[i, :] = (
                shall_only,
                shall_not,
                may,
                must,
                ner_counts["MONEY"],
                ner_counts["DATE"],
                ner_counts["ORG"],
                ner_counts["PERSON"],
                avg_sent_len,
                word_count,
                passive_voice,
                dep_depth,
                pos_ratio,
            )

        return out

    def get_feature_names_out(self, input_features=None) -> np.ndarray:  # noqa: ARG002
        return np.array(FEATURE_NAMES, dtype=object)

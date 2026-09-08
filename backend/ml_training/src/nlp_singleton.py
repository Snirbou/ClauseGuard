"""Process-wide spaCy singleton + Doc cache.

Both `LegalFeatureExtractor` (custom dense features) and the TF-IDF tokenizer
need spaCy parses of the same documents. A FeatureUnion calls each branch
independently with the same raw text, which would normally produce two spaCy
passes per document. We avoid that with a tiny LRU cache keyed on text.

Pickling note: sklearn pickles the pipeline. `lru_cache` is attached to the
module function, NOT the estimator instance — so unpickling on another machine
re-invokes spaCy fresh; the cache is a runtime-local optimization, not part of
the artifact.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

_NLP: Any | None = None
# Mirrors ml_inference/src/nlp_singleton.py: SPACY_MODEL picks the pipeline.
# Training defaults to the large model; the served model may be smaller (see
# scripts/07_spacy_model_ablation.py for the measured F1 cost).
_MODEL_NAME: str = os.environ.get("SPACY_MODEL", "en_core_web_lg")


def get_nlp() -> Any:
    """Lazy-load and return the singleton spaCy nlp object."""
    global _NLP
    if _NLP is None:
        import spacy
        _NLP = spacy.load(_MODEL_NAME, disable=["textcat"])
    return _NLP


@lru_cache(maxsize=200_000)
def get_doc(text: str) -> Any:
    """Return a cached spaCy Doc for `text`. Reused by both feature branches."""
    return get_nlp()(text)


def clear_cache() -> None:
    get_doc.cache_clear()


def lemma_tokenize(text: str) -> list[str]:
    """Tokenizer callable for sklearn's TfidfVectorizer.

    Uses the cached Doc, drops stop-words and punctuation, returns lemma
    strings. Top-level function so the pipeline pickles cleanly.
    """
    from .preprocessing import EXTENDED_LEGAL_STOPWORDS

    doc = get_doc(text)
    out: list[str] = []
    for token in doc:
        if token.is_punct or token.is_space:
            continue
        lemma = token.lemma_.lower().strip()
        if not lemma:
            continue
        if lemma in EXTENDED_LEGAL_STOPWORDS:
            continue
        out.append(lemma)
    return out

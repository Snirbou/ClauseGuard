"""Document preprocessing for the Layer 1 sandbox.

Order-sensitive pipeline applied per document:
  (a) PDF artifact normalization
  (b) spaCy NER on RAW (post-(a)) text -> entity counts (handled in features.py
      which consumes the cached Doc; we expose normalize_pdf_artifacts here)
  (c) Number normalization (monetary / percentage / time period)
  (d) Extended legal stop-words (with critical negations preserved)
  (e) Lemmatization via spaCy token.lemma_ (handled in features.py)

Steps (b) and (e) reuse the same spaCy Doc to avoid a second pass — see
features.py for the cached-Doc path.
"""

from __future__ import annotations

import re
from typing import Final, Iterable

# ---------------------------------------------------------------------------
# (a) PDF artifact normalization
# ---------------------------------------------------------------------------

_HYPHEN_BREAK_RE = re.compile(r"(\w+)-\s*\n\s*(\w+)")
_PAGE_NUMBER_RE = re.compile(r"\n\s*(?:page\s*)?\d{1,4}\s*(?:of\s*\d{1,4})?\s*\n", re.IGNORECASE)
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")
_TRAILING_WS_RE = re.compile(r"[ \t]+\n")
_RUNNING_HEADER_HINT_RE = re.compile(
    r"^\s*(?:confidential|draft|exhibit\s+[a-z0-9]+|page\s+\d+|\d+\s*/\s*\d+)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def normalize_pdf_artifacts(text: str) -> str:
    """Step (a). De-hyphenate, strip page numbers and obvious running headers."""
    text = _HYPHEN_BREAK_RE.sub(r"\1\2", text)
    text = _PAGE_NUMBER_RE.sub("\n", text)
    text = _RUNNING_HEADER_HINT_RE.sub("", text)
    text = _TRAILING_WS_RE.sub("\n", text)
    text = _MULTI_NEWLINE_RE.sub("\n\n", text)
    return text.strip()


# ---------------------------------------------------------------------------
# (c) Number normalization
# ---------------------------------------------------------------------------

# Order matters: percentage before generic numbers; monetary before time periods
# (so "30 days" doesn't get caught by money first).
_MONETARY_RE = re.compile(
    r"(?:"
    r"(?:US\$|USD|EUR|GBP|\$|£|€)\s?\d[\d,]*(?:\.\d+)?(?:\s?(?:million|billion|thousand|m|bn|k))?"
    r"|"
    r"\d[\d,]*(?:\.\d+)?\s?(?:dollars|euros|pounds|usd|eur|gbp)"
    r")",
    re.IGNORECASE,
)
_PERCENTAGE_RE = re.compile(
    r"\d+(?:\.\d+)?\s*(?:%|(?:percent|per cent|pct)\b)",
    re.IGNORECASE,
)
_TIME_PERIOD_RE = re.compile(
    r"\b\d+\s?[-]?\s?(?:day|days|week|weeks|month|months|year|years|hour|hours|business day|business days|calendar day|calendar days)\b",
    re.IGNORECASE,
)

MONETARY_TOKEN: Final[str] = "__MONETARY_AMOUNT__"
PERCENTAGE_TOKEN: Final[str] = "__PERCENTAGE__"
TIME_PERIOD_TOKEN: Final[str] = "__TIME_PERIOD__"


def normalize_numbers(text: str) -> str:
    """Step (c). Replace monetary, percentage and time-period spans with sentinels.

    Run AFTER spaCy NER has already extracted MONEY/DATE entity counts from the
    raw text. Calling this before NER will destroy the surface forms NER relies
    on.
    """
    text = _MONETARY_RE.sub(MONETARY_TOKEN, text)
    text = _PERCENTAGE_RE.sub(PERCENTAGE_TOKEN, text)
    text = _TIME_PERIOD_RE.sub(TIME_PERIOD_TOKEN, text)
    return text


# ---------------------------------------------------------------------------
# (d) Extended legal stop-words
# ---------------------------------------------------------------------------

# Negations and quantifiers we MUST keep (they flip clause meaning).
PRESERVE_TOKENS: Final[frozenset[str]] = frozenset({
    "not", "no", "only", "nothing", "neither", "nor", "never",
    "without", "except", "unless",
})

# Legal boilerplate terms that add noise to TF-IDF.
LEGAL_BOILERPLATE_STOPWORDS: Final[frozenset[str]] = frozenset({
    "herein", "hereinafter", "hereinabove", "hereinbefore", "hereof", "hereto",
    "heretofore", "hereunder", "hereby", "thereto", "thereof", "therein",
    "thereunder", "therewith", "wherein", "whereof", "whereas", "witnesseth",
    "aforesaid", "aforementioned", "notwithstanding", "pursuant",
    "such", "said", "the", "this", "that", "these", "those",
})


def build_extended_stopwords(base: Iterable[str] | None = None) -> frozenset[str]:
    """Compose the final stop-word set.

    Starts with `base` (typically sklearn's English list), unions in legal
    boilerplate, then removes anything in PRESERVE_TOKENS so legal negations
    survive.
    """
    if base is None:
        try:
            from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
            base_set: set[str] = set(ENGLISH_STOP_WORDS)
        except ImportError:
            base_set = set()
    else:
        base_set = {tok.lower() for tok in base}

    combined = base_set | LEGAL_BOILERPLATE_STOPWORDS
    combined -= PRESERVE_TOKENS
    return frozenset(combined)


EXTENDED_LEGAL_STOPWORDS: Final[frozenset[str]] = build_extended_stopwords()

"""Tests for src/preprocessing.py."""
from __future__ import annotations

from src.preprocessing import (
    EXTENDED_LEGAL_STOPWORDS,
    MONETARY_TOKEN,
    PERCENTAGE_TOKEN,
    PRESERVE_TOKENS,
    TIME_PERIOD_TOKEN,
    normalize_numbers,
    normalize_pdf_artifacts,
)


class TestNormalizePdfArtifacts:
    def test_dehyphenates_line_breaks(self):
        text = "intellec-\ntual property"
        assert normalize_pdf_artifacts(text) == "intellectual property"

    def test_strips_page_numbers(self):
        text = "clause one\n\n12\n\nclause two"
        out = normalize_pdf_artifacts(text)
        assert "12" not in out
        assert "clause one" in out
        assert "clause two" in out

    def test_collapses_excess_newlines(self):
        text = "a\n\n\n\nb"
        assert "\n\n\n" not in normalize_pdf_artifacts(text)


class TestNormalizeNumbers:
    def test_substitutes_dollar_amount(self):
        assert MONETARY_TOKEN in normalize_numbers("Pay $5,000 within 30 days")

    def test_substitutes_percentage(self):
        assert PERCENTAGE_TOKEN in normalize_numbers("a fee of 15% per annum")

    def test_substitutes_time_period(self):
        assert TIME_PERIOD_TOKEN in normalize_numbers("within 30 days of receipt")

    def test_substitutes_word_dollars(self):
        assert MONETARY_TOKEN in normalize_numbers("a payment of 5,000 dollars")


class TestStopwords:
    def test_preserves_negations(self):
        for tok in ("not", "no", "only"):
            assert tok in PRESERVE_TOKENS
            assert tok not in EXTENDED_LEGAL_STOPWORDS

    def test_includes_legal_boilerplate(self):
        for tok in ("herein", "whereas", "hereinafter", "thereto", "witnesseth"):
            assert tok in EXTENDED_LEGAL_STOPWORDS

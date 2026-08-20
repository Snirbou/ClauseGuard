"""Segmentation strategy tests over synthetic PDFs of varying layouts.

Each case builds a real PDF in memory with fitz, extracts it exactly the way
main.py does, and asserts clause boundaries plus AC-S03 text coverage
(≥95% of non-whitespace characters preserved).
"""

from __future__ import annotations

import fitz
import pytest

from segmentation import (
    LineInfo,
    coverage_ratio,
    extract_lines,
    segment_text,
    split_layout_headings,
)

CLAUSE_BODIES = [
    "The Contractor shall provide web development services including design and deployment.",
    "The Client shall pay a fixed fee of USD 12,000 payable net 60 days from invoice.",
    "The Contractor assigns to the Client all right, title and interest in the work product.",
    "Each party shall hold the other's Confidential Information in strict confidence.",
    "The Contractor shall indemnify and hold harmless the Client from all claims.",
]


def _extract(pdf_bytes: bytes) -> tuple[str, list[LineInfo]]:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page_texts = [p.get_text("text") for p in doc if p.get_text("text").strip()]
    lines = extract_lines(doc)
    doc.close()
    return "\n\n".join(page_texts).strip(), lines


def _pdf_from_text(body: str, fontname: str = "helv", fontsize: float = 10.0) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_textbox(
        fitz.Rect(56, 56, 556, 780), body, fontsize=fontsize, fontname=fontname, lineheight=1.3
    )
    data = doc.tobytes()
    doc.close()
    return data


# ---------------------------------------------------------------------------
# Strategy 1 — blank lines
# ---------------------------------------------------------------------------

def test_blank_line_layout() -> None:
    body = "\n\n".join(
        f"{i + 1}. HEADING {i + 1}. {text}" for i, text in enumerate(CLAUSE_BODIES)
    )
    full_text, lines = _extract(_pdf_from_text(body))
    segments = segment_text(full_text, lines)
    assert len(segments) == len(CLAUSE_BODIES)
    assert coverage_ratio(full_text, segments) >= 0.95


# ---------------------------------------------------------------------------
# Strategy 3 — regex headings (no blank lines, numbered headings)
# ---------------------------------------------------------------------------

def test_numbered_headings_without_blank_lines() -> None:
    body = "\n".join(
        f"{i + 1}. SECTION TITLE. {text}" for i, text in enumerate(CLAUSE_BODIES)
    )
    full_text, lines = _extract(_pdf_from_text(body))
    segments = segment_text(full_text, lines)
    assert len(segments) == len(CLAUSE_BODIES)
    assert coverage_ratio(full_text, segments) >= 0.95


# ---------------------------------------------------------------------------
# Strategy 2 — layout headings (bold, unnumbered, no blank lines)
# ---------------------------------------------------------------------------

def test_bold_headings_without_numbers() -> None:
    """Headings carry no numbering — only typography identifies them."""
    doc = fitz.open()
    page = doc.new_page()
    y = 72.0
    titles = ["SCOPE OF WORK", "PAYMENT TERMS", "INTELLECTUAL PROPERTY",
              "CONFIDENTIALITY", "LIABILITY"]
    for title, text in zip(titles, CLAUSE_BODIES, strict=True):
        page.insert_text((56, y), title, fontsize=10, fontname="hebo")  # bold
        y += 14
        for chunk in (text[:70], text[70:]):
            if chunk:
                page.insert_text((56, y), chunk, fontsize=10, fontname="helv")
                y += 13
        y += 4  # small gap, NOT a blank text line
    pdf = doc.tobytes()
    doc.close()

    full_text, lines = _extract(pdf)
    # Precondition for the test to be meaningful: blank-line split must fail.
    from segmentation import split_blank_lines

    if len(split_blank_lines(full_text)) > 1:
        pytest.skip("extractor produced blank lines; layout path not exercised")

    segments = segment_text(full_text, lines)
    assert len(segments) == len(titles)
    for title, segment in zip(titles, segments, strict=True):
        assert segment.startswith(title)
    assert coverage_ratio(full_text, segments) >= 0.95


def test_layout_split_pure() -> None:
    """split_layout_headings in isolation, no PDF round-trip."""
    lines = [
        LineInfo("FIRST HEADING", 10.0, True),
        LineInfo("body line one", 10.0, False),
        LineInfo("body line two", 10.0, False),
        LineInfo("SECOND HEADING", 10.0, True),
        LineInfo("more body text", 10.0, False),
    ]
    segments = split_layout_headings(lines)
    assert len(segments) == 2
    assert segments[0].startswith("FIRST HEADING")
    assert segments[1].startswith("SECOND HEADING")


def test_oversized_heading_detected() -> None:
    lines = [
        LineInfo("Big Title", 16.0, False),
        LineInfo("body body body", 10.0, False),
        LineInfo("Another Big Title", 16.0, False),
        LineInfo("body body body", 10.0, False),
    ]
    assert len(split_layout_headings(lines)) == 2


# ---------------------------------------------------------------------------
# Strategy 4 — unstructured documents stay whole
# ---------------------------------------------------------------------------

def test_single_paragraph_stays_single() -> None:
    body = "This is one flowing paragraph with no headings and no gaps " * 8
    full_text, lines = _extract(_pdf_from_text(body.strip()))
    segments = segment_text(full_text, lines)
    assert len(segments) == 1
    assert coverage_ratio(full_text, segments) >= 0.95


# ---------------------------------------------------------------------------
# Post-processing
# ---------------------------------------------------------------------------

def test_tiny_fragments_merge_forward() -> None:
    text = "IV\n\n1. PAYMENT. The Client shall pay the fee.\n\n2. TERM. One year."
    segments = segment_text(text, None)
    # "IV" (2 chars) merges into the payment clause instead of standing alone.
    assert len(segments) == 2
    assert segments[0].startswith("IV")
    assert "PAYMENT" in segments[0]


def test_empty_text() -> None:
    assert segment_text("", None) == []

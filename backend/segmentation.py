"""Clause segmentation — pure functions over extracted PDF content.

Everything downstream (classification, risk analysis, summaries) inherits
the quality of this split, which makes it the quality ceiling of the whole
product. Strategies are tried in order and the first that finds real
structure wins:

1. **Blank lines** — the original heuristic; correct whenever the PDF's
   text layer preserves paragraph gaps.
2. **Layout headings** — PyMuPDF gives us font sizes and bold flags per
   span. Real contracts are usually extracted with *no* blank lines (one
   line per visual line), but their section headings are visually distinct;
   a line that is bold or set larger than the body text starts a new clause.
3. **Regex headings** — numbered-clause patterns ("1. SCOPE", "ARTICLE 5")
   catch documents whose headings carry no typographic signal.
4. **Whole document** — a genuinely unstructured document stays one clause.

AC-S02/S03 (PRD): clause order follows document order, and no text is lost —
every strategy partitions its source text, so coverage is ≥95% by
construction; tests assert it anyway.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass

_CLAUSE_HEADING_RE = re.compile(
    r"(?=^[ \t]*(?:"
    r"(?:ARTICLE|SECTION|CLAUSE)\s+[0-9IVXL]+"     # "ARTICLE 5", "Section IV"
    r"|\d{1,2}(?:\.\d{1,2})*[.)]\s+[A-Z]"          # "1. SCOPE", "2.1) Payment"
    r"))",
    re.MULTILINE | re.IGNORECASE,
)

_HEADING_LINE_RE = re.compile(
    r"^[ \t]*(?:(?:ARTICLE|SECTION|CLAUSE)\s+[0-9IVXL]+|\d{1,2}(?:\.\d{1,2})*[.)]\s+\S)",
    re.IGNORECASE,
)

# A PyMuPDF span flag: bit 4 marks a bold face.
_BOLD_FLAG = 1 << 4

# Fragments shorter than this merge into the following segment — they are
# almost always page furniture, not clauses.
_MIN_FRAGMENT_CHARS = 15


@dataclass(frozen=True)
class LineInfo:
    """One visual line of the document, with its typographic signal."""

    text: str
    max_size: float
    all_bold: bool


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

def split_blank_lines(full_text: str) -> list[str]:
    return [part.strip() for part in re.split(r"\n\s*\n", full_text) if part.strip()]


def split_regex_headings(full_text: str) -> list[str]:
    return [part.strip() for part in _CLAUSE_HEADING_RE.split(full_text) if part.strip()]


def split_layout_headings(lines: list[LineInfo]) -> list[str]:
    """Split on typographically distinct lines (bold / oversized / numbered).

    ``lines`` come from PyMuPDF's dict extraction (see ``extract_lines``).
    The body size is the document's median span size; a heading is a line
    set noticeably larger, or fully bold and short, or matching the
    numbered-heading pattern.
    """
    sizes = [line.max_size for line in lines if line.text.strip()]
    if not sizes:
        return []
    body_size = statistics.median(sizes)

    def is_heading(line: LineInfo) -> bool:
        text = line.text.strip()
        if not text:
            return False
        if _HEADING_LINE_RE.match(text):
            return True
        if line.max_size > body_size * 1.15:
            return True
        return line.all_bold and len(text) < 80

    segments: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        text = line.text.rstrip()
        if not text.strip():
            continue
        if is_heading(line) and current:
            segments.append(current)
            current = []
        current.append(text)
    if current:
        segments.append(current)

    return ["\n".join(seg).strip() for seg in segments if "\n".join(seg).strip()]


# ---------------------------------------------------------------------------
# Post-processing
# ---------------------------------------------------------------------------

def _merge_tiny_fragments(segments: list[str]) -> list[str]:
    """Fold fragments below the minimum size into the segment that follows."""
    merged: list[str] = []
    pending: str | None = None
    for segment in segments:
        if pending is not None:
            segment = f"{pending}\n{segment}"
            pending = None
        if len(segment.strip()) < _MIN_FRAGMENT_CHARS:
            pending = segment
            continue
        merged.append(segment)
    if pending is not None:
        if merged:
            merged[-1] = f"{merged[-1]}\n{pending}"
        else:
            merged.append(pending)
    return [seg.strip() for seg in merged if seg.strip()]


def coverage_ratio(full_text: str, segments: list[str]) -> float:
    """Fraction of the source's non-whitespace characters kept (AC-S03)."""
    source = len(re.sub(r"\s", "", full_text))
    if source == 0:
        return 1.0
    kept = sum(len(re.sub(r"\s", "", seg)) for seg in segments)
    return kept / source


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

def segment_text(full_text: str, lines: list[LineInfo] | None = None) -> list[str]:
    """Split extracted contract text into clauses. See module docstring."""
    blank = split_blank_lines(full_text)
    if len(blank) > 1:
        return _merge_tiny_fragments(blank)

    if lines:
        layout = split_layout_headings(lines)
        if len(layout) > 1:
            return _merge_tiny_fragments(layout)

    regex = split_regex_headings(full_text)
    if len(regex) > 1:
        return _merge_tiny_fragments(regex)

    return blank  # zero or one segment: the document as a whole


def lines_from_page_dict(data: dict) -> list[LineInfo]:
    """Per-line typography from one PyMuPDF ``get_text("dict")`` payload.

    Split out of ``extract_lines`` so a caller that already holds a TextPage
    — notably the OCR path in ``pdf_extract`` — can produce the same
    ``LineInfo`` shape without re-reading the page.
    """
    lines: list[LineInfo] = []
    for block in data.get("blocks", []):
        for raw_line in block.get("lines", []):
            spans = raw_line.get("spans", [])
            if not spans:
                continue
            text = "".join(span.get("text", "") for span in spans)
            if not text.strip():
                continue
            lines.append(
                LineInfo(
                    text=text,
                    max_size=max(float(span.get("size", 0.0)) for span in spans),
                    all_bold=all(
                        (int(span.get("flags", 0)) & _BOLD_FLAG) != 0 for span in spans
                    ),
                )
            )
    return lines


def extract_lines(doc) -> list[LineInfo]:
    """Pull per-line typography from an open PyMuPDF document."""
    lines: list[LineInfo] = []
    for page in doc:
        lines.extend(lines_from_page_dict(page.get_text("dict")))
    return lines

"""PDF text extraction — the one seam every consumer shares.

The upload endpoint (main.py), the segmentation tests and the evaluation
scripts under eval/ must extract text *identically*: the gold annotations of
the real-contract corpus are anchored to this text, so any drift between the
app and the evaluator would silently invalidate the benchmark. Keep the
normalisation here and nowhere else. This is also where OCR plugs in for
scanned pages (Phase 5).
"""

from __future__ import annotations

from dataclasses import dataclass

import fitz  # PyMuPDF

from segmentation import LineInfo, extract_lines


class PasswordProtectedError(ValueError):
    """The PDF is encrypted and cannot be read without a password."""


@dataclass(frozen=True)
class ExtractedDocument:
    """Text plus the typography the layout segmentation strategy needs."""

    full_text: str
    layout_lines: list[LineInfo]
    page_count: int
    #: Pages that yielded any text. Lower than ``page_count`` for scanned or
    #: mixed documents (the gap is what OCR would have to fill).
    text_pages: int

    @property
    def is_empty(self) -> bool:
        return not self.full_text


def extract_document_text(raw_bytes: bytes) -> ExtractedDocument:
    """Extract the document's text exactly the way the upload endpoint does.

    Pages are joined with a blank line (the first segmentation strategy
    splits on blank lines), empty pages are dropped, and the result is
    stripped. Raises ``PasswordProtectedError`` for encrypted files; any
    other PyMuPDF failure propagates for the caller to map.
    """
    doc = fitz.open(stream=raw_bytes, filetype="pdf")
    try:
        if doc.needs_pass:
            raise PasswordProtectedError("PDF is password protected")

        page_texts: list[str] = []
        for page in doc:
            page_text = page.get_text("text") or ""
            if page_text.strip():
                page_texts.append(page_text)

        # Typography (font sizes, bold flags) feeds the layout-based
        # segmentation strategy; it must be read while the doc is open.
        layout_lines = extract_lines(doc)
        page_count = doc.page_count
    finally:
        # fitz documents hold an open handle on the stream buffer.
        doc.close()

    return ExtractedDocument(
        full_text="\n\n".join(page_texts).strip(),
        layout_lines=layout_lines,
        page_count=page_count,
        text_pages=len(page_texts),
    )

"""PDF text extraction — the one seam every consumer shares.

The upload endpoint (main.py), the segmentation tests and the evaluation
scripts under eval/ must extract text *identically*: the gold annotations of
the real-contract corpus are anchored to this text, so any drift between the
app and the evaluator would silently invalidate the benchmark. Keep the
normalisation here and nowhere else.

**OCR.** A scanned contract is an image: PyMuPDF returns nothing for it, and
before this the upload was simply refused. Pages that yield no digital text
are now rendered and passed to Tesseract (through PyMuPDF's own
``get_textpage_ocr``), so a photographed or scanned agreement is analyzed
like any other. Three properties matter:

- **Digital text is never re-OCRed.** A page that already has a text layer
  is read exactly as before, byte for byte, so nothing about the existing
  corpus or its anchors moves. OCR only fills pages that were empty.
- **It is bounded.** ``OCR_MAX_PAGES`` caps the work, because OCR runs
  inside the upload request (roughly a second per page) and AC-API01 gives
  that request a 5s p95 budget. A scan past the cap is refused with a clear
  message rather than silently truncated.
- **It degrades to the old behaviour.** With ``OCR_ENABLED=false`` or no
  Tesseract binary on the host, the extraction returns empty text and the
  caller raises the same "needs OCR" error it always did.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field

import fitz  # PyMuPDF

from config import settings
from logger import get_logger
from segmentation import LineInfo, lines_from_page_dict

logger = get_logger(__name__)


class PasswordProtectedError(ValueError):
    """The PDF is encrypted and cannot be read without a password."""


def ocr_available() -> bool:
    """Whether a Tesseract binary is on PATH for PyMuPDF to drive.

    Not cached: the answer is a filesystem lookup, and caching it would make
    /api/health lie for the lifetime of the process after an operator fixes
    a broken image.
    """
    return shutil.which("tesseract") is not None


@dataclass(frozen=True)
class ExtractedDocument:
    """Text plus the typography the layout segmentation strategy needs."""

    full_text: str
    layout_lines: list[LineInfo]
    page_count: int
    #: Pages that yielded any text, digital or OCR'd.
    text_pages: int
    #: Pages whose text came from OCR. Zero for an ordinary digital PDF.
    ocr_pages: int = 0
    #: Pages with no digital text that OCR did not cover — because it is
    #: disabled, unavailable, over the page cap, or it failed on the page.
    #: A non-empty list with ``ocr_pages == 0`` is the "needs OCR" case.
    unreadable_pages: list[int] = field(default_factory=list)
    #: Set when OCR was wanted but could not run at all; surfaced to the user.
    ocr_error: str | None = None

    @property
    def is_empty(self) -> bool:
        return not self.full_text

    @property
    def used_ocr(self) -> bool:
        return self.ocr_pages > 0


def _ocr_page_text(page, dpi: int) -> tuple[str, list[LineInfo]]:
    """OCR one page and return its text plus its (approximate) typography.

    ``full=True`` because we only reach here for pages with no digital text
    at all — the cheaper whole-page path, and it avoids PyMuPDF's redaction
    dance for mixed pages. OCR spans carry synthetic font sizes, so the
    layout segmentation strategy is weak on scans; ``segment_text`` falls
    through to the regex strategy, which is the intended behaviour.
    """
    textpage = page.get_textpage_ocr(full=True, dpi=dpi, language="eng")
    text = page.get_text("text", textpage=textpage) or ""
    lines = lines_from_page_dict(page.get_text("dict", textpage=textpage))
    return text, lines


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

        # Per-page slots rather than a flat list: OCR fills gaps in the
        # middle of a mixed document, and a clause's position in the contract
        # is part of the output (AC-S02), so recovered pages must land in
        # document order, not at the end.
        page_count = doc.page_count
        page_slots: list[str | None] = [None] * page_count
        line_slots: list[list[LineInfo]] = [[] for _ in range(page_count)]
        empty_pages: list[int] = []

        for page in doc:
            page_text = page.get_text("text") or ""
            if page_text.strip():
                page_slots[page.number] = page_text
                # Typography (font sizes, bold flags) feeds the layout-based
                # segmentation strategy; it must be read while the doc is open.
                line_slots[page.number] = lines_from_page_dict(page.get_text("dict"))
            else:
                empty_pages.append(page.number)
        ocr_pages = 0
        ocr_error: str | None = None
        unreadable = list(empty_pages)

        # Only scanned pages reach OCR; a fully digital document never does,
        # so its extraction is unchanged.
        if empty_pages and settings.OCR_ENABLED:
            if not ocr_available():
                ocr_error = "tesseract is not installed on the server"
            elif len(empty_pages) > settings.OCR_MAX_PAGES:
                ocr_error = (
                    f"{len(empty_pages)} scanned pages exceed the "
                    f"{settings.OCR_MAX_PAGES}-page OCR limit"
                )
            else:
                recovered: list[int] = []
                for number in empty_pages:
                    try:
                        text, lines = _ocr_page_text(doc.load_page(number), settings.OCR_DPI)
                    except Exception as exc:  # noqa: BLE001 — never fail the upload here
                        logger.warning("OCR failed on page %d: %s", number + 1, exc)
                        ocr_error = ocr_error or f"OCR failed: {exc}"
                        continue
                    if text.strip():
                        page_slots[number] = text
                        line_slots[number] = lines
                        recovered.append(number)
                ocr_pages = len(recovered)
                unreadable = [n for n in empty_pages if n not in set(recovered)]
                if ocr_pages:
                    logger.info(
                        "OCR recovered %d of %d image-only page(s).",
                        ocr_pages,
                        len(empty_pages),
                    )
        elif empty_pages and not settings.OCR_ENABLED:
            ocr_error = "OCR is disabled on the server"
    finally:
        # fitz documents hold an open handle on the stream buffer.
        doc.close()

    page_texts = [text for text in page_slots if text is not None]
    layout_lines = [line for slot in line_slots for line in slot]

    return ExtractedDocument(
        full_text="\n\n".join(page_texts).strip(),
        layout_lines=layout_lines,
        page_count=page_count,
        text_pages=len(page_texts),
        ocr_pages=ocr_pages,
        unreadable_pages=unreadable,
        ocr_error=ocr_error,
    )

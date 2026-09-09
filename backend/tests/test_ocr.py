"""OCR for scanned PDFs.

A "scanned" page here is a real rendered image of text with no text layer —
built by drawing text, rasterising it, and inserting the raster into a fresh
page — which is exactly what a phone photo or a flatbed scan produces.

Tesseract is a system package, so the tests that actually read a scan skip
where it is missing (Windows dev boxes) and run in the Docker image and CI,
which install it. The tests that matter most need no Tesseract at all: they
pin the behaviour when OCR *cannot* run, which is the path a misconfigured
deployment takes.
"""

from __future__ import annotations

import fitz
import pytest

import pdf_extract
from config import settings
from pdf_extract import extract_document_text, ocr_available

REQUIRES_TESSERACT = pytest.mark.skipif(
    not ocr_available(), reason="tesseract is not installed on this host"
)

SCAN_TEXT = "PAYMENT. The Client shall pay the Contractor within thirty days."


def _scanned_pdf(text: str = SCAN_TEXT, pages: int = 1) -> bytes:
    """A PDF whose pages are images of text — no digital text layer."""
    source = fitz.open()
    for _ in range(pages):
        page = source.new_page()
        page.insert_textbox(
            fitz.Rect(40, 40, 560, 300), text, fontsize=18, fontname="helv"
        )
    scanned = fitz.open()
    for page in source:
        pixmap = page.get_pixmap(dpi=200)
        image_page = scanned.new_page(width=page.rect.width, height=page.rect.height)
        image_page.insert_image(image_page.rect, pixmap=pixmap)
    data = scanned.tobytes()
    source.close()
    scanned.close()
    return data


def _digital_pdf(text: str) -> bytes:
    doc = fitz.open()
    doc.new_page().insert_textbox(
        fitz.Rect(56, 56, 556, 780), text, fontsize=11, fontname="helv"
    )
    data = doc.tobytes()
    doc.close()
    return data


def _mixed_pdf() -> bytes:
    """Page 1 digital, page 2 a scan — the case that breaks page ordering."""
    digital = fitz.open(stream=_digital_pdf("1. FIRST PAGE. Digital text here."), filetype="pdf")
    scan = fitz.open(stream=_scanned_pdf("2. SECOND PAGE. Scanned text here."), filetype="pdf")
    digital.insert_pdf(scan)
    data = digital.tobytes()
    digital.close()
    scan.close()
    return data


def test_a_scanned_page_really_has_no_text_layer() -> None:
    """Guards the fixture itself: if this fails the other tests prove nothing."""
    doc = fitz.open(stream=_scanned_pdf(), filetype="pdf")
    try:
        assert doc[0].get_text("text").strip() == ""
    finally:
        doc.close()


def test_digital_pdfs_never_touch_ocr(monkeypatch: pytest.MonkeyPatch) -> None:
    """A page with a text layer must be read as before — no OCR, no cost."""
    def _boom(*_args, **_kwargs):
        raise AssertionError("OCR ran on a page that already had text")

    monkeypatch.setattr(pdf_extract, "_ocr_page_text", _boom)
    extracted = extract_document_text(_digital_pdf("The Contractor shall deliver."))
    assert "Contractor" in extracted.full_text
    assert extracted.ocr_pages == 0
    assert extracted.used_ocr is False
    assert extracted.unreadable_pages == []
    assert extracted.ocr_error is None


def test_scan_is_refused_when_ocr_is_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "OCR_ENABLED", False)
    extracted = extract_document_text(_scanned_pdf())
    assert extracted.is_empty
    assert extracted.ocr_pages == 0
    assert extracted.unreadable_pages == [0]
    assert extracted.ocr_error == "OCR is disabled on the server"


def test_scan_is_refused_when_tesseract_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "OCR_ENABLED", True)
    monkeypatch.setattr(pdf_extract, "ocr_available", lambda: False)
    extracted = extract_document_text(_scanned_pdf())
    assert extracted.is_empty
    assert "tesseract is not installed" in extracted.ocr_error


def test_scan_over_the_page_cap_is_refused_without_running_ocr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The cap exists because OCR runs inside the upload request (AC-API01)."""
    monkeypatch.setattr(settings, "OCR_ENABLED", True)
    monkeypatch.setattr(settings, "OCR_MAX_PAGES", 1)
    monkeypatch.setattr(pdf_extract, "ocr_available", lambda: True)
    monkeypatch.setattr(
        pdf_extract,
        "_ocr_page_text",
        lambda *_a, **_k: pytest.fail("OCR ran despite the page cap"),
    )
    extracted = extract_document_text(_scanned_pdf(pages=3))
    assert extracted.is_empty
    assert extracted.ocr_pages == 0
    assert "exceed the 1-page OCR limit" in extracted.ocr_error


def test_a_failing_page_is_reported_not_raised(monkeypatch: pytest.MonkeyPatch) -> None:
    """A Tesseract crash must never take the upload down with it."""
    monkeypatch.setattr(settings, "OCR_ENABLED", True)
    monkeypatch.setattr(pdf_extract, "ocr_available", lambda: True)

    def _fail(*_args, **_kwargs):
        raise RuntimeError("tesseract exploded")

    monkeypatch.setattr(pdf_extract, "_ocr_page_text", _fail)
    extracted = extract_document_text(_scanned_pdf())
    assert extracted.is_empty
    assert extracted.ocr_pages == 0
    assert extracted.unreadable_pages == [0]
    assert "tesseract exploded" in extracted.ocr_error


def test_ocr_fills_pages_in_document_order(monkeypatch: pytest.MonkeyPatch) -> None:
    """A recovered page belongs where it sits in the contract (AC-S02).

    Stubbed rather than real OCR so the ordering invariant is checked on
    every machine, including those without Tesseract.
    """
    monkeypatch.setattr(settings, "OCR_ENABLED", True)
    monkeypatch.setattr(pdf_extract, "ocr_available", lambda: True)
    monkeypatch.setattr(
        pdf_extract, "_ocr_page_text", lambda page, dpi: ("2. SECOND PAGE (ocr)", [])
    )

    extracted = extract_document_text(_mixed_pdf())
    assert extracted.ocr_pages == 1
    assert extracted.page_count == 2
    first = extracted.full_text.index("FIRST PAGE")
    second = extracted.full_text.index("SECOND PAGE (ocr)")
    assert first < second, "the OCR'd page was appended instead of slotted in"


@REQUIRES_TESSERACT
def test_real_ocr_reads_a_scanned_contract() -> None:
    extracted = extract_document_text(_scanned_pdf())
    assert extracted.used_ocr is True
    assert extracted.ocr_pages == 1
    assert extracted.unreadable_pages == []
    assert extracted.ocr_error is None
    lowered = extracted.full_text.lower()
    # OCR is not character-perfect; assert on the words that carry meaning.
    assert "payment" in lowered
    assert "contractor" in lowered
    assert "thirty days" in lowered


@REQUIRES_TESSERACT
def test_real_ocr_keeps_mixed_documents_in_order() -> None:
    extracted = extract_document_text(_mixed_pdf())
    assert extracted.ocr_pages == 1
    assert extracted.text_pages == 2
    lowered = extracted.full_text.lower()
    assert lowered.index("first page") < lowered.index("second page")

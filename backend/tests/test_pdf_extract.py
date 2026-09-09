"""pdf_extract is the shared extraction seam (upload, tests, eval scripts)."""

from __future__ import annotations

import fitz
import pytest

from pdf_extract import PasswordProtectedError, extract_document_text


def _pdf(body: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_textbox(fitz.Rect(56, 56, 556, 780), body, fontsize=10.0, fontname="helv")
    data = doc.tobytes()
    doc.close()
    return data


def test_extracts_text_and_layout_lines() -> None:
    body = "1. PAYMENT. The Client shall pay the Contractor within thirty days.\n\n2. TERM. Two years."
    extracted = extract_document_text(_pdf(body))
    assert "pay the Contractor" in extracted.full_text
    assert extracted.full_text == extracted.full_text.strip()
    assert extracted.page_count == 1
    assert extracted.text_pages == 1
    assert extracted.layout_lines and any("PAYMENT" in line.text for line in extracted.layout_lines)
    assert extracted.is_empty is False


def test_blank_document_is_empty_not_an_error() -> None:
    doc = fitz.open()
    doc.new_page()
    data = doc.tobytes()
    doc.close()
    extracted = extract_document_text(data)
    assert extracted.is_empty is True
    assert extracted.page_count == 1
    assert extracted.text_pages == 0


def test_password_protected_pdf_raises() -> None:
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "secret")
    data = doc.tobytes(encryption=fitz.PDF_ENCRYPT_AES_256, user_pw="hunter2", owner_pw="owner")
    doc.close()
    with pytest.raises(PasswordProtectedError):
        extract_document_text(data)


def test_garbage_bytes_propagate_as_a_parse_error() -> None:
    # PyMuPDF raises its own error types; main.py maps anything that is not
    # PasswordProtectedError to the "Failed to parse PDF" envelope.
    with pytest.raises((RuntimeError, ValueError, fitz.FileDataError)):
        extract_document_text(b"not a pdf at all")

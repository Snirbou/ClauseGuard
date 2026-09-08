"""Stable, machine-readable codes for user-facing API errors.

The frontend renders errors in the visitor's language (Hebrew UI) by
looking the ``code`` up in its dictionary; ``detail`` keeps carrying the
English human-readable text, so older clients and the smoke test are
unaffected. The field is additive: envelopes without a code look exactly as
they did before.

Adding a code is fine. Renaming or removing one silently breaks the
frontend mapping, which is why tests/test_error_codes.py freezes the list.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException


class CodedHTTPException(HTTPException):
    """HTTPException carrying a stable code alongside the human ``detail``."""

    def __init__(
        self,
        status_code: int,
        detail: Any,
        *,
        code: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=detail, headers=headers)
        self.code = code


# --- auth -----------------------------------------------------------------
AUTH_SIGN_IN_REQUIRED = "auth.sign_in_required"
AUTH_SESSION_EXPIRED = "auth.session_expired"
AUTH_INVALID_CREDENTIALS = "auth.invalid_credentials"
AUTH_EMAIL_TAKEN = "auth.email_taken"
AUTH_INVALID_EMAIL = "auth.invalid_email"
AUTH_PASSWORD_TOO_SHORT = "auth.password_too_short"
RATE_LIMITED = "rate_limited"

# --- contracts / runs -------------------------------------------------------
CONTRACT_NOT_FOUND = "contract.not_found"
CONTRACT_DELETE_FAILED = "contract.delete_failed"
RUN_NOT_FOUND = "run.not_found"

# --- analysis ---------------------------------------------------------------
ANALYSIS_FAILED = "analysis.failed"
ANALYSIS_LLM_NOT_CONFIGURED = "analysis.llm_not_configured"
ANALYSIS_IN_PROGRESS = "analysis.in_progress"
ANALYSIS_NO_CLAUSES = "analysis.no_clauses"

# --- upload -----------------------------------------------------------------
UPLOAD_INVALID_TYPE = "upload.invalid_type"
UPLOAD_EMPTY = "upload.empty"
UPLOAD_TOO_LARGE = "upload.too_large"
UPLOAD_READ_FAILED = "upload.read_failed"
UPLOAD_PASSWORD_PROTECTED = "upload.password_protected"
UPLOAD_PARSE_FAILED = "upload.parse_failed"
UPLOAD_NEEDS_OCR = "upload.needs_ocr"
UPLOAD_NO_CLAUSES = "upload.no_clauses"
UPLOAD_PERSIST_FAILED = "upload.persist_failed"

# --- generic ----------------------------------------------------------------
VALIDATION_ERROR = "validation_error"
INTERNAL_ERROR = "internal_error"

ALL_CODES: frozenset[str] = frozenset(
    value
    for name, value in globals().items()
    if name.isupper() and isinstance(value, str) and name != "ALL_CODES"
)

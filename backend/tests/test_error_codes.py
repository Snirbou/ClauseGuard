"""Error codes are a frontend contract: the Hebrew UI maps them to
localized messages. The list is frozen here so a rename shows up as a test
failure instead of as an English message leaking into the Hebrew UI."""

from __future__ import annotations

import asyncio
import json

from fastapi import HTTPException
from starlette.requests import Request

import auth
import error_codes
import main
from analysis_service import (
    AnalysisError,
    AnalysisInProgressError,
    LLMNotConfiguredError,
)

FROZEN_CODES = {
    "auth.sign_in_required",
    "auth.session_expired",
    "auth.invalid_credentials",
    "auth.email_taken",
    "auth.invalid_email",
    "auth.password_too_short",
    "rate_limited",
    "contract.not_found",
    "contract.delete_failed",
    "run.not_found",
    "analysis.failed",
    "analysis.llm_not_configured",
    "analysis.in_progress",
    "analysis.no_clauses",
    "upload.invalid_type",
    "upload.empty",
    "upload.too_large",
    "upload.read_failed",
    "upload.password_protected",
    "upload.parse_failed",
    "upload.needs_ocr",
    "upload.no_clauses",
    "upload.persist_failed",
    "validation_error",
    "internal_error",
}


def _request() -> Request:
    return Request({"type": "http", "method": "GET", "path": "/", "headers": []})


def _body(response) -> dict:
    return json.loads(response.body)


def test_code_list_is_frozen() -> None:
    assert set(error_codes.ALL_CODES) == FROZEN_CODES


def test_coded_exception_renders_code_in_envelope() -> None:
    exc = error_codes.CodedHTTPException(
        status_code=404, detail="Contract not found.", code=error_codes.CONTRACT_NOT_FOUND
    )
    response = asyncio.run(main.http_exception_handler(_request(), exc))
    assert response.status_code == 404
    assert _body(response) == {
        "status": "error",
        "detail": "Contract not found.",
        "code": "contract.not_found",
    }


def test_plain_http_exception_keeps_the_legacy_shape() -> None:
    response = asyncio.run(
        main.http_exception_handler(_request(), HTTPException(status_code=418, detail="teapot"))
    )
    assert _body(response) == {"status": "error", "detail": "teapot"}


def test_upload_envelope_carries_the_code() -> None:
    exc = main._upload_http_error(
        "x.pdf", "Empty file.", code=error_codes.UPLOAD_EMPTY
    )
    body = _body(asyncio.run(main.http_exception_handler(_request(), exc)))
    assert body["status"] == "error"
    assert body["filename"] == "x.pdf"
    assert body["parsed_clauses"] == []
    assert body["detail"] == "Empty file."
    assert body["code"] == "upload.empty"


def test_upload_envelope_without_code_is_unchanged() -> None:
    exc = main._upload_http_error("x.pdf", "Boom.")
    body = _body(asyncio.run(main.http_exception_handler(_request(), exc)))
    assert "code" not in body


def test_credential_problems_carry_codes() -> None:
    assert auth.validate_credentials_format("nope", "longenough") == (
        "Enter a valid email address.",
        error_codes.AUTH_INVALID_EMAIL,
    )
    problem = auth.validate_credentials_format("a@b.co", "short")
    assert problem is not None and problem[1] == error_codes.AUTH_PASSWORD_TOO_SHORT
    assert auth.validate_credentials_format("a@b.co", "longenough") is None


def test_analysis_errors_carry_codes() -> None:
    assert LLMNotConfiguredError().code == error_codes.ANALYSIS_LLM_NOT_CONFIGURED
    assert AnalysisInProgressError().code == error_codes.ANALYSIS_IN_PROGRESS
    assert AnalysisError("x").code == error_codes.ANALYSIS_FAILED
    assert AnalysisError("x").status_code == 502

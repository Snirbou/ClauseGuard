from __future__ import annotations

import re
from typing import Any, List

import fitz  # PyMuPDF
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse


app = FastAPI()


def _is_pdf_upload(upload: UploadFile) -> bool:
    content_type = (upload.content_type or "").lower()
    filename = (upload.filename or "").lower()
    return content_type == "application/pdf" or filename.endswith(".pdf")


def _error_envelope(
    *,
    filename: str,
    detail: str,
    status_code: int = 400,
) -> dict[str, Any]:
    # Exact error envelope required by the Step 0 API contract.
    return {
        "status": "error",
        "filename": filename,
        "parsed_clauses": [],
        "detail": detail,
    }


@app.exception_handler(HTTPException)
async def http_exception_handler(
    request: Request,
    exc: HTTPException,
) -> JSONResponse:
    filename = "uploaded.pdf"

    # We encode both filename and message in HTTPException.detail to keep the
    # error envelope consistent with the agreed contract.
    if isinstance(exc.detail, dict):
        filename = str(exc.detail.get("filename", filename))
        message = exc.detail.get("message") or exc.detail.get("detail")
        detail = str(message) if message is not None else str(exc.detail)
    else:
        detail = str(exc.detail)

    return JSONResponse(
        status_code=exc.status_code,
        content=_error_envelope(filename=filename, detail=detail),
    )


# Allow the Next.js dev server to talk to FastAPI locally.
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/contracts/upload")
async def upload_contract(file: UploadFile = File(...)) -> dict[str, Any]:
    filename = file.filename or "uploaded.pdf"

    if not _is_pdf_upload(file):
        raise HTTPException(
            status_code=400,
            detail={"filename": filename, "message": "Invalid file type. PDF required."},
        )

    try:
        raw_bytes = await file.read()
    except Exception:
        raise HTTPException(
            status_code=400,
            detail={"filename": filename, "message": "Failed to read uploaded file."},
        )

    if not raw_bytes:
        raise HTTPException(
            status_code=400,
            detail={"filename": filename, "message": "Empty file."},
        )

    try:
        doc = fitz.open(stream=raw_bytes, filetype="pdf")
        page_texts: List[str] = []
        for page in doc:
            text = page.get_text("text") or ""
            if text.strip():
                page_texts.append(text)

        full_text = "\n\n".join(page_texts).strip()
        if not full_text:
            raise HTTPException(
                status_code=400,
                detail={
                    "filename": filename,
                    "message": "Could not extract text from PDF.",
                },
            )

        # Naive segmentation: split on blank lines.
        segments = re.split(r"\n\s*\n", full_text)
        parsed_clauses = []
        clause_index = 1
        for segment in segments:
            cleaned = segment.strip()
            if not cleaned:
                continue
            parsed_clauses.append(
                {
                    "clause_index": clause_index,
                    "raw_text": cleaned,
                }
            )
            clause_index += 1

        return {
            "status": "success",
            "filename": filename,
            "parsed_clauses": parsed_clauses,
        }
    except Exception:
        raise HTTPException(
            status_code=400,
            detail={"filename": filename, "message": "Failed to parse PDF."},
        )


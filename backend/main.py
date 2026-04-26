from __future__ import annotations

import re
from contextlib import asynccontextmanager
from typing import Any, List

import fitz  # PyMuPDF
from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from classifier import mock_classify
from database import Base, engine, get_db
from models import Contract, ParsedClause


# ---------------------------------------------------------------------------
# Application lifespan — create tables on startup
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create all tables when the app starts (dev convenience)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(lifespan=lifespan)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
    # Exact error envelope required by the Step 1 API contract.
    return {
        "status": "error",
        "filename": filename,
        "contract_id": None,
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


# ---------------------------------------------------------------------------
# CORS — Allow the Next.js dev server to talk to FastAPI locally.
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Upload endpoint — Step 1: parse → classify → persist → return handoff JSON
# ---------------------------------------------------------------------------

@app.post("/api/contracts/upload")
async def upload_contract(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
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

        # --- Classify each segment ---
        classified = []
        clause_index = 1
        for segment in segments:
            cleaned = segment.strip()
            if not cleaned:
                continue
            ctype, confidence = mock_classify(cleaned)
            classified.append({
                "clause_index": clause_index,
                "raw_text": cleaned,
                "clause_type": ctype,
                "clause_type_confidence": confidence,
            })
            clause_index += 1

        # --- Persist to PostgreSQL ---
        contract = Contract(original_filename=filename)
        db.add(contract)
        await db.flush()  # populates contract.id

        clause_rows: list[ParsedClause] = []
        for item in classified:
            row = ParsedClause(
                contract_id=contract.id,
                clause_index=item["clause_index"],
                raw_text=item["raw_text"],
                clause_type=item["clause_type"],
                clause_type_confidence=item["clause_type_confidence"],
            )
            db.add(row)
            clause_rows.append(row)

        await db.commit()

        # --- Build handoff response ---
        return {
            "status": "success",
            "filename": filename,
            "contract_id": str(contract.id),
            "parsed_clauses": [
                {
                    "parsed_clause_id": str(row.id),
                    "contract_id": str(contract.id),
                    "clause_index": row.clause_index,
                    "raw_text": row.raw_text,
                    "clause_type": row.clause_type,
                    "clause_type_confidence": float(row.clause_type_confidence),
                }
                for row in clause_rows
            ],
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=400,
            detail={"filename": filename, "message": "Failed to parse PDF."},
        )

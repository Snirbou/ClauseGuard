# Walkthrough — Step 1: PostgreSQL Integration & Mock ML Classifier

## Summary

Step 1 transitions ClauseGuard from a stateless Walking Skeleton to a persisted, classifiable pipeline. Every uploaded PDF now creates a `contracts` row and a set of `parsed_clauses` rows in PostgreSQL, each annotated with a mock `clause_type` and `clause_type_confidence`.

---

## Files Created (8)

| File | Purpose |
|------|---------|
| [docker-compose.yml](file:///c:/Users/kohen/OneDrive/Desktop/%D7%A4%D7%A8%D7%95%D7%99%D7%A7%D7%98%D7%99%D7%9D/ClauseGuard/docker-compose.yml) | Postgres 16 Alpine container (user/pass/db: `clauseguard`, port 5432) |
| [backend/.env](file:///c:/Users/kohen/OneDrive/Desktop/%D7%A4%D7%A8%D7%95%D7%99%D7%A7%D7%98%D7%99%D7%9D/ClauseGuard/backend/.env) | `DATABASE_URL` for local dev (gitignored) |
| [backend/.env.example](file:///c:/Users/kohen/OneDrive/Desktop/%D7%A4%D7%A8%D7%95%D7%99%D7%A7%D7%98%D7%99%D7%9D/ClauseGuard/backend/.env.example) | Template for `.env` (safe to commit) |
| [backend/config.py](file:///c:/Users/kohen/OneDrive/Desktop/%D7%A4%D7%A8%D7%95%D7%99%D7%A7%D7%98%D7%99%D7%9D/ClauseGuard/backend/config.py) | Pydantic-settings singleton loading `DATABASE_URL` |
| [backend/database.py](file:///c:/Users/kohen/OneDrive/Desktop/%D7%A4%D7%A8%D7%95%D7%99%D7%A7%D7%98%D7%99%D7%9D/ClauseGuard/backend/database.py) | Async engine, `async_sessionmaker`, `Base`, `get_db` dependency |
| [backend/models.py](file:///c:/Users/kohen/OneDrive/Desktop/%D7%A4%D7%A8%D7%95%D7%99%D7%A7%D7%98%D7%99%D7%9D/ClauseGuard/backend/models.py) | `Contract` + `ParsedClause` ORM models (UUID PKs, FK cascade) |
| [backend/classifier.py](file:///c:/Users/kohen/OneDrive/Desktop/%D7%A4%D7%A8%D7%95%D7%99%D7%A7%D7%98%D7%99%D7%9D/ClauseGuard/backend/classifier.py) | `mock_classify()` — 7 keyword rules + `"general"` fallback |
| [.gitignore](file:///c:/Users/kohen/OneDrive/Desktop/%D7%A4%D7%A8%D7%95%D7%99%D7%A7%D7%98%D7%99%D7%9D/ClauseGuard/.gitignore) | Root gitignore protecting `.env` from accidental commit |

## Files Modified (2)

| File | Change |
|------|--------|
| [backend/requirements.txt](file:///c:/Users/kohen/OneDrive/Desktop/%D7%A4%D7%A8%D7%95%D7%99%D7%A7%D7%98%D7%99%D7%9D/ClauseGuard/backend/requirements.txt) | Added: `sqlalchemy[asyncio]`, `asyncpg`, `pydantic-settings`, `python-dotenv` |
| [backend/main.py](file:///c:/Users/kohen/OneDrive/Desktop/%D7%A4%D7%A8%D7%95%D7%99%D7%A7%D7%98%D7%99%D7%9D/ClauseGuard/backend/main.py) | Full refactor: DB session injection, mock classification, PostgreSQL persistence, backward-compatible handoff JSON |

---

## Key Changes in `main.py`

```diff:main.py
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

===
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

```

### What changed:
1. **Lifespan context manager** — auto-creates tables on startup via `Base.metadata.create_all`
2. **`Depends(get_db)`** — injects an `AsyncSession` into the endpoint
3. **Classification loop** — each segment passes through `mock_classify()` before persistence
4. **DB persistence** — `Contract` row created → flushed for UUID → `ParsedClause` rows bulk-inserted → committed
5. **Error envelope** — now includes `contract_id: null` for consistency
6. **`except HTTPException: raise`** — fixes the Step 0 bug where `HTTPException` was silently swallowed by the bare `except Exception`

---

## Startup Commands

Run these in order from the project root:

### 1. Start PostgreSQL (Docker)
```powershell
docker compose up -d
```

### 2. Install new Python dependencies
```powershell
pip install -r backend/requirements.txt
```

### 3. Start FastAPI backend
```powershell
cd backend
uvicorn main:app --reload --port 8000
```
> Tables are auto-created on first startup via the lifespan hook.

### 4. Smoke test (backend only)
```powershell
curl -X POST http://127.0.0.1:8000/api/contracts/upload `
  -F "file=@C:/path/to/your/contract.pdf"
```

Expected response shape:
```json
{
  "status": "success",
  "filename": "contract.pdf",
  "contract_id": "<uuid>",
  "parsed_clauses": [
    {
      "parsed_clause_id": "<uuid>",
      "contract_id": "<uuid>",
      "clause_index": 1,
      "raw_text": "...",
      "clause_type": "payment_terms",
      "clause_type_confidence": 0.85
    }
  ]
}
```

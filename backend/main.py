from __future__ import annotations

# numpy MUST be fully imported before dspy/litellm. dspy's import chain
# leaves numpy in a state where a later in-process spaCy/thinc import
# re-executes numpy/__init__ and dies with "data type 'bool' not
# understood", killing the Layer 1 classifier. Importing numpy first is the
# empirically verified fix (see docs/ROADMAP.md, Phase A).
import numpy  # noqa: F401  isort: skip

import re
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Any
from uuid import UUID

import anyio.to_thread
import fitz  # PyMuPDF
from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware

from analysis_service import (
    AnalysisError,
    distribution_from_levels,
    get_run,
    latest_run_for_contract,
    recover_stale_runs,
    shutdown_analysis_tasks,
    start_analysis,
    wait_for_run,
)
from api_schemas import (
    AnalysisRunInfo,
    AnalysisRunResponse,
    AnalyzeAcceptedResponse,
    ClauseDetail,
    ContractDetailResponse,
    ContractListResponse,
    ContractSummary,
    DeleteResponse,
    HealthResponse,
)
from classifier import classifier_info, classify, warm_up
from config import settings
from database import get_db, init_db
from logger import get_logger
from models import Contract, ParsedClause, RiskScore

logger = get_logger(__name__)

_UPLOAD_CHUNK_BYTES = 1024 * 1024      # stream the upload 1 MB at a time

# Fallback clause boundaries, used only when blank-line splitting fails.
# Zero-width lookahead so the heading stays attached to the clause it starts.
_CLAUSE_HEADING_RE = re.compile(
    r"(?=^[ \t]*(?:"
    r"(?:ARTICLE|SECTION|CLAUSE)\s+[0-9IVXL]+"     # "ARTICLE 5", "Section IV"
    r"|\d{1,2}(?:\.\d{1,2})*[.)]\s+[A-Z]"          # "1. SCOPE", "2.1) Payment"
    r"))",
    re.MULTILINE | re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Application lifespan — create tables on startup
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create all tables and indexes when the app starts (dev convenience)."""
    try:
        await init_db()
    except Exception as exc:
        # Deliberately non-fatal: the app still serves /api/health, which
        # reports database="unavailable". Refusing to boot would instead give
        # the frontend an opaque connection error with no explanation.
        logger.error(
            "Could not initialise the database (%s). Is Postgres running? "
            "Start it with: docker compose up -d",
            exc,
        )

    if not settings.llm_configured:
        logger.warning(
            "No language model configured — POST /api/contracts/{id}/analyze "
            "will return 503. Set a real OPENAI_API_KEY in backend/.env."
        )

    # Runs left pending/running by a previous process cannot still be
    # executing — surface them as failed so the user can simply re-run.
    try:
        await recover_stale_runs()
    except Exception:
        logger.exception("Stale-run recovery failed (continuing).")

    # Load the Layer 1 classifier off the event loop so the first upload is
    # not the request that pays the spaCy model load. Never fatal: on any
    # failure classify() falls back to the keyword rules.
    mode = await anyio.to_thread.run_sync(warm_up)
    logger.info("Layer 1 classifier ready (mode=%s).", mode)
    yield
    # Cancel in-flight analysis runs; they finalize their DB rows as failed.
    await shutdown_analysis_tasks()


app = FastAPI(
    title="ClauseGuard API",
    version="0.3.0",
    description=(
        "Upload freelance contract PDFs, segment them into clauses, and run "
        "DSPy-powered risk analysis over the result."
    ),
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Error envelopes
# ---------------------------------------------------------------------------

def _upload_error_envelope(*, filename: str, detail: str) -> dict[str, Any]:
    """The exact error envelope required by the Step 1 upload API contract."""
    return {
        "status": "error",
        "filename": filename,
        "contract_id": None,
        "parsed_clauses": [],
        "detail": detail,
    }


def _error_envelope(detail: str) -> dict[str, Any]:
    """Error envelope for every endpoint other than upload."""
    return {"status": "error", "detail": detail}


def _upload_http_error(filename: str, message: str, status_code: int = 400) -> HTTPException:
    """Build an HTTPException that the handler renders as the upload envelope.

    Encoding the filename in ``detail`` is how the upload route keeps its
    documented error shape while still going through normal FastAPI raising.
    """
    return HTTPException(
        status_code=status_code,
        detail={"filename": filename, "message": message},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict) and "filename" in exc.detail:
        # Upload-route error — preserve the legacy envelope verbatim.
        message = exc.detail.get("message") or exc.detail.get("detail")
        content = _upload_error_envelope(
            filename=str(exc.detail.get("filename") or "uploaded.pdf"),
            detail=str(message) if message is not None else str(exc.detail),
        )
    else:
        content = _error_envelope(str(exc.detail))

    return JSONResponse(
        status_code=exc.status_code,
        content=content,
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Render FastAPI's validation failures in our own envelope.

    The common case is a malformed UUID in the path, which would otherwise
    produce a shape the frontend does not know how to read.
    """
    problems = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error.get("loc", ()) if part != "body")
        problems.append(f"{location}: {error.get('msg', 'invalid value')}" if location else error.get("msg", "invalid value"))

    return JSONResponse(
        status_code=422,
        content=_error_envelope("Invalid request. " + "; ".join(problems)),
    )


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Global catch-all so an unexpected crash still returns clean JSON.

    Without this, an unhandled exception escapes to Starlette's outermost
    error middleware, which sits *outside* CORSMiddleware — the browser then
    sees an opaque CORS failure instead of the actual error.
    """

    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except Exception:
            logger.exception(
                "Unhandled error on %s %s", request.method, request.url.path
            )
            return JSONResponse(
                status_code=500,
                content=_error_envelope(
                    "Internal server error. Check the backend log for details."
                ),
            )


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
# Order matters: add_middleware() prepends, so the LAST one added is outermost.
# CORS must wrap the error handler, otherwise error responses ship without CORS
# headers and the browser cannot read them.

app.add_middleware(ErrorHandlingMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Upload helpers
# ---------------------------------------------------------------------------

def _is_pdf_upload(upload: UploadFile) -> bool:
    content_type = (upload.content_type or "").lower()
    filename = (upload.filename or "").lower()
    return content_type == "application/pdf" or filename.endswith(".pdf")


async def _read_upload_limited(upload: UploadFile, filename: str) -> bytes:
    """Read the upload, refusing anything over ``MAX_UPLOAD_BYTES``.

    Read in chunks rather than all at once so an oversized file is rejected
    part-way through instead of being buffered in full first.
    """
    limit = settings.MAX_UPLOAD_BYTES
    too_large = _upload_http_error(
        filename,
        f"File is too large. Maximum size is {settings.max_upload_mb:.0f} MB.",
        status_code=413,
    )

    declared_size = getattr(upload, "size", None)
    if isinstance(declared_size, int) and declared_size > limit:
        raise too_large

    chunks: list[bytes] = []
    total = 0
    try:
        while True:
            chunk = await upload.read(_UPLOAD_CHUNK_BYTES)
            if not chunk:
                break
            total += len(chunk)
            if total > limit:
                raise too_large
            chunks.append(chunk)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to read uploaded file %s", filename)
        raise _upload_http_error(filename, "Failed to read uploaded file.") from None

    return b"".join(chunks)


def _segment_clauses(full_text: str) -> list[str]:
    """Split extracted PDF text into individual clauses.

    Blank lines remain the primary rule. But PyMuPDF very often extracts a
    contract as one line per *visual* line with no blank lines at all, in which
    case that rule returns the entire document as a single clause and the whole
    downstream pipeline degenerates — one classification and one AI summary for
    the whole agreement.

    When that happens, fall back to splitting on numbered clause headings.
    The fallback only applies if it actually finds boundaries, so a genuinely
    single-clause document still comes back as one clause.
    """
    segments = [part.strip() for part in re.split(r"\n\s*\n", full_text) if part.strip()]
    if len(segments) > 1:
        return segments

    fallback = [part.strip() for part in _CLAUSE_HEADING_RE.split(full_text) if part.strip()]
    if len(fallback) > 1:
        logger.info(
            "No blank-line clause breaks found; segmented %d clauses by heading.",
            len(fallback),
        )
        return fallback

    return segments


def _extract_and_classify(raw_bytes: bytes, filename: str) -> list[dict[str, Any]]:
    """Extract text, segment into clauses, and classify each one.

    Runs on a worker thread — PyMuPDF is CPU-bound and would otherwise block
    the event loop for the duration of a large document.
    """
    doc = None
    try:
        doc = fitz.open(stream=raw_bytes, filetype="pdf")

        if doc.needs_pass:
            raise _upload_http_error(
                filename, "This PDF is password protected and cannot be read."
            )

        page_texts: list[str] = []
        for page in doc:
            page_text = page.get_text("text") or ""
            if page_text.strip():
                page_texts.append(page_text)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to parse PDF %s", filename)
        raise _upload_http_error(filename, "Failed to parse PDF.") from None
    finally:
        # fitz documents hold an open handle on the stream buffer.
        if doc is not None:
            doc.close()

    full_text = "\n\n".join(page_texts).strip()
    if not full_text:
        raise _upload_http_error(
            filename,
            "Could not extract text from PDF. It may be a scanned image, "
            "which needs OCR.",
        )

    segments = _segment_clauses(full_text)

    classified: list[dict[str, Any]] = []
    clause_index = 1
    for segment in segments:
        cleaned = segment.strip()
        if not cleaned:
            continue
        clause_type, confidence = classify(cleaned)
        classified.append(
            {
                "clause_index": clause_index,
                "raw_text": cleaned,
                "clause_type": clause_type,
                "clause_type_confidence": confidence,
            }
        )
        clause_index += 1

    if not classified:
        raise _upload_http_error(filename, "No clauses could be extracted from this PDF.")

    return classified


# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------

def _as_float(value: Decimal | float | None) -> float | None:
    """Numeric columns come back as Decimal; JSON wants a float."""
    if value is None:
        return None
    return float(value)


def _normalize_risk_factors(value: Any) -> list[str]:
    """risk_factors is JSONB — tolerate list, string, or NULL."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    return []


def _to_clause_detail(clause: ParsedClause, risk: RiskScore | None) -> ClauseDetail:
    return ClauseDetail(
        parsed_clause_id=clause.id,
        contract_id=clause.contract_id,
        clause_index=clause.clause_index,
        raw_text=clause.raw_text,
        clause_type=clause.clause_type,
        clause_type_confidence=_as_float(clause.clause_type_confidence),
        risk_level=risk.risk_level if risk else None,
        risk_score=_as_float(risk.risk_score) if risk else None,
        risk_percentile=risk.risk_percentile if risk else None,
        risk_factors=_normalize_risk_factors(risk.risk_factors) if risk else [],
        plain_language_summary=risk.plain_language_summary if risk else None,
        dspy_program_version=risk.dspy_program_version if risk else None,
        analyzed_at=risk.created_at if risk else None,
    )


async def _require_contract(db: AsyncSession, contract_id: UUID) -> Contract:
    contract = await db.get(Contract, contract_id)
    if contract is None:
        raise HTTPException(status_code=404, detail="Contract not found.")
    return contract


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/api/health", response_model=HealthResponse)
async def health(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    try:
        await db.execute(text("SELECT 1"))
        database = "ok"
    except Exception as exc:
        logger.error("Health check database probe failed: %s", exc)
        database = "unavailable"
        # Leave the session usable for the rest of its (short) life.
        await db.rollback()

    return HealthResponse(
        status="ok" if database == "ok" else "degraded",
        database=database,
        llm_configured=settings.llm_configured,
        provider=settings.DSPY_PROVIDER,
        model=settings.DSPY_MODEL,
        auto_analyze_on_upload=settings.AUTO_ANALYZE_ON_UPLOAD,
        max_upload_mb=settings.max_upload_mb,
        classifier=classifier_info(),
    )


# ---------------------------------------------------------------------------
# Upload — parse → classify → persist → return handoff JSON
# ---------------------------------------------------------------------------

@app.post("/api/contracts/upload")
async def upload_contract(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    filename = file.filename or "uploaded.pdf"

    if not _is_pdf_upload(file):
        raise _upload_http_error(filename, "Invalid file type. PDF required.")

    raw_bytes = await _read_upload_limited(file, filename)
    if not raw_bytes:
        raise _upload_http_error(filename, "Empty file.")

    classified = await anyio.to_thread.run_sync(
        _extract_and_classify, raw_bytes, filename
    )

    # --- Persist to PostgreSQL ---
    # Kept in its own try so a database failure is not reported to the user as
    # a PDF parsing failure, which is what the previous single-try version did.
    try:
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
    except Exception:
        await db.rollback()
        logger.exception("Failed to persist contract %s", filename)
        raise _upload_http_error(
            filename,
            "Failed to save the contract to the database.",
            status_code=500,
        ) from None

    # --- Build handoff response (contract fields must not change) ---
    response: dict[str, Any] = {
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

    # --- Optional auto-analysis (additive field, off by default) ---
    if settings.AUTO_ANALYZE_ON_UPLOAD:
        response["analysis"] = await _auto_analyze(db, contract.id)

    return response


async def _auto_analyze(db: AsyncSession, contract_id: UUID) -> dict[str, Any]:
    """Schedule analysis right after upload, degrading gracefully on failure.

    A failed schedule must never fail the upload — the contract is already
    saved and the user can start the analysis from the detail page. The
    upload response does not wait for the run; it carries the run id.
    """
    try:
        run = await start_analysis(db, contract_id)
    except AnalysisError as exc:
        logger.warning("Auto-analysis skipped for %s: %s", contract_id, exc.message)
        return {"status": "skipped", "detail": exc.message}
    except Exception:
        logger.exception("Auto-analysis crashed for contract %s", contract_id)
        return {
            "status": "skipped",
            "detail": "Automatic analysis failed to start. Try again from the contract page.",
        }

    return {"status": "started", "run_id": str(run.id)}


# ---------------------------------------------------------------------------
# GET /api/contracts — list view
# ---------------------------------------------------------------------------

@app.get("/api/contracts", response_model=ContractListResponse)
async def list_contracts(db: AsyncSession = Depends(get_db)) -> ContractListResponse:
    # DISTINCT matters: the double LEFT JOIN multiplies rows, so a plain
    # COUNT would report clause_count * analyzed_count.
    clause_count = func.count(func.distinct(ParsedClause.id)).label("clause_count")
    analyzed_count = func.count(func.distinct(RiskScore.id)).label("analyzed_count")

    stmt = (
        select(
            Contract.id,
            Contract.original_filename,
            Contract.created_at,
            clause_count,
            analyzed_count,
        )
        .select_from(Contract)
        .outerjoin(ParsedClause, ParsedClause.contract_id == Contract.id)
        .outerjoin(RiskScore, RiskScore.parsed_clause_id == ParsedClause.id)
        .group_by(Contract.id, Contract.original_filename, Contract.created_at)
        .order_by(Contract.created_at.desc())
    )

    rows = (await db.execute(stmt)).all()

    contracts = [
        ContractSummary(
            id=row.id,
            original_filename=row.original_filename,
            created_at=row.created_at,
            clause_count=row.clause_count,
            analyzed_clause_count=row.analyzed_count,
            has_analysis=row.analyzed_count > 0,
        )
        for row in rows
    ]

    return ContractListResponse(count=len(contracts), contracts=contracts)


# ---------------------------------------------------------------------------
# GET /api/contracts/{id} — detail view with risk data
# ---------------------------------------------------------------------------

@app.get("/api/contracts/{contract_id}", response_model=ContractDetailResponse)
async def get_contract(
    contract_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ContractDetailResponse:
    contract = await _require_contract(db, contract_id)

    stmt = (
        select(ParsedClause, RiskScore)
        .outerjoin(RiskScore, RiskScore.parsed_clause_id == ParsedClause.id)
        .where(ParsedClause.contract_id == contract_id)
        .order_by(ParsedClause.clause_index)
    )
    rows = (await db.execute(stmt)).all()

    clauses = [_to_clause_detail(clause, risk) for clause, risk in rows]
    analyzed = sum(1 for clause in clauses if clause.risk_level is not None)

    latest = await latest_run_for_contract(db, contract_id)

    return ContractDetailResponse(
        id=contract.id,
        original_filename=contract.original_filename,
        created_at=contract.created_at,
        clause_count=len(clauses),
        analyzed_clause_count=analyzed,
        has_analysis=analyzed > 0,
        risk_distribution=distribution_from_levels(c.risk_level for c in clauses),
        latest_run=_to_run_info(latest) if latest else None,
        clauses=clauses,
    )


# ---------------------------------------------------------------------------
# Analysis runs — the bridge
# ---------------------------------------------------------------------------

def _to_run_info(run) -> AnalysisRunInfo:
    return AnalysisRunInfo(
        id=run.id,
        contract_id=run.contract_id,
        status=run.status,
        started_at=run.started_at,
        completed_at=run.completed_at,
        processing_time_ms=run.processing_time_ms,
        clause_count=run.clause_count,
        completed_clauses=run.completed_clauses or 0,
        error_message=run.error_message,
        run_metadata=run.run_metadata,
    )


@app.post(
    "/api/contracts/{contract_id}/analyze",
    response_model=AnalyzeAcceptedResponse,
    status_code=202,
)
async def analyze(
    contract_id: UUID,
    wait: bool = False,
    force: bool = False,
    db: AsyncSession = Depends(get_db),
) -> AnalyzeAcceptedResponse:
    """Schedule an analysis run over every clause of the contract.

    Returns 202 with the run immediately; poll GET /api/analysis-runs/{id}
    for progress while per-clause results land incrementally.

    Query flags:
      wait=true   block until the run finishes before responding (tests/CLI)
      force=true  re-analyze every clause, ignoring the content-hash cache
    """
    await _require_contract(db, contract_id)

    try:
        run = await start_analysis(db, contract_id, force=force)
    except AnalysisError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    if wait:
        await wait_for_run(run.id)
        await db.refresh(run)

    return AnalyzeAcceptedResponse(run=_to_run_info(run))


@app.get("/api/analysis-runs/{run_id}", response_model=AnalysisRunResponse)
async def get_analysis_run(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> AnalysisRunResponse:
    run = await get_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Analysis run not found.")
    return AnalysisRunResponse(run=_to_run_info(run))


# ---------------------------------------------------------------------------
# DELETE /api/contracts/{id}
# ---------------------------------------------------------------------------

@app.delete("/api/contracts/{contract_id}", response_model=DeleteResponse)
async def delete_contract(
    contract_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> DeleteResponse:
    """Delete a contract; parsed_clauses and risk_scores cascade in Postgres.

    Uses a Core DELETE rather than ``session.delete(obj)`` because the ORM
    cascade would lazy-load the clause collection, which raises MissingGreenlet
    on an async session.
    """
    try:
        result = await db.execute(sa_delete(Contract).where(Contract.id == contract_id))
        # Read rowcount before commit — the cursor result is only guaranteed
        # to carry it while the transaction is still open.
        deleted_rows = result.rowcount
        await db.commit()
    except Exception:
        await db.rollback()
        logger.exception("Failed to delete contract %s", contract_id)
        raise HTTPException(status_code=500, detail="Failed to delete the contract.") from None

    if deleted_rows == 0:
        raise HTTPException(status_code=404, detail="Contract not found.")

    return DeleteResponse(contract_id=contract_id)

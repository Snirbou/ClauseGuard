"""Pydantic response models for the ClauseGuard HTTP API.

Kept separate from ``schemas.py`` (which models the DSPy pipeline's internal
input/output) so that the wire format can evolve without disturbing the
pipeline contract.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Shared pieces
# ---------------------------------------------------------------------------

class RiskDistribution(BaseModel):
    """How the clauses of a contract are spread across risk levels."""

    high: int = 0
    medium: int = 0
    low: int = 0
    unanalyzed: int = 0


class ClauseDetail(BaseModel):
    """A parsed clause plus its risk analysis, when one exists.

    Every risk field is optional: a clause that has not been through the DSPy
    pipeline yet has a ``parsed_clauses`` row but no ``risk_scores`` row.
    """

    parsed_clause_id: UUID
    contract_id: UUID
    clause_index: int
    raw_text: str
    clause_type: str | None = None
    clause_type_confidence: float | None = None

    # --- populated from risk_scores (LEFT JOIN) ---
    risk_level: str | None = None
    risk_score: float | None = None
    risk_percentile: int | None = None
    risk_factors: list[str] = Field(default_factory=list)
    plain_language_summary: str | None = None
    dspy_program_version: str | None = None
    analyzed_at: datetime | None = None

    @property
    def has_analysis(self) -> bool:
        return self.risk_level is not None


# ---------------------------------------------------------------------------
# GET /api/contracts
# ---------------------------------------------------------------------------

class ContractSummary(BaseModel):
    """One row of the contracts list view."""

    id: UUID
    original_filename: str
    created_at: datetime
    clause_count: int
    analyzed_clause_count: int
    has_analysis: bool


class ContractListResponse(BaseModel):
    status: Literal["success"] = "success"
    count: int
    contracts: list[ContractSummary]


# ---------------------------------------------------------------------------
# GET /api/contracts/{id}
# ---------------------------------------------------------------------------

class ContractFindingInfo(BaseModel):
    """A contract-level finding (currently: missing-protection detections)."""

    id: UUID
    finding_type: str          # "missing_protection"
    pain_point: str            # PRD §1.2 category
    severity: str              # "high" | "medium"
    title: str
    detail: str


class ContractDetailResponse(BaseModel):
    status: Literal["success"] = "success"
    id: UUID
    original_filename: str
    created_at: datetime
    clause_count: int
    analyzed_clause_count: int
    has_analysis: bool
    risk_distribution: RiskDistribution
    # Contract-level outputs of the latest analysis run.
    analysis_summary: str | None = None
    findings: list[ContractFindingInfo] = Field(default_factory=list)
    # Most recent analysis run, if any — lets the UI resume polling an
    # in-flight run after a page refresh and surface the last error.
    latest_run: AnalysisRunInfo | None = None
    clauses: list[ClauseDetail]


# ---------------------------------------------------------------------------
# Analysis runs (POST /api/contracts/{id}/analyze + GET /api/analysis-runs/{id})
# ---------------------------------------------------------------------------

class AnalysisRunInfo(BaseModel):
    """State of one analysis run — the shape the frontend polls."""

    id: UUID
    contract_id: UUID
    status: Literal["pending", "running", "completed", "failed"]
    started_at: datetime
    completed_at: datetime | None = None
    processing_time_ms: int | None = None
    clause_count: int | None = None
    completed_clauses: int = 0
    error_message: str | None = None
    # provider/model/dspy_version/cached_clauses/analyzed_clauses/...
    run_metadata: dict[str, Any] | None = None


class AnalyzeAcceptedResponse(BaseModel):
    """202 body: the run was scheduled; poll GET /api/analysis-runs/{id}."""

    status: Literal["accepted"] = "accepted"
    run: AnalysisRunInfo


class AnalysisRunResponse(BaseModel):
    status: Literal["success"] = "success"
    run: AnalysisRunInfo


# ---------------------------------------------------------------------------
# DELETE /api/contracts/{id}
# ---------------------------------------------------------------------------

class DeleteResponse(BaseModel):
    status: Literal["success"] = "success"
    contract_id: UUID
    deleted: bool = True


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class AuthRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)
    password: str = Field(..., min_length=1, max_length=512)


class UserResponse(BaseModel):
    status: Literal["success"] = "success"
    id: UUID
    email: str


# ---------------------------------------------------------------------------
# Compliance & metrics
# ---------------------------------------------------------------------------

class DisclaimerViewRequest(BaseModel):
    """Body of POST /api/disclaimer-views (UPL audit trail, AC-X05)."""

    page: str = Field(..., min_length=1, max_length=256)
    contract_id: UUID | None = None


class MetricsResponse(BaseModel):
    """Evaluation dashboard payload (AcceptanceCriteria §4).

    Every block is a free-form dict so fields can be added without breaking
    older clients; the frontend types (frontend/src/types/contracts.ts)
    document the current shape.
    """

    status: Literal["success"] = "success"
    classifier: dict[str, Any]
    runs: dict[str, Any]
    pipeline: dict[str, Any]
    compliance: dict[str, Any]
    # Additive (Phase 3): summary readability (AC-P04) and high-risk
    # precision/recall (AC-R05); empty dicts when not measured.
    quality: dict[str, Any] = Field(default_factory=dict)
    risk: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str
    database: str
    llm_configured: bool
    provider: str
    model: str
    auto_analyze_on_upload: bool
    max_upload_mb: float
    # Whether scanned PDFs can be read: OCR is enabled AND a Tesseract
    # binary is present. False means image-only uploads are refused.
    ocr: dict[str, Any] = Field(default_factory=dict)
    # Layer 1 classifier status: mode ("model" | "mock"), artifact metadata
    # and test metrics when the trained pipeline is live.
    classifier: dict[str, Any] = Field(default_factory=dict)
    # Set when the database could not be initialised at startup (migrations
    # did not run). The endpoint answers 503 while this is non-null.
    startup_error: str | None = None

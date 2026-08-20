"""SQLAlchemy ORM models for ClauseGuard.

Tables:
    contracts       — uploaded contract metadata (no user_id yet; Step 3).
    parsed_clauses  — individual clauses extracted from a contract.
    risk_scores     — DSPy analysis output, one row per parsed clause.

Schema rule: columns and tables here are additive only.  Existing columns are
never renamed or removed.  Indexes added below are also applied to already
existing databases by ``ensure_indexes()`` in ``database.py`` — SQLAlchemy's
``create_all`` only builds indexes for tables it creates from scratch.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from database import Base


class User(Base):
    """Registered user (AC-A01/A04). Passwords are Argon2 hashes, never text."""

    __tablename__ = "users"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    email = Column(String(320), nullable=False, unique=True, index=True)
    password_hash = Column(String(256), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class Session(Base):
    """Server-side session backing the httpOnly cookie.

    The cookie carries the raw token; only its sha256 is stored, so a
    database leak does not leak usable sessions. Logout revokes the row.
    """

    __tablename__ = "sessions"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)


class Contract(Base):
    __tablename__ = "contracts"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    # Owner. Nullable for rows uploaded before auth existed; every new
    # upload sets it, and all read paths filter by it.
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    original_filename = Column(String(512), nullable=False)
    # Contract-level executive summary, written at the end of an analysis
    # run (one LLM call over the per-clause digest). Additive column.
    analysis_summary = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,                       # list view orders by created_at DESC
        default=lambda: datetime.now(UTC),
    )

    # Relationship
    parsed_clauses = relationship(
        "ParsedClause",
        back_populates="contract",
        cascade="all, delete-orphan",
    )


class ParsedClause(Base):
    __tablename__ = "parsed_clauses"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    contract_id = Column(
        UUID(as_uuid=True),
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,                       # every read path filters on this
    )
    clause_index = Column(Integer, nullable=False)
    raw_text = Column(Text, nullable=False)
    clause_type = Column(String(128), nullable=True)          # ML-predicted
    clause_type_confidence = Column(
        Numeric(5, 4), nullable=True,                          # 0.0000–1.0000
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    # Relationship
    contract = relationship("Contract", back_populates="parsed_clauses")
    risk_score = relationship(
        "RiskScore",
        back_populates="parsed_clause",
        uselist=False,
        cascade="all, delete-orphan",
    )


class RiskScore(Base):
    __tablename__ = "risk_scores"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    parsed_clause_id = Column(
        UUID(as_uuid=True),
        ForeignKey("parsed_clauses.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    risk_level = Column(String(16), nullable=False)
    risk_score = Column(Numeric(5, 4), nullable=False)
    risk_percentile = Column(Integer, nullable=True)
    risk_factors = Column(JSONB, nullable=True)
    plain_language_summary = Column(Text, nullable=True)
    ml_model_version_id = Column(UUID(as_uuid=True), nullable=True)
    dspy_program_version = Column(String(128), nullable=True)
    # sha256 over (clause text | provider/model | program version). When an
    # incoming clause hashes to the same value, re-analysis is skipped — the
    # stored result is already the answer this pipeline would produce.
    content_hash = Column(String(64), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    # Relationship
    parsed_clause = relationship("ParsedClause", back_populates="risk_score")


class AnalysisRun(Base):
    """One execution of the analysis pipeline over a contract.

    Matches PRD/DataModel.md §2.6. The analyze endpoint returns 202 with a
    run id; the run advances in the background and the frontend polls it.
    """

    __tablename__ = "analysis_runs"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    contract_id = Column(
        UUID(as_uuid=True),
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = Column(String(32), nullable=False, index=True)  # pending|running|completed|failed
    started_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    completed_at = Column(DateTime(timezone=True), nullable=True)
    processing_time_ms = Column(Integer, nullable=True)
    clause_count = Column(Integer, nullable=True)
    # Progress counter, incremented as each clause's result is persisted.
    completed_clauses = Column(Integer, nullable=False, default=0, server_default="0")
    error_message = Column(Text, nullable=True)
    # "metadata" is reserved on declarative models; the column keeps the
    # PRD's name while the attribute is run_metadata.
    run_metadata = Column("metadata", JSONB, nullable=True)


class DisclaimerLog(Base):
    """UPL audit trail (AC-X05): one row per disclaimer render.

    The frontend fires a log request whenever a page showing the disclaimer
    banner is viewed; the table proves the disclaimer display rate.
    """

    __tablename__ = "disclaimer_logs"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    # Nullable, no FK: the log must outlive the contract it was shown for.
    contract_id = Column(UUID(as_uuid=True), nullable=True)
    page = Column(String(256), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        default=lambda: datetime.now(UTC),
    )


class ContractFinding(Base):
    """A contract-level finding — currently missing-protection detections.

    Refreshed atomically on every analysis run (delete + insert), so the
    stored findings always reflect the latest clause classification.
    """

    __tablename__ = "contract_findings"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    contract_id = Column(
        UUID(as_uuid=True),
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    finding_type = Column(String(32), nullable=False)   # "missing_protection"
    pain_point = Column(String(64), nullable=False)     # PRD §1.2 category
    severity = Column(String(16), nullable=False)       # "high" | "medium"
    title = Column(String(256), nullable=False)
    detail = Column(Text, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

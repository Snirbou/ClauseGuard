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
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from database import Base


class Contract(Base):
    __tablename__ = "contracts"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    # user_id FK omitted — Step 3
    original_filename = Column(String(512), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,                       # list view orders by created_at DESC
        default=lambda: datetime.now(timezone.utc),
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
        default=lambda: datetime.now(timezone.utc),
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
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationship
    parsed_clause = relationship("ParsedClause", back_populates="risk_score")

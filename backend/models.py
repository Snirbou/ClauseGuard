"""SQLAlchemy ORM models for ClauseGuard Step 1.

Tables:
    contracts       — uploaded contract metadata (no user_id yet; Step 3).
    parsed_clauses  — individual clauses extracted from a contract.
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
from sqlalchemy.dialects.postgresql import UUID
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

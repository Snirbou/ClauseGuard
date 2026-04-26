# Step 1: PostgreSQL Integration & ML Classification Handoff

> **Role:** Developer 1 — System Designer / Backend Architect
> **Baseline:** Phase 0 Walking Skeleton ([main.py](file:///c:/Users/kohen/OneDrive/Desktop/%D7%A4%D7%A8%D7%95%D7%99%D7%A7%D7%98%D7%99%D7%9D/ClauseGuard/backend/main.py))
> **Constraint:** No Users / Auth (reserved for Step 3)

---

## 1. PostgreSQL Database Schema (SQLAlchemy ORM Models)

Two tables are required for Step 1. The schema below is derived from [DataModel.md](file:///c:/Users/kohen/OneDrive/Desktop/%D7%A4%D7%A8%D7%95%D7%99%D7%A7%D7%98%D7%99%D7%9D/ClauseGuard/PRD/DataModel.md) §2.2 and §2.3, **minus** the `user_id` FK (deferred to Step 3).

### 1.1 `contracts` Table

```python
# backend/models.py

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, String, Text
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
```

> [!NOTE]
> The PRD's `contracts` table also includes `file_size_bytes`, `file_storage_path`, `contract_type`, `status`, `error_message`, and `processed_at`. These columns are **intentionally omitted** in Step 1 to keep the scope minimal. They will be added when the full upload pipeline (file storage, async processing, status tracking) is wired up.

### 1.2 `parsed_clauses` Table

```python
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
```

### 1.3 Equivalent DDL (for reference)

```sql
CREATE TABLE contracts (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    original_filename VARCHAR(512) NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE parsed_clauses (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_id             UUID NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
    clause_index            INTEGER NOT NULL,
    raw_text                TEXT NOT NULL,
    clause_type             VARCHAR(128),
    clause_type_confidence  NUMERIC(5,4),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_parsed_clauses_contract_id ON parsed_clauses(contract_id);
```

---

## 2. Endpoint Modification — `/api/contracts/upload`

The existing flow in [main.py L73–L140](file:///c:/Users/kohen/OneDrive/Desktop/%D7%A4%D7%A8%D7%95%D7%99%D7%A7%D7%98%D7%99%D7%9D/ClauseGuard/backend/main.py#L73-L140) will be extended. The new flow is:

```mermaid
flowchart TD
    A["Receive PDF upload"] --> B["Validate PDF (existing)"]
    B --> C["Extract text via PyMuPDF (existing)"]
    C --> D["Naive segmentation (existing)"]
    D --> E["🆕 Run mock_classify on each segment"]
    E --> F["🆕 Create Contract row in DB"]
    F --> G["🆕 Bulk-insert ParsedClause rows"]
    G --> H["🆕 Return JSON with contract_id + UUIDs + types"]
```

### 2.1 Step-by-step pseudocode

```python
@app.post("/api/contracts/upload")
async def upload_contract(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),       # NEW: injected session
) -> dict[str, Any]:

    filename = file.filename or "uploaded.pdf"

    # --- Existing validation & PDF parsing (unchanged) ---
    # ... validate PDF type ...
    # ... read bytes ...
    # ... extract text with PyMuPDF ...
    # ... naive segmentation via re.split(r"\n\s*\n", full_text) ...

    # --- NEW: Classify each segment ---
    classified = []
    for idx, segment in enumerate(segments, start=1):
        cleaned = segment.strip()
        if not cleaned:
            continue
        ctype, confidence = mock_classify(cleaned)  # see §3
        classified.append({
            "clause_index": idx,
            "raw_text": cleaned,
            "clause_type": ctype,
            "clause_type_confidence": confidence,
        })

    # --- NEW: Persist to PostgreSQL ---
    contract = Contract(original_filename=filename)
    db.add(contract)
    await db.flush()                          # populates contract.id

    clause_rows = []
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

    # --- NEW: Build handoff response ---
    return {
        "status": "success",
        "filename": filename,                    # KEPT: backward compat with Step 0 frontend
        "contract_id": str(contract.id),
        "parsed_clauses": [
            {
                "parsed_clause_id": str(row.id),
                "contract_id": str(contract.id),
                "clause_index": row.clause_index,  # KEPT: backward compat with Step 0 frontend
                "raw_text": row.raw_text,
                "clause_type": row.clause_type,
                "clause_type_confidence": float(row.clause_type_confidence),
            }
            for row in clause_rows
        ],
    }
```

> [!NOTE]
> The Step 0 response fields (`filename` at top level, `clause_index` per clause) are **preserved** alongside the new Step 1 fields (`contract_id`, `parsed_clause_id`, `clause_type`, `clause_type_confidence`). This ensures the existing Next.js frontend continues to work without modification during the transition.

---

## 3. Mock ML Classifier (Rule-Based)

A pure-Python function with no external dependencies that acts as a stand-in for the real Layer 1 Scikit-learn classifier. It will be replaced by **Developer 1 (Full-Stack & ML)** when the real spaCy + Scikit-learn pipeline is built. Developer 2 (DSPy) does **not** touch this function — they only consume the classified records from the database.

```python
# backend/classifier.py

def mock_classify(raw_text: str) -> tuple[str, float]:
    """
    Rule-based mock classifier.
    Returns (clause_type, confidence).
    """
    text_lower = raw_text.lower()

    rules: list[tuple[list[str], str, float]] = [
        (
            ["intellectual property", "ip ", "ip,", "ownership of work",
             "work product", "inventions", "copyright assignment"],
            "ip_assignment",
            0.92,
        ),
        (
            ["payment", "invoice", "compensation", "fee", "remuneration",
             "net 30", "net 60", "billing"],
            "payment_terms",
            0.85,
        ),
        (
            ["terminat", "cancel", "expir", "end of term",
             "notice period", "wind down"],
            "termination",
            0.88,
        ),
        (
            ["liable", "liability", "indemnif", "damages",
             "limitation of liability", "hold harmless"],
            "liability",
            0.83,
        ),
        (
            ["confidential", "non-disclosure", "nda", "proprietary information",
             "trade secret"],
            "confidentiality",
            0.90,
        ),
        (
            ["scope of work", "deliverables", "services", "obligations",
             "responsibilities", "statement of work"],
            "scope_of_work",
            0.80,
        ),
        (
            ["governing law", "jurisdiction", "dispute resolution",
             "arbitration", "venue", "applicable law"],
            "governing_law",
            0.87,
        ),
    ]

    for keywords, clause_type, confidence in rules:
        if any(kw in text_lower for kw in keywords):
            return clause_type, confidence

    return "general", 0.50
```

> [!TIP]
> The function signature `(raw_text: str) -> tuple[str, float]` is intentionally simple so that Developer 1 can later swap it with a Scikit-learn `model.predict()` + `model.predict_proba()` call without changing the calling code in `main.py`.

---

## 4. JSON Handoff Schema (Layer 2 API Contract)

This is the **exact** JSON response the endpoint will return after Step 1. Layer 2 (DSPy pipeline, Developer 2) will consume the `parsed_clauses` array from this response (or query them from the DB by `contract_id`).

### 4.1 Success Response (`200 OK`)

```json
{
  "status": "success",
  "filename": "msa.pdf",
  "contract_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "parsed_clauses": [
    {
      "parsed_clause_id": "11111111-2222-3333-4444-555555555555",
      "contract_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "clause_index": 1,
      "raw_text": "All intellectual property created during this engagement...",
      "clause_type": "ip_assignment",
      "clause_type_confidence": 0.92
    },
    {
      "parsed_clause_id": "66666666-7777-8888-9999-000000000000",
      "contract_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "clause_index": 2,
      "raw_text": "Payment shall be made within 30 days of invoice...",
      "clause_type": "payment_terms",
      "clause_type_confidence": 0.85
    },
    {
      "parsed_clause_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
      "contract_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "clause_index": 3,
      "raw_text": "This agreement is made between Party A and Party B...",
      "clause_type": "general",
      "clause_type_confidence": 0.50
    }
  ]
}
```

### 4.2 Error Response (`400`)

```json
{
  "status": "error",
  "filename": "uploaded.mp4",
  "contract_id": null,
  "parsed_clauses": [],
  "detail": "Invalid file type. PDF required."
}
```

### 4.3 Field Specifications

| Field | Type | Source | Notes |
|-------|------|--------|-------|
| `status` | `"success" \| "error"` | Endpoint logic | Same as Step 0 |
| `filename` | `string` | Upload filename | **Kept from Step 0** for backward compat |
| `contract_id` | `string (UUID)` or `null` | `contracts.id` | `null` on error |
| `parsed_clauses` | `array` | `parsed_clauses` table | Empty `[]` on error |
| `parsed_clauses[].parsed_clause_id` | `string (UUID)` | `parsed_clauses.id` | Primary key |
| `parsed_clauses[].contract_id` | `string (UUID)` | FK echo | Always matches top-level `contract_id` |
| `parsed_clauses[].clause_index` | `integer` | 1-based monotonic | **Kept from Step 0** for backward compat |
| `parsed_clauses[].raw_text` | `string` | Extracted text | Same as Step 0 |
| `parsed_clauses[].clause_type` | `string` | Mock classifier | One of: `ip_assignment`, `payment_terms`, `termination`, `liability`, `confidentiality`, `scope_of_work`, `governing_law`, `general` |
| `parsed_clauses[].clause_type_confidence` | `float` | Mock classifier | Range `[0.0, 1.0]` |

> [!NOTE]
> **Full backward compatibility with Step 0 is maintained.** The `filename` top-level field and `clause_index` per-clause field are preserved. The frontend will not break. New consumers (Layer 2 / DSPy) should use `contract_id` and `parsed_clause_id` for DB lookups.

---

## 5. New Backend Dependencies

| Package | Purpose | Version Strategy |
|---------|---------|-----------------|
| `sqlalchemy[asyncio]` | ORM + async engine | `>=2.0` (modern 2.x style) |
| `asyncpg` | Async PostgreSQL driver for SQLAlchemy | Latest stable |
| `pydantic-settings` | Load `DATABASE_URL` from `.env` | Latest stable |
| `python-dotenv` | `.env` file loading (used by pydantic-settings) | Latest stable |
| `alembic` | DB migrations (optional for Step 1, required for Step 2+) | Latest stable |

### Updated `requirements.txt`

```
fastapi
uvicorn
python-multipart
PyMuPDF
sqlalchemy[asyncio]
asyncpg
pydantic-settings
python-dotenv
```

### `.env` file (new, gitignored)

```env
DATABASE_URL=postgresql+asyncpg://clauseguard:clauseguard@localhost:5432/clauseguard
```

---

## Proposed File Structure After Step 1

```
ClauseGuard/
├── docker-compose.yml   # NEW: local PostgreSQL container
└── backend/
    ├── main.py          # Modified: endpoint now persists + classifies
    ├── models.py        # NEW: SQLAlchemy ORM models (Contract, ParsedClause)
    ├── database.py      # NEW: async engine, session factory, Base
    ├── config.py        # NEW: pydantic-settings for DATABASE_URL
    ├── classifier.py    # NEW: mock_classify() function
    ├── requirements.txt # Modified: new dependencies
    ├── .env             # NEW: local DB connection string (gitignored)
    └── .env.example     # NEW: template for .env
```

### `docker-compose.yml` (project root)

```yaml
version: "3.9"
services:
  postgres:
    image: postgres:16-alpine
    container_name: clauseguard-db
    restart: unless-stopped
    ports:
      - "5432:5432"
    environment:
      POSTGRES_USER: clauseguard
      POSTGRES_PASSWORD: clauseguard
      POSTGRES_DB: clauseguard
    volumes:
      - pg_data:/var/lib/postgresql/data

volumes:
  pg_data:
```

> [!TIP]
> Start the database with `docker compose up -d` from the project root before running the backend.

---

## Resolved Decisions

| Decision | Resolution |
|----------|------------|
| **Q1 — Frontend backward compat** | ✅ **Keep both.** `filename` stays at top level, `clause_index` stays in each clause object, alongside the new UUID and ML fields. No frontend breakage. |
| **Q2 — PostgreSQL provisioning** | ✅ **Docker Compose.** A `docker-compose.yml` with Postgres 16 Alpine is included (see §File Structure above). |
| **Q3 — Sync vs Async** | ✅ **Async.** Using `asyncpg` + async SQLAlchemy sessions, matching FastAPI's async-native design. |
| **Role correction** | ✅ **Developer 1** (Full-Stack & ML) owns the mock classifier swap to real Scikit-learn/spaCy. Developer 2 (DSPy) only reads classified records from the DB. |

---

## Verification Plan

### Automated Tests
1. Start the backend with `uvicorn main:app --reload --port 8000`.
2. Upload a test PDF via `curl`:
   ```powershell
   curl -X POST http://127.0.0.1:8000/api/contracts/upload `
     -F "file=@C:/path/to/test.pdf"
   ```
3. Verify the response matches the §4.1 schema exactly (check for `contract_id`, `parsed_clause_id`, `clause_type`, `clause_type_confidence`).
4. Query the database directly to confirm rows exist:
   ```sql
   SELECT * FROM contracts ORDER BY created_at DESC LIMIT 1;
   SELECT * FROM parsed_clauses WHERE contract_id = '<uuid>' ORDER BY clause_index;
   ```

### Manual Verification
- Upload a contract PDF with known clause types (e.g., one containing "payment" and "intellectual property" keywords) and verify the mock classifier labels them correctly.
- Upload a non-PDF file and verify the error envelope matches §4.2.

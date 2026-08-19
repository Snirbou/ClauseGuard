# ClauseGuard — AI-Powered Contract Clause Analyzer

ClauseGuard reads freelance service agreements clause by clause, explains each
one in plain English, and flags the terms most likely to hurt the freelancer
signing them.

> **This tool provides educational, pattern-based analysis only. It is NOT legal
> advice. Always consult a qualified attorney.**

---

## Current status

The upload pipeline and the AI analysis pipeline are **connected end to end**.
A contract can be uploaded, segmented, classified, analyzed and read entirely
from the web UI — no CLI step required.

| Capability | Status |
|---|---|
| PDF upload, text extraction, clause segmentation | ✅ |
| Rule-based clause classification (7 types + fallback) | ✅ *(mock — placeholder for a real ML model)* |
| Persistence to PostgreSQL (contracts / parsed_clauses / risk_scores) | ✅ |
| DSPy + OpenAI risk analysis triggered from the API | ✅ |
| Contract list / detail / delete endpoints | ✅ |
| Full Next.js frontend (landing, upload, list, analysis) | ✅ |
| UPL disclaimer + "Consult a Lawyer" CTA | ✅ |
| Optional auto-analysis on upload | ✅ *(off by default)* |
| Authentication / multi-user | ❌ not started |
| Background job queue for analysis | ❌ analysis runs synchronously |
| OCR for scanned PDFs | ❌ text-layer PDFs only |
| Hebrew / RTL UI | ❌ English-first for now |

---

## Architecture

```
      Browser (Next.js 16 / React 19 / Tailwind 4)
        │
        │  POST /api/contracts/upload        (multipart PDF)
        │  GET  /api/contracts               (list)
        │  GET  /api/contracts/{id}          (detail + risk join)
        │  POST /api/contracts/{id}/analyze  (run the AI pipeline)
        │  DELETE /api/contracts/{id}
        ▼
      FastAPI (backend/main.py)
        │
        ├─ PyMuPDF ──► text extraction ──► clause segmentation
        │                                       │
        │                                       ▼
        │                              classifier.mock_classify()
        │                                       │
        │                                       ▼
        │                          contracts + parsed_clauses  ──┐
        │                                                        │
        └─ analysis_service.analyze_contract()                    │  PostgreSQL 16
              │                                                   │
              ├─ dspy_pipeline.configure_lm()   (once per process) │
              ├─ dspy_pipeline.process_clauses() ──► OpenAI        │
              └─ db_writer.save_results_to_db() ──► risk_scores ───┘
```

`analysis_service.py` is the bridge that was previously missing — before it,
a developer had to run `run_pipeline.py --db --save` by hand.

### Clause segmentation

Clauses are split on blank lines. PyMuPDF frequently extracts contracts with
**no** blank lines (one line per visual line), which would collapse the whole
document into a single clause, so there is a fallback that splits on numbered
clause headings (`1. SCOPE`, `ARTICLE 5`, `2.1) Payment`). The fallback only
engages when blank-line splitting finds no boundaries.

This is still a heuristic. Replacing it with a real NLP segmenter is the
highest-value next step for analysis quality.

---

## Running locally

### 1. Start PostgreSQL

```bash
docker compose up -d
```

The backend still starts if Postgres is unreachable — it logs the failure and
`GET /api/health` reports `"database": "unavailable"`, so the UI shows a clear
message instead of an opaque connection error.

### 2. Configure the backend

```bash
cp backend/.env.example backend/.env
```

Then edit `backend/.env` and set a real `OPENAI_API_KEY`. Without one,
everything except `POST /api/contracts/{id}/analyze` works normally; that
endpoint returns `503` with an explanatory message.

### 3. Start the backend

```bash
cd backend && pip install -r requirements.txt && uvicorn main:app --reload --port 8000
```

Interactive API docs: <http://127.0.0.1:8000/docs>

### 4. Start the frontend

```bash
cd frontend && npm install && npm run dev
```

Open <http://localhost:3000>. Set `NEXT_PUBLIC_API_BASE_URL` if the backend is
not on `http://localhost:8000`.

### 5. Verify it works

With the backend running:

```bash
cd backend && python smoke_test.py
```

This walks the whole path — upload → list → detail → analyze → detail →
delete — asserting the response shape at each step, and exits non-zero on the
first failure. The analysis step is skipped automatically when no
`OPENAI_API_KEY` is configured, so it is still useful without one.

### Windows install note

`pip install -r requirements.txt` can fail with
`OSError: [Errno 2] No such file or directory` while unpacking `litellm`. This
is the 260-character `MAX_PATH` limit, not a broken package. `requirements.txt`
pins `litellm>=1.97.0`, which ships a compiled wheel without the offending
deep paths. If you still hit it, map the backend to a short drive letter and
install through that:

```bash
subst Q: C:\path\to\ClauseGuard\backend
```

---

## Configuration (`backend/.env`)

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://clauseguard:clauseguard@localhost:5432/clauseguard` | Async Postgres DSN |
| `OPENAI_API_KEY` | *(none)* | Required for AI analysis; placeholder values are detected and treated as unset |
| `DSPY_PROVIDER` | `openai` | `openai` or `ollama` |
| `DSPY_MODEL` | `gpt-4o-mini` | Model name |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Used when provider is `ollama` |
| `MAX_UPLOAD_BYTES` | `10485760` (10 MB) | Enforced in the browser and on the server |
| `AUTO_ANALYZE_ON_UPLOAD` | `false` | Run analysis inline after upload |
| `CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Comma-separated allowed origins |

`AUTO_ANALYZE_ON_UPLOAD` is off by default because it bills the LLM on every
upload and blocks the upload request until analysis finishes. When enabled, a
failed analysis never fails the upload — the response carries an
`analysis: { status: "skipped", detail: ... }` field.

---

## API

### `POST /api/contracts/upload`

`multipart/form-data` with a `file` field containing a PDF.

**Success (200)** — this envelope is a stable contract; fields are only ever added:

```json
{
  "status": "success",
  "filename": "msa.pdf",
  "contract_id": "1b9d...",
  "parsed_clauses": [
    {
      "parsed_clause_id": "7c2a...",
      "contract_id": "1b9d...",
      "clause_index": 1,
      "raw_text": "1. SCOPE OF WORK. ...",
      "clause_type": "scope_of_work",
      "clause_type_confidence": 0.8
    }
  ]
}
```

**Error** — same envelope shape, always with an empty `parsed_clauses`:

```json
{
  "status": "error",
  "filename": "msa.pdf",
  "contract_id": null,
  "parsed_clauses": [],
  "detail": "File is too large. Maximum size is 10 MB."
}
```

Status codes: `400` invalid type / unreadable / no extractable text,
`413` over the size limit, `500` database write failure.

### `GET /api/contracts`

Every contract with `clause_count`, `analyzed_clause_count` and `has_analysis`.
`has_analysis` is derived from a join against `risk_scores` rather than a status
column, so no migration is needed.

### `GET /api/contracts/{id}`

Contract metadata, a `risk_distribution` summary, and every clause LEFT JOINed
with its risk score. Risk fields are `null` for clauses that have not been
analyzed.

### `POST /api/contracts/{id}/analyze`

Runs the DSPy pipeline over every clause and upserts into `risk_scores`.
**Synchronous** — the response is sent only after analysis is persisted, which
takes roughly one LLM round-trip per clause. Moving this to a background worker
is a known future improvement.

Status codes: `404` unknown contract, `400` contract has no clauses,
`409` an analysis is already running for this contract, `503` no LLM
configured, `502` every clause failed (usually a bad key or no credit).

### `DELETE /api/contracts/{id}`

Deletes the contract; `parsed_clauses` and `risk_scores` cascade in Postgres.

### `GET /api/health`

Reports database reachability, whether an LLM is configured, and the active
upload limit.

Errors on all non-upload endpoints use `{"status": "error", "detail": "..."}`.

---

## Frontend

| Route | Purpose |
|---|---|
| `/` | Landing page — what ClauseGuard does and what it is not |
| `/upload` | Drag-and-drop upload, client-side type/size validation, clause-type badges on the result |
| `/contracts` | All uploaded contracts with analysis status; delete with confirmation |
| `/contracts/[id]` | **The main screen.** Risk distribution, Analyze button, per-clause cards with type badge, collapsible text, risk level, plain-language summary, risk factors, and a "Consult a Lawyer" CTA on high-risk clauses |

Dark mode follows the OS setting, and the layout is responsive. The UPL
disclaimer renders in the root layout on every page and cannot be dismissed.

**Next.js 16 note:** `params` in dynamic routes is a `Promise` and must be
awaited — synchronous access was removed. See
`frontend/node_modules/next/dist/docs/01-app/02-guides/upgrading/version-16.md`.

---

## Backend module map

| File | Responsibility |
|---|---|
| `main.py` | FastAPI app, all HTTP endpoints, error handlers, PDF extraction and segmentation |
| `analysis_service.py` | Bridge: DB clauses → DSPy pipeline → `risk_scores` |
| `api_schemas.py` | Pydantic response models for the HTTP API |
| `schemas.py` | Pydantic models for the DSPy pipeline's own input/output |
| `models.py` | SQLAlchemy ORM (`contracts`, `parsed_clauses`, `risk_scores`) |
| `database.py` | Async engine, session factory, `init_db()` |
| `config.py` | Settings from `backend/.env` |
| `classifier.py` | Rule-based mock clause classifier (intentional placeholder) |
| `dspy_pipeline.py` | DSPy signature, module, LM configuration, batch processing |
| `optimizer.py` | BootstrapFewShot / MIPROv2 optimization workflows |
| `db_writer.py` | Upsert into `risk_scores` |
| `run_pipeline.py` | CLI runner (still useful for offline/mock runs) |
| `smoke_test.py` | End-to-end API check against a running backend |
| `mock_data.py` | Sample clauses for offline DSPy testing |
| `logger.py` | Structured logging under `clauseguard.*` |

### CLI (still supported)

```bash
python run_pipeline.py --mock                      # offline, no DB
python run_pipeline.py --db --contract-id <UUID> --save
python run_pipeline.py --mock --optimize           # BootstrapFewShot
```

---

## Implementation notes worth knowing

**`dspy.configure()` is single-owner.** DSPy only lets the thread that first
called `dspy.configure()` call it again. Calling `configure_lm()` per request
from FastAPI's rotating threadpool raises
`RuntimeError: dspy.settings can only be changed by the thread that initially
configured it` on the second request. `analysis_service._ensure_lm_configured()`
therefore calls it exactly once per process.

**The pipeline runs off the event loop.** `process_clauses()` is synchronous and
network-bound; it is dispatched with `anyio.to_thread.run_sync` so it does not
stall every other request. PDF parsing is offloaded the same way.

**Empty results mean total failure.** `process_clauses()` logs and skips clauses
that raise, so an empty result list from a non-empty input means every call
failed. That is surfaced as `502` rather than a misleading "0 clauses analyzed".

**Schema changes are additive only.** Existing columns are never renamed or
removed. `Base.metadata.create_all` does not add indexes to tables that already
exist, so `database.init_db()` also issues `CREATE INDEX IF NOT EXISTS`.

---

## Project documents

`PRD/` contains the product requirements, data model, acceptance criteria, user
stories and glossary. Only 3 of the 9 planned tables are implemented.

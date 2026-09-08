# ClauseGuard — AI-Powered Contract Clause Analyzer

ClauseGuard reads freelance service agreements clause by clause, explains each
one in plain English, flags the terms most likely to hurt the freelancer
signing them — and just as importantly, flags the protections the contract
**doesn't** contain.

> **This tool provides educational, pattern-based analysis only. It is NOT legal
> advice. Always consult a qualified attorney.**

---

## Current status

The product is **feature-complete and works end to end out of the box**. With
no API key it runs in offline demo mode (deterministic, clearly labeled canned
analysis); pasting a real `OPENAI_API_KEY` into `backend/.env` is the only step
needed to switch to real AI analysis.

| Capability | Status |
|---|---|
| PDF upload, extraction, layout-aware clause segmentation | ✅ |
| **Layer 1** — trained clause classifier (macro-F1 **0.929**, LEDGAR) with keyword fallback | ✅ |
| **Layer 2** — DSPy + LLM plain-language summaries and risk factors | ✅ |
| **Layer 3** — hybrid risk scoring (classifier confidence + LLM signals) | ✅ |
| Asynchronous analysis runs with live progress and content-hash caching | ✅ |
| Missing-protection findings (the PRD's five freelancer pain points) | ✅ |
| Contract-level executive summary + per-clause risk percentiles | ✅ |
| Authentication (Argon2 + httpOnly sessions) and per-user data isolation | ✅ |
| UPL safeguards: non-dismissable disclaimer, audit log, prescriptive-language filter, progressive disclosure, Consult-a-Lawyer CTA | ✅ |
| Evaluation dashboard (per-class F1, latency percentiles, compliance counters) | ✅ |
| Alembic migrations, CI (lint + 117 unit tests + migration drift check + image boot test), 63-check E2E smoke test | ✅ |
| Dockerfiles + full-stack compose, Railway config (`docs/DEPLOY.md`) | ✅ |
| Cloud deployment, OCR for scanned PDFs, Hebrew/RTL | ❌ future (see docs/ROADMAP.md) |

---

## Quick start (development)

```bash
# 1. Database
docker compose up -d

# 2. Backend  (Python 3.13)
cd backend
python -m venv venv && venv/Scripts/pip install -r requirements.txt   # once
python -m spacy download en_core_web_sm                               # once, ~12MB — optional*
venv/Scripts/python -m uvicorn main:app --port 8000

# 3. Frontend
cd frontend
npm install
npm run dev
```

Open <http://localhost:3000>, create an account, upload a PDF, press
**Analyze contract**.

\* Without the spaCy model the app still works — the classifier falls back to
keyword rules and `/api/health` reports `"mode": "mock"`.

**Verify everything:**

```bash
cd backend && venv/Scripts/python smoke_test.py
```

63 end-to-end checks: auth, upload, error paths, async analysis with progress
polling, caching, findings, percentiles, cross-user isolation, delete cascade.

### Full stack in Docker

```bash
docker compose -f docker-compose.full.yml up --build
```

---

## Turning on real AI analysis

Edit `backend/.env`:

```
OPENAI_API_KEY=sk-...your real key...
```

That's it — `DSPY_PROVIDER=auto` detects the key and switches from the
offline demo analyzer to `gpt-4o-mini` on the next backend restart. Every
generated summary passes a prescriptive-language filter before persistence,
and unchanged clauses are served from the content-hash cache on re-runs, so
re-analyzing a contract costs nothing.

---

## Architecture

```
   Browser (Next.js 16 / React 19 / TanStack Query / Tailwind 4)
     │      /api/* — same-origin rewrite; httpOnly session cookie
     ▼
   Next.js proxy ─────────────► FastAPI (backend/main.py)
                                  │
      upload ─► PyMuPDF ─► segmentation.py (blank lines → layout → regex)
                                  │
                        classifier.py  «Layer 1: sklearn, F1 0.929»
                                  │
                     contracts + parsed_clauses  (PostgreSQL 16)
                                  │
      analyze ─► analysis_runs row ─► asyncio task, semaphore(6)
                    │  per clause: dspy_pipeline «Layer 2» ─► upl.py filter
                    │              ─► scoring.py «Layer 3» ─► risk_scores
                    │  (content-hash cache skips unchanged clauses)
                    └─► pain_points.py findings + executive summary + percentiles
                                  │
      frontend polls the run ─► clause cards fill in live
```

- **Three-layer AI** (PRD §5.2): classical ML classification, programmatic
  LLM analysis, deterministic hybrid scoring — all live in the API.
- **Runs, not requests**: `POST /analyze` returns `202` with a run id;
  work executes in the background with per-clause persistence, retries, and
  crash recovery. `?wait=true` gives tests a blocking mode.
- **Demo provider**: `DSPY_PROVIDER=fake` (or `auto` with no key) runs a
  deterministic offline analyzer so every feature works with zero API cost.

## API surface

| Method | Path | Notes |
|---|---|---|
| `POST` | `/api/auth/register` / `login` / `logout`, `GET /api/auth/me` | Argon2 + httpOnly session cookie; rate-limited |
| `POST` | `/api/contracts/upload` | auth; stable Step-1 envelope, fields only ever added |
| `GET` | `/api/contracts` | auth; owner-scoped list with analysis status |
| `GET` | `/api/contracts/{id}` | auth; clauses + risk + findings + summary + latest run |
| `POST` | `/api/contracts/{id}/analyze` | auth; `202` + run; `?wait=true`, `?force=true` |
| `GET` | `/api/analysis-runs/{id}` | auth; progress polling |
| `DELETE` | `/api/contracts/{id}` | auth; cascades clauses/scores/runs/findings |
| `GET` | `/api/health` | open; DB, LLM mode, classifier status |
| `GET` | `/api/metrics` | auth; dashboard data |
| `POST` | `/api/disclaimer-views` | open, rate-limited; untrusted contract_id dropped |

Interactive docs: <http://127.0.0.1:8000/docs>.

## Frontend routes

| Route | Purpose |
|---|---|
| `/` | Landing |
| `/login`, `/signup` | Auth (protected routes redirect here) |
| `/upload` | Drag-and-drop upload with client-side validation |
| `/contracts` | Owner-scoped list with analysis status |
| `/contracts/[id]` | **The main screen** — live-progress analysis, risk overview, executive summary, missing-protection findings, progressive-disclosure clause cards |
| `/dashboard` | Evaluation dashboard: per-class F1, run latency, compliance |

## Backend module map

| File | Responsibility |
|---|---|
| `main.py` | FastAPI app, endpoints, error envelopes, middleware |
| `auth.py` | Argon2 hashing, cookie sessions, rate limiting |
| `analysis_service.py` | Analysis runs: scheduling, concurrency, caching, recovery |
| `segmentation.py` | Clause splitting: blank-line / layout / regex strategies |
| `classifier.py` | Layer 1: trained pipeline with keyword fallback |
| `dspy_pipeline.py` | Layer 2: DSPy signature/module, LM configuration |
| `scoring.py` | Layer 3: hybrid risk blend (pure module) |
| `pain_points.py` | Missing-protection checklist (PRD's five pain points) |
| `contract_summary.py` | Executive-summary signature + demo fallback |
| `upl.py` | Prescriptive-language filter (AC-P02) |
| `fake_llm.py` | Deterministic offline analyzer (demo mode / CI) |
| `db_writer.py`, `models.py`, `database.py`, `config.py` | Persistence + settings |
| `alembic/` | Migrations (startup runs `upgrade head`; pre-Alembic DBs are stamped) |
| `ml_training/` | Isolated training sandbox for the classifier artifact |
| `smoke_test.py` | 63-check end-to-end verification |

## Implementation notes worth knowing

- **`dspy.configure()` is single-owner** — only the first thread that calls it
  may call it again; it happens exactly once per process.
- **numpy must import before dspy/litellm** — otherwise a later spaCy import
  re-executes numpy's init and predict crashes ("data type 'bool' not
  understood"). Pinned at the top of `main.py`/`classifier.py`.
- **The classifier artifact was trained on Python 3.11 / sklearn 1.5.2** and
  runs here on 3.13 / newer sklearn: loading is validated with a smoke
  prediction and falls back to keyword rules on any failure.
- **Windows + pip**: `litellm>=1.97` matters — earlier versions break on
  MAX_PATH. If installs fail mysteriously, see the note in `requirements.txt`.
- **Schema changes are additive only** and go through Alembic; startup
  detects pre-Alembic databases and stamps the baseline.

## Project documents

- `docs/STATUS.md` — **start here**: what exists today, what remains, how
  to verify, and the housekeeping that has been done.
- `docs/ROADMAP.md` — the technical review this build executed, plus what's
  deliberately deferred (deployment, OCR, Hebrew/RTL, DSPy optimizer upgrade).
- `PRD/` — product requirements, data model, acceptance criteria.

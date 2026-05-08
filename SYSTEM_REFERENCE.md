# SYSTEM_REFERENCE.md

> Authoritative context for AI coding agents working in the ClauseGuard repository.
> Sourced exclusively from files present in the repo. Do not infer beyond what is documented here.

---

## Section 1 — System Identity & Purpose

ClauseGuard is an AI-powered contract clause analyzer for freelance service agreements. A user uploads a PDF; the FastAPI backend extracts text with PyMuPDF, segments it into clauses, classifies each clause with a rule-based mock classifier (`backend/classifier.py`), persists `Contract` and `ParsedClause` rows in PostgreSQL, and returns a strict JSON handoff. A separate DSPy pipeline (`backend/dspy_pipeline.py`, `backend/run_pipeline.py`) consumes those rows to produce per-clause `plain_language_summary`, `risk_factors`, `dspy_risk_score`, and a categorical `risk_level` written to the `risk_scores` table. The Next.js frontend (`frontend/`) renders only `parsed_clauses` from the upload response.

**Primary outputs:**
- HTTP response: `POST /api/contracts/upload` returns the success/error envelope defined in [README.md](README.md#strict-api-contract-must-preserve).
- DB rows: `contracts`, `parsed_clauses`, `risk_scores` (PostgreSQL).
- Optimized DSPy program artifact: `backend/optimized_pipeline.json` (written by `optimizer.py`).
- CLI stdout summary from [backend/run_pipeline.py](backend/run_pipeline.py).

**Persistent state model:** PostgreSQL via async SQLAlchemy. Tables are created at FastAPI startup via `Base.metadata.create_all` ([backend/main.py:25-26](backend/main.py#L25-L26)). No Alembic migrations are configured. The DSPy writer ([backend/db_writer.py](backend/db_writer.py)) uses PostgreSQL `INSERT ... ON CONFLICT DO UPDATE` keyed by `parsed_clause_id` — direct overwrites of pre-existing rows are forbidden because each clause has at most **one** `risk_scores` row (UNIQUE constraint on `parsed_clause_id`); concurrent writers must use UPSERT semantics, never raw INSERT.

**Persistent state files / tables:**
- `contracts` table — uploaded contract metadata (id, original_filename, created_at).
- `parsed_clauses` table — per-clause text, ML-predicted type, confidence, FK to contracts.
- `risk_scores` table — DSPy-derived risk_level, risk_score, risk_factors (JSONB), plain_language_summary, dspy_program_version.
- `backend/optimized_pipeline.json` — compiled DSPy program (BootstrapFewShot or MIPROv2 output).
- `backend/.env` — local secrets (`DATABASE_URL`, `OPENAI_API_KEY`); **gitignored**.
- `backend/.env.example` — committed template.
- Postgres data volume `pg_data` — managed by docker-compose ([docker-compose.yml](docker-compose.yml)).

**Agent-facing invariant files:**
- [README.md](README.md) — strict API contract for `POST /api/contracts/upload`.
- [frontend/AGENTS.md](frontend/AGENTS.md) — explicit warning that this is **not** the Next.js you know; consult `node_modules/next/dist/docs/` before writing frontend code.
- [frontend/CLAUDE.md](frontend/CLAUDE.md) — re-exports `AGENTS.md`.
- [docs/snapshots/snapshot_2026-04-26.md](docs/snapshots/snapshot_2026-04-26.md) — Phase 1 architecture snapshot.

---

## Section 2 — Repository Topology

```
ClauseGuard/
├── README.md                    # Strict API contract + run instructions
├── docker-compose.yml           # Postgres 16 Alpine, port 5432
├── .gitignore                   # Protects .env (allows .env.example)
├── PRD/                         # Product requirements
│   ├── PRD.md
│   ├── DataModel.md             # Full target PostgreSQL schema
│   ├── UserStories.md
│   ├── Glossary.md
│   └── AcceptanceCriteria.md
├── docs/
│   ├── raw/step1_developer1_2026-04-27/   # Session transcripts (Step 1)
│   └── snapshots/                          # Architecture snapshots
│       ├── snapshot_2026-03-19.md         # Phase 0 baseline
│       └── snapshot_2026-04-26.md         # Phase 1 (DB + Mock ML)
├── backend/                     # FastAPI app + DSPy pipeline
│   ├── main.py                  # POST /api/contracts/upload
│   ├── classifier.py            # mock_classify() — Layer 1 stand-in
│   ├── config.py                # Pydantic Settings (DATABASE_URL)
│   ├── database.py              # async engine, session factory, Base
│   ├── models.py                # Contract, ParsedClause, RiskScore ORM
│   ├── schemas.py               # ClauseInput, ClauseAnalysisResult (Pydantic)
│   ├── dspy_pipeline.py         # ContractClauseAnalysisV2 + ClauseAnalyzerV2
│   ├── optimizer.py             # BootstrapFewShot, MIPROv2, TRAIN_DATA
│   ├── db_writer.py             # save_results_to_db() — UPSERT to risk_scores
│   ├── mock_data.py             # get_mock_clauses() — offline fixtures
│   ├── run_pipeline.py          # CLI: --mock | --db | --optimize | --save
│   ├── logger.py                # get_logger(), RunStats
│   ├── requirements.txt
│   ├── .env / .env.example
│   └── README.md
└── frontend/                    # Next.js 16.2 (App Router) + Tailwind v4
    ├── AGENTS.md                # MANDATORY agent guidance
    ├── CLAUDE.md                # Re-exports AGENTS.md
    ├── package.json             # next 16.2.0, react 19.2.4
    ├── next.config.ts
    ├── tsconfig.json
    └── src/
        ├── app/
        │   ├── layout.tsx       # RootLayout (Geist fonts)
        │   ├── page.tsx         # Home → UploadDropzone
        │   └── globals.css
        ├── components/
        │   ├── UploadDropzone.tsx
        │   └── ClauseList.tsx
        ├── lib/api.ts           # uploadContractFile()
        └── types/contracts.ts   # ParsedClause, UploadResponse
```

| Path | Type | Agent Action | Notes |
|------|------|--------------|-------|
| [README.md](README.md) | Contract | Read before any backend edit | Defines `POST /api/contracts/upload` envelope |
| [frontend/AGENTS.md](frontend/AGENTS.md) | Invariant | Read before any frontend edit | "NOT the Next.js you know" — read `node_modules/next/dist/docs/` |
| [docker-compose.yml](docker-compose.yml) | Infra | Run `docker compose up -d` to start Postgres | User/pass/db all `clauseguard`, port 5432 |
| [backend/main.py](backend/main.py) | Source (entry) | Modify upload endpoint here | Lifespan auto-creates tables |
| [backend/classifier.py](backend/classifier.py) | Source (Layer 1 mock) | Replace with real spaCy+sklearn | Owner: Developer 1 only |
| [backend/dspy_pipeline.py](backend/dspy_pipeline.py) | Source (Layer 2) | Modify DSPy signature/module here | Owner: Developer 2 only |
| [backend/optimizer.py](backend/optimizer.py) | Source | Run optimizers; do not edit metric without review | Writes `optimized_pipeline.json` |
| [backend/db_writer.py](backend/db_writer.py) | Source | Persist DSPy results | UPSERT only (ON CONFLICT DO UPDATE) |
| [backend/schemas.py](backend/schemas.py) | Contract | Pydantic types Dev1↔Dev2 boundary | Decoupled from ORM |
| [backend/models.py](backend/models.py) | Contract | SQLAlchemy ORM | Authoritative table definitions |
| [backend/.env](backend/.env) | Secret | NEVER commit | `.gitignore` excludes it |
| [backend/.env.example](backend/.env.example) | Template | Safe to commit | Has `DATABASE_URL` and `OPENAI_API_KEY` placeholders |
| [PRD/DataModel.md](PRD/DataModel.md) | Spec | Reference for target schema | Some tables (users, annotations, runs) are unimplemented |
| [docs/snapshots/](docs/snapshots/) | Audit trail | Append-only architecture snapshots | One file per phase |
| [docs/raw/](docs/raw/) | Audit trail | Session transcripts | Append-only |
| [frontend/src/lib/api.ts](frontend/src/lib/api.ts) | Source | Modify API client here | Reads `NEXT_PUBLIC_API_BASE_URL` |
| [frontend/src/types/contracts.ts](frontend/src/types/contracts.ts) | Contract | Frontend response type | Currently strips DB UUID fields |

**Filename / naming patterns (verbatim from source):**
- Snapshots: `snapshot_YYYY-MM-DD.md` (e.g., `snapshot_2026-04-26.md`).
- Raw session dirs: `step{N}_developer{N}_YYYY-MM-DD/` (e.g., `step1_developer1_2026-04-27/`).
- DSPy compiled artifact: exactly `backend/optimized_pipeline.json` ([optimizer.py:21](backend/optimizer.py#L21)).
- Postgres connection: `postgresql+asyncpg://clauseguard:clauseguard@localhost:5432/clauseguard` ([config.py:17](backend/config.py#L17)).

**Derived ID / slug formats:**
- `contract_id`: UUID v4 generated by `uuid.uuid4` in `Contract.id` default — example: `bdab9a61-9b70-4f27-97ce-bc600d892442`.
- `parsed_clause_id`: UUID v4 from `ParsedClause.id` default — example: `fe3ba60d-e201-4a6a-ab7a-489c130d3656`.
- `clause_index`: 1-based, monotonic INTEGER per contract — example: `1, 2, 3, ...`.
- `clause_type`: lowercase snake-case literal from the fixed set listed in Section 6.

---

## Section 3 — Module / Skill Matrix

This repo has no formal "skill" system; the matrix below covers the major code modules.

| Module/Skill Name | Invocation | Primary Input | Primary Outputs | State Written | Forbidden Actions |
|---|---|---|---|---|---|
| `upload_contract` ([main.py:103](backend/main.py#L103)) | HTTP `POST /api/contracts/upload` (multipart, field `file`) | UploadFile (PDF) | JSON envelope `{status, filename, contract_id, parsed_clauses[]}` | INSERT `contracts`, INSERT `parsed_clauses` | Changing top-level envelope keys; omitting `parsed_clauses` on error |
| `mock_classify` ([classifier.py:11](backend/classifier.py#L11)) | `from classifier import mock_classify; mock_classify(text)` | `raw_text: str` | `(clause_type: str, confidence: float)` | None | Adding clause types outside the fixed 8 (see Section 6) |
| `ClauseAnalyzerV2` ([dspy_pipeline.py:81](backend/dspy_pipeline.py#L81)) | `analyzer = ClauseAnalyzerV2(); analyzer(raw_text=..., clause_type=...)` | `raw_text`, `clause_type` | `dspy.Prediction` with `plain_language_summary`, `risk_factors`, `dspy_risk_score` | None (in-memory) | Editing the docstring of `ContractClauseAnalysisV2` casually — DSPy uses it as the prompt |
| `process_clauses` ([dspy_pipeline.py:171](backend/dspy_pipeline.py#L171)) | `process_clauses(clauses, analyzer=...)` | `list[ClauseInput]` | `list[ClauseAnalysisResult]` | None (in-memory) | Bypassing `_parse_risk_score` clamp `[0.0, 1.0]` |
| `configure_lm` ([dspy_pipeline.py:99](backend/dspy_pipeline.py#L99)) | `configure_lm(provider="openai", model="gpt-4o-mini")` | provider, model, optional api_key/base_url | Sets global `dspy.LM` | Process-global state | Calling without `OPENAI_API_KEY` set when provider="openai" |
| `save_results_to_db` ([db_writer.py:20](backend/db_writer.py#L20)) | `await save_results_to_db(results)` | `list[ClauseAnalysisResult]` | `int` (rows saved) | UPSERT `risk_scores` | Plain INSERT — must use `on_conflict_do_update` keyed on `parsed_clause_id` |
| `run_bootstrap_fewshot` ([optimizer.py:118](backend/optimizer.py#L118)) | `run_bootstrap_fewshot()` | `TRAIN_DATA` (5 examples) | Compiled `dspy.Module` | Writes `backend/optimized_pipeline.json` | Running without an LM configured |
| `run_miprov2` ([optimizer.py:142](backend/optimizer.py#L142)) | `run_miprov2()` | `TRAIN_DATA` | Compiled `dspy.Module` | Overwrites `backend/optimized_pipeline.json` | Removing `requires_permission_to_run=False` (will hang on prompt) |
| `load_optimized_analyzer` ([optimizer.py:170](backend/optimizer.py#L170)) | `load_optimized_analyzer()` | `optimized_pipeline.json` if present | `dspy.Module` (optimized or fresh) | None | Failing silently if load throws — currently logs warning and returns fresh |
| `quality_metric` ([optimizer.py:75](backend/optimizer.py#L75)) | Used by `BootstrapFewShot`/`MIPROv2` `metric=` | `dspy.Example`, `dspy.Prediction` | `float` in `[0.0, 1.0]` | None | Returning >1.0 or <0.0 |
| `run_pipeline` CLI ([run_pipeline.py:215](backend/run_pipeline.py#L215)) | `python run_pipeline.py --mock --save` | argparse flags | stdout report; optional DB writes | `risk_scores` if `--save`; `optimized_pipeline.json` if `--optimize*` | Running `--db` without `--contract-id` filter on a populated DB without intent |
| `get_db` ([database.py:46](backend/database.py#L46)) | `db: AsyncSession = Depends(get_db)` | none | Yielded `AsyncSession` | Depends on caller | Using outside FastAPI request lifecycle (use `async_session_factory` directly instead) |
| `UploadDropzone` ([UploadDropzone.tsx:14](frontend/src/components/UploadDropzone.tsx#L14)) | Rendered by `app/page.tsx` | User-selected `File` | UI state + `ClauseList` render | None | Sending non-PDF without client-side rejection |
| `uploadContractFile` ([api.ts:6](frontend/src/lib/api.ts#L6)) | `await uploadContractFile(file)` | `File` | `UploadResponse` | None | Hardcoding the API URL — must respect `NEXT_PUBLIC_API_BASE_URL` |

**Variant behaviors to highlight:**
- `--mock` (offline) vs `--db` (live): `--mock` calls `get_mock_clauses()` ([mock_data.py](backend/mock_data.py)); `--db` calls `_fetch_clauses_from_db(args.contract_id)` ([run_pipeline.py:141](backend/run_pipeline.py#L141)).
- BootstrapFewShot vs MIPROv2: BFS = ~5–10 LLM calls, fast; MIPROv2 = ~50+ calls, generates dynamic instructions ([optimizer.py:118-167](backend/optimizer.py#L118-L167)).
- `--save` is **off by default**; persistence is opt-in ([run_pipeline.py:204](backend/run_pipeline.py#L204)).

**Concrete invocations:**
- Upload: `curl -X POST http://127.0.0.1:8000/api/contracts/upload -F "file=@./contract.pdf"`
- Mock + optimize + persist: `python run_pipeline.py --mock --optimize --save`
- DB run for a single contract: `python run_pipeline.py --db --contract-id <UUID> --save`

---

## Section 4 — State Architecture & Mutation Rules

**Canonical cycle (DSPy persistence path):**
1. **Read** — `_fetch_clauses_from_db()` selects from `parsed_clauses` ordered by `(contract_id, clause_index)`.
2. **Validate** — Pydantic `ClauseInput` enforces UUID types and required fields ([schemas.py:19](backend/schemas.py#L19)).
3. **Mutate** — `process_clauses()` produces `ClauseAnalysisResult` objects (no DB writes).
4. **Write** — `save_results_to_db()` issues `INSERT ... ON CONFLICT (parsed_clause_id) DO UPDATE` against `risk_scores`, then `await session.commit()`.

**Canonical cycle (upload path):**
1. **Validate** — `_is_pdf_upload()` checks content-type/extension.
2. **Parse** — PyMuPDF (`fitz.open`) extracts text per page.
3. **Segment** — `re.split(r"\n\s*\n", full_text)` (naive blank-line split).
4. **Classify** — `mock_classify(cleaned)` per non-empty segment.
5. **Persist** — `db.add(Contract)` → `db.flush()` → `db.add(ParsedClause)` per clause → `db.commit()`.
6. **Respond** — Build the JSON handoff.

### State entries

#### `contracts`
- **Schema location:** [backend/models.py:28-49](backend/models.py#L28-L49) (target spec: [PRD/DataModel.md §2.2](PRD/DataModel.md)).
- **Primary writer:** `upload_contract` in `main.py`.
- **Append-only fields:** `id`, `created_at`, `original_filename` (no UPDATE path exists in current code).
- **Mutable fields:** None implemented.
- **Hard prohibition:** No `user_id` column exists yet (deferred to Step 3 per [snapshot_2026-04-26.md](docs/snapshots/snapshot_2026-04-26.md)). Do not add until Step 3.

#### `parsed_clauses`
- **Schema location:** [backend/models.py:52-84](backend/models.py#L52-L84).
- **Primary writer:** `upload_contract`.
- **Append-only fields:** `id`, `contract_id`, `clause_index`, `raw_text`, `created_at`.
- **Mutable fields:** `clause_type`, `clause_type_confidence` (re-running the classifier is permitted by code shape, but no current code path updates these).
- **Hard prohibition:** `clause_index` must remain 1-based and monotonic per `contract_id`. ON DELETE CASCADE from `contracts`.

#### `risk_scores`
- **Schema location:** [backend/models.py:87-115](backend/models.py#L87-L115).
- **Primary writer:** `save_results_to_db` ([db_writer.py](backend/db_writer.py)).
- **Append-only fields:** `id`, `parsed_clause_id`, `created_at`.
- **Mutable fields (via UPSERT):** `risk_level`, `risk_score`, `risk_factors`, `plain_language_summary`, `dspy_program_version`.
- **Hard prohibition:** `parsed_clause_id` is UNIQUE. Two `risk_scores` rows for the same clause are forbidden. Always use `insert().on_conflict_do_update(index_elements=["parsed_clause_id"], ...)`.

#### `optimized_pipeline.json`
- **Schema location:** Format owned by DSPy (`dspy.Module.save`/`load`). Do not hand-edit.
- **Primary writer:** `run_bootstrap_fewshot` and `run_miprov2`.
- **Append-only fields:** None — file is wholesale overwritten on each successful optimization run.
- **Mutable fields:** Whole file.
- **Hard prohibition:** Do not commit this artifact unless an explicit version-pinning workflow is introduced; it is a build output of an LLM call.

#### `docs/snapshots/snapshot_*.md`
- **Schema location:** Free-form markdown; pattern: `snapshot_YYYY-MM-DD.md`.
- **Primary writer:** Human / AI agent at end of phase.
- **Append-only:** Yes — never overwrite a prior snapshot; create a new dated file.

**Cross-module symmetry:**
- `ClauseInput.clause_type` and `ClauseAnalysisResult.clause_type` must echo verbatim ([dspy_pipeline.py:201](backend/dspy_pipeline.py#L201)).
- `ClauseAnalysisResult.dspy_risk_score` (float, clamped `[0.0, 1.0]`) maps to `risk_scores.risk_score` (Numeric(5,4)).
- `ClauseAnalysisResult.risk_level` is derived from `dspy_risk_score` by `_score_to_level()`: `<0.4 → "low"`, `<0.7 → "medium"`, else `"high"` ([dspy_pipeline.py:162-168](backend/dspy_pipeline.py#L162-L168)).

**Audit trail mechanism:** Architecture snapshots in `docs/snapshots/` and per-step session transcripts under `docs/raw/stepN_developerN_YYYY-MM-DD/`. Each new phase commit is paired with a new snapshot file. `dspy_program_version` in `risk_scores` records the DSPy library version at write time.

⚠️ INVARIANT: `parsed_clauses[].clause_index` is 1-based and monotonic per contract. Violation = frontend rendering bug + clause-ordering regression.
⚠️ INVARIANT: `risk_scores` writes use `INSERT ... ON CONFLICT (parsed_clause_id) DO UPDATE`. Violation = `IntegrityError` on re-run, lost results.
⚠️ INVARIANT: The `POST /api/contracts/upload` envelope keys (`status`, `filename`, `contract_id`, `parsed_clauses[]`, optional `detail`) must not change. Violation = breaks the frontend client and the strict contract in [README.md](README.md).
⚠️ INVARIANT: `dspy_risk_score` ∈ `[0.0, 1.0]`, enforced by `_parse_risk_score` clamp. Violation = downstream `_score_to_level` mis-bucketing and DB constraint risk on Numeric(5,4).
⚠️ INVARIANT: Developer 2 (DSPy) must not edit `backend/classifier.py`; Developer 1 (Full-Stack & ML) must not edit `backend/dspy_pipeline.py` ([snapshot_2026-04-26.md §4.2](docs/snapshots/snapshot_2026-04-26.md)). Violation = role boundary breach + merge conflict risk.
⚠️ INVARIANT: `backend/.env` must never be committed. Violation = secret leak (the file is gitignored — keep it that way).
⚠️ INVARIANT: New architecture snapshots are append-only (`snapshot_YYYY-MM-DD.md`); never overwrite older snapshots. Violation = loss of phase history.

---

## Section 5 — Pipeline / Execution Stages

**Primary HTTP pipeline (`POST /api/contracts/upload`, [main.py:103-209](backend/main.py#L103-L209)):**
1. **Validate upload** — `_is_pdf_upload(file)` checks `content_type == "application/pdf"` or filename ends with `.pdf`. On fail → 400 with envelope.
2. **Read bytes** — `await file.read()`. Empty body → 400.
3. **Open PDF** — `fitz.open(stream=raw_bytes, filetype="pdf")`. Failure throws → caught, returns 400 "Failed to parse PDF.".
4. **Extract text** — Iterate pages, collect non-empty `page.get_text("text")`, join with `"\n\n"`. Empty extraction → 400 "Could not extract text from PDF.".
5. **Segment** — `re.split(r"\n\s*\n", full_text)` (naive). Per [README.md](README.md), this is the line targeted for replacement by spaCy-based segmentation.
6. **Classify** — Per non-empty segment, call `mock_classify` and append `{clause_index, raw_text, clause_type, clause_type_confidence}` (1-based index).
7. **Persist** — `db.add(Contract(original_filename=filename))` → `await db.flush()` (populates `contract.id`) → loop `db.add(ParsedClause(...))` → `await db.commit()`.
8. **Emit handoff JSON** — Build response with `parsed_clause_id`, `contract_id`, `clause_index`, `raw_text`, `clause_type`, `clause_type_confidence`.

**DSPy pipeline ([run_pipeline.py:81-122](backend/run_pipeline.py#L81-L122)):**
1. **`configure_lm(provider, model)`** — Sets `dspy.configure(lm=...)`.
2. **Optimization phase** — One of: `run_miprov2()`, `run_bootstrap_fewshot()`, or `load_optimized_analyzer()` (default).
3. **Source clauses** — `--mock` → `get_mock_clauses()`; `--db` → `_fetch_clauses_from_db(contract_id)`.
4. **`process_clauses(clauses, analyzer=...)`** — Per clause: run analyzer, parse `dspy_risk_score` via regex, parse `risk_factors` (comma- or newline-split), derive `risk_level`.
5. **Print** — `_print_result` per clause, then `_print_summary` table.
6. **Persist (optional)** — If `--save`: `asyncio.run(save_results_to_db(results))` UPSERTs into `risk_scores`.

**Quality gates (must pass before write/emit):**
- Upload: PDF type check, non-empty bytes, non-empty extracted text, at least one non-empty segment.
- DSPy: `_parse_risk_score` clamp; `_parse_risk_factors` returns `[]` for `"none"/"n/a"/"null"` so empty lists serialize cleanly to JSONB.
- Optimizer `quality_metric`: returns scalar in `[0.0, 1.0]` (sum of three sub-scores capped by their individual maxima of 0.4 + 0.3 + 0.3).

**Dry-run / preview mode:** `python run_pipeline.py --mock` (no `--save`) prints results to stdout without touching DB. `--db` without `--save` reads but does not write. There is no preview mode for the upload endpoint — it always writes on success.

---

## Section 6 — Input Contracts

**HTTP upload input ([main.py:103-114](backend/main.py#L103-L114)):**
- Method: `POST /api/contracts/upload`
- Content-Type: `multipart/form-data`
- Field: `file` (exact name) — PDF binary
- Validation: content-type `application/pdf` OR filename ending `.pdf` (case-insensitive)
- Max size: **not enforced in code** ([snapshot_2026-04-26.md §5.1](docs/snapshots/snapshot_2026-04-26.md)); PRD target is 10MB.

**DSPy pipeline input — `ClauseInput` ([schemas.py:19-46](backend/schemas.py#L19-L46)):**
```json
{
  "parsed_clause_id": "11111111-0000-0000-0000-000000000001",
  "contract_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "raw_text": "All intellectual property... assigned to the Client.",
  "clause_type": "ip_assignment"
}
```

**Allowed `clause_type` values (verbatim from [classifier.py](backend/classifier.py) and [dspy_pipeline.py:46-50](backend/dspy_pipeline.py#L46-L50)):**
`ip_assignment`, `payment_terms`, `termination`, `liability`, `confidentiality`, `scope_of_work`, `governing_law`, `general`.

**Optional / supplementary inputs:**
- `--contract-id <UUID>` filter for `--db` mode ([run_pipeline.py:202](backend/run_pipeline.py#L202)).
- Provider override: `--provider openai|ollama` ([run_pipeline.py:209](backend/run_pipeline.py#L209)).
- Model override: `--model <name>` (default `gpt-4o-mini`).

**Error handling on malformed input:**
- Non-PDF / missing file → `400` with `_error_envelope` containing `detail: "Invalid file type. PDF required."`.
- Empty body → `400` `"Empty file."`.
- Unparseable PDF → `400` `"Failed to parse PDF."`.
- Empty extracted text → `400` `"Could not extract text from PDF."`.
- DSPy LLM error per clause → logged; that clause is omitted from the result list ([dspy_pipeline.py:209-210](backend/dspy_pipeline.py#L209-L210)). The pipeline does not abort the whole run.
- `--db` mode with zero clauses → `sys.exit(0)` after warning ([run_pipeline.py:158](backend/run_pipeline.py#L158)).

**External resource access policy:**
- LLM calls: per-clause via DSPy. There is no rate limiter or concurrency cap in code. The optimizer auto-mode `"light"` runs ~50–60 trials ([optimizer.py:153](backend/optimizer.py#L153)).
- DB: single async engine, connection pool default. No retry policy.
- No web/HTTP fetches outside the LLM call path.

---

## Section 7 — Output Contracts

### 7.1 HTTP `POST /api/contracts/upload` — success (200)

```json
{
  "status": "success",
  "filename": "msa.pdf",
  "contract_id": "bdab9a61-9b70-4f27-97ce-bc600d892442",
  "parsed_clauses": [
    {
      "parsed_clause_id": "fe3ba60d-e201-4a6a-ab7a-489c130d3656",
      "contract_id": "bdab9a61-9b70-4f27-97ce-bc600d892442",
      "clause_index": 1,
      "raw_text": "This Agreement starts on the Effective Date...",
      "clause_type": "general",
      "clause_type_confidence": 0.50
    }
  ]
}
```

### 7.2 HTTP `POST /api/contracts/upload` — error (4xx)

```json
{
  "status": "error",
  "filename": "uploaded.mp4",
  "contract_id": null,
  "parsed_clauses": [],
  "detail": "Invalid file type. PDF required."
}
```

**Mandatory keys (always present):** `status`, `filename`, `contract_id` (or `null`), `parsed_clauses` (`[]` on error). `detail` is present only on error. Source: [main.py:43-56](backend/main.py#L43-L56), [main.py:186-202](backend/main.py#L186-L202).

**Validation gates before emit:** PDF parse must succeed; at least one non-empty segment; `db.commit()` must succeed (otherwise the broad `except Exception` handler returns `400 "Failed to parse PDF."`).

### 7.3 DSPy result — `ClauseAnalysisResult` ([schemas.py:49-91](backend/schemas.py#L49-L91))

```json
{
  "parsed_clause_id": "11111111-0000-0000-0000-000000000001",
  "contract_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "clause_type": "ip_assignment",
  "plain_language_summary": "You keep the rights to your pre-existing tools...",
  "risk_factors": ["No pre-existing IP carve-out", "Uncapped liability"],
  "dspy_risk_score": 0.25,
  "risk_level": "low"
}
```

### 7.4 `risk_scores` row write contract ([db_writer.py:45-64](backend/db_writer.py#L45-L64))

| Column | Source | Note |
|---|---|---|
| `parsed_clause_id` | input | UNIQUE; conflict key |
| `risk_level` | `result.risk_level` | One of `"low" | "medium" | "high"` |
| `risk_score` | `result.dspy_risk_score` | Numeric(5,4), `[0.0, 1.0]` |
| `risk_factors` | `result.risk_factors` | JSONB array of strings |
| `plain_language_summary` | `result.plain_language_summary` | TEXT |
| `dspy_program_version` | `dspy.__version__` | VARCHAR(128) |

### 7.5 Markdown outputs (snapshots / walkthroughs)

- File names: `snapshot_YYYY-MM-DD.md`, `walkthrough.md`, `implementation_plan.md`.
- Hierarchy in existing snapshots: `# Title` → numbered `## Section` (1) Title + Metadata, (2) System Architecture View, (3) Current Phase Status, (4) Core Achievements, (5) API Contracts & DB Schema, (6) ML & AI Pipeline State, (7) UPL Compliance Audit, (8) Observability & Maintenance.
- Tables use GitHub-flavored markdown. Code fences use ```powershell``` / ```json``` / ```diff:filename```.
- No math formatting conventions are present in the repo. [NOT FOUND IN REPO — VERIFY] for math styling.

### 7.6 Append-only fields (must not be deleted or overwritten)

- `docs/snapshots/snapshot_*.md` — once committed, never overwrite; add a new dated file.
- `docs/raw/stepN_developerN_YYYY-MM-DD/` — session transcripts; new directory per step/developer.
- `risk_scores.id`, `risk_scores.parsed_clause_id`, `risk_scores.created_at` — set once at insert; only the value-bearing columns are updated on conflict.

---

## Section 8 — Disambiguation & Anti-Hallucination Rules

1. **Do not invent envelope fields.** [README.md](README.md) and [main.py:186-202](backend/main.py#L186-L202) define the exact response shape. Adding `errors[]`, `meta`, or `version` to the top level breaks the contract. Correct: extend `parsed_clauses[]` items only, and only with explicit cross-developer agreement.

2. **`status` is exactly `"success"` or `"error"`.** Not `"ok"`, `"failed"`, `"partial"`. Source: [README.md §Schema Rules](README.md), [main.py:50-56](backend/main.py#L50-L56).

3. **`clause_type` is restricted to 8 values.** Listed in Section 6. Adding a new category requires updating both `classifier.py` rules **and** the description in `dspy_pipeline.py:46-50` (the DSPy InputField description is part of the prompt).

4. **`clause_index` is 1-based.** Not 0-based. Source: [main.py:153](backend/main.py#L153), [README.md §Schema Rules](README.md), [PRD/DataModel.md §2.3](PRD/DataModel.md).

5. **Do not write to `risk_scores` with plain INSERT.** Use the UPSERT pattern in [db_writer.py:45-64](backend/db_writer.py#L45-L64). The `parsed_clause_id` UNIQUE constraint ([models.py:98](backend/models.py#L98)) will raise `IntegrityError` otherwise.

6. **Do not edit `backend/classifier.py` if you are operating as Developer 2 (DSPy).** Source: [classifier.py:5-6](backend/classifier.py#L5-L6) explicit comment: "Developer 2 (DSPy) does NOT touch this function — they only consume the classified records from the database." Conversely, Developer 1 should not edit `dspy_pipeline.py` / `optimizer.py` / `db_writer.py` without coordination.

7. **Do not delete the docstring of `ContractClauseAnalysisV2`.** DSPy uses the class docstring and `desc=` fields as the prompt. Casual edits silently change LLM behavior. Source: [dspy_pipeline.py:29-74](backend/dspy_pipeline.py#L29-L74).

8. **Do not assume `users`, `clause_annotations`, `analysis_runs`, `disclaimer_logs`, or `ml_model_versions` tables exist.** [PRD/DataModel.md](PRD/DataModel.md) describes the **target** schema. Currently only `contracts`, `parsed_clauses`, `risk_scores` are implemented in [models.py](backend/models.py). Treat references in PRD as forward-looking until merged into `models.py`.

9. **Do not assume there is a real ML classifier.** `mock_classify` is a keyword-rule stub. Source: [classifier.py:1-7](backend/classifier.py#L1-L7). It returns `("general", 0.50)` on no match and is English-only.

10. **Do not assume the frontend type covers all backend response fields.** [frontend/src/types/contracts.ts](frontend/src/types/contracts.ts) only declares `clause_index` and `raw_text` on `ParsedClause`. The backend now also returns `parsed_clause_id`, `contract_id`, `clause_type`, `clause_type_confidence` ([snapshot_2026-04-26.md §5.1](docs/snapshots/snapshot_2026-04-26.md)). Adding fields requires updating this type explicitly.

11. **Do not write Next.js code from training-data conventions.** [frontend/AGENTS.md](frontend/AGENTS.md): "This is NOT the Next.js you know... Read the relevant guide in `node_modules/next/dist/docs/` before writing any code." `package.json` pins `next@16.2.0`, `react@19.2.4`. Verify APIs against the installed version, not memory.

12. **Do not commit `backend/.env` or `optimized_pipeline.json`.** `.env` is gitignored. `optimized_pipeline.json` is a generated artifact; treat as a build output unless an explicit pinning workflow is introduced.

13. **Do not call DSPy without `OPENAI_API_KEY`.** `configure_lm("openai", ...)` raises `EnvironmentError` if missing ([dspy_pipeline.py:107-110](backend/dspy_pipeline.py#L107-L110)). For offline development use `--mock` and a real key, OR `--provider ollama --model <local-model>`.

14. **Do not produce prescriptive legal language.** Per [PRD/PRD.md §5.4 UPL Safety](PRD/PRD.md) and [PRD/AcceptanceCriteria.md §1.6](PRD/AcceptanceCriteria.md): the system is informational only. Outputs use "commonly associated with", "typically includes", "pattern flagged" — never "you should", "we recommend", "we advise". DSPy outputs feed user-visible UI eventually; preserve this framing in any prompt or summary edits.

15. **`risk_factors` for "none" inputs returns `[]`, not `["None"]`.** Source: [dspy_pipeline.py:135-137](backend/dspy_pipeline.py#L135-L137). Don't store the literal string "None" in JSONB.

### When Uncertain, Do This

- **Halt and surface the ambiguity.** Cite the specific file path and line that creates the uncertainty.
- **Cross-check schemas at the Pydantic ↔ ORM ↔ HTTP boundary.** A field present in only two of the three is the source of most bugs ([schemas.py](backend/schemas.py) ↔ [models.py](backend/models.py) ↔ [main.py](backend/main.py) response builder).
- **Propose the minimally invasive safe action** (e.g., add a field rather than rename; UPSERT rather than DELETE+INSERT).
- **Re-read [frontend/AGENTS.md](frontend/AGENTS.md) before any frontend change** — Next.js 16 / React 19 may diverge from training-data assumptions.
- **Do not proceed until the user confirms** when the change touches the upload envelope, ORM table shape, or DSPy signature.

---

## Section 9 — Quick-Reference Cheat Sheet

| Task | Correct Module/Skill | Key Flag/Option |
|---|---|---|
| Add a new clause type | [backend/classifier.py](backend/classifier.py) + update `clause_type` desc in [dspy_pipeline.py:46-50](backend/dspy_pipeline.py#L46-L50) | Coordinate Dev1 + Dev2 |
| Replace mock classifier with real ML | [backend/classifier.py](backend/classifier.py) (Developer 1 only) | Keep `(str, float)` return |
| Edit DSPy prompt | [backend/dspy_pipeline.py](backend/dspy_pipeline.py) — `ContractClauseAnalysisV2` docstring + InputField/OutputField `desc` | Re-run optimizer after edit |
| Persist DSPy results | `save_results_to_db()` in [backend/db_writer.py](backend/db_writer.py) | UPSERT via `on_conflict_do_update` |
| Run pipeline with mock data | `python backend/run_pipeline.py` | `--mock --save` |
| Run pipeline against DB | `python backend/run_pipeline.py` | `--db --contract-id <UUID> --save` |
| Optimize prompts (fast) | `run_bootstrap_fewshot` ([optimizer.py:118](backend/optimizer.py#L118)) | `--optimize` |
| Optimize prompts (thorough) | `run_miprov2` ([optimizer.py:142](backend/optimizer.py#L142)) | `--optimize-mipro` |
| Add response field | [backend/main.py:186-202](backend/main.py#L186-L202) **and** [frontend/src/types/contracts.ts](frontend/src/types/contracts.ts) | Maintain envelope keys |
| Start Postgres | `docker compose up -d` | Repo root |
| Start backend | `cd backend && uvicorn main:app --reload --port 8000` | Requires `.env` |
| Start frontend | `cd frontend && npm run dev` | Port 3000; `NEXT_PUBLIC_API_BASE_URL` overrides backend URL |
| Lint frontend | `npm run lint` (in `frontend/`) | ESLint v9 |
| Build frontend | `npm run build` (in `frontend/`) | Next.js 16.2 |
| Install backend deps | `pip install -r backend/requirements.txt` | See [backend/requirements.txt](backend/requirements.txt) |

**State / schema paths (copy-paste):**
- `backend/models.py` — SQLAlchemy ORM (Contract, ParsedClause, RiskScore)
- `backend/schemas.py` — Pydantic (ClauseInput, ClauseAnalysisResult)
- `PRD/DataModel.md` — full target PostgreSQL schema spec
- `backend/.env` — local secrets (gitignored)
- `backend/.env.example` — secrets template
- `backend/optimized_pipeline.json` — compiled DSPy program (build artifact)
- `docs/snapshots/snapshot_2026-04-26.md` — most recent architecture snapshot

**Quality-gate commands (copy-paste):**
- `pip install -r backend/requirements.txt`
- `docker compose up -d`
- `cd backend && uvicorn main:app --reload --port 8000`
- `cd frontend && npm install && npm run dev`
- `cd frontend && npm run lint`
- `cd frontend && npm run build`
- `python backend/run_pipeline.py --mock` (smoke test — no DB, no save)

**Core state mutation invariant:** Per-clause risk results write to `risk_scores` via PostgreSQL UPSERT keyed on UNIQUE `parsed_clause_id`; the upload endpoint envelope keys (`status`, `filename`, `contract_id`, `parsed_clauses[]`, optional `detail`) are immutable and `clause_index` is 1-based monotonic.

**Escalation rule:** If a required file is `[MISSING]` or a required field is absent from the DB / response, **halt and surface the gap to the user** before proceeding. Do not synthesize plausible defaults for envelope keys, table columns, or DSPy field names.

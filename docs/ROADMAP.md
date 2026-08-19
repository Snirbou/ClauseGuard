# ClauseGuard — Technical Review & Implementation Roadmap

**Date:** 2026-08-20
**Baseline:** `main` @ `445de98` (post Phase 1–4 integration)
**Measured against:** `PRD/PRD.md` v1.0, `PRD/AcceptanceCriteria.md` v1.0

---

## 1. Honest assessment

### What is already genuinely good

- **Clean layering.** The DSPy pipeline (`dspy_pipeline.py`, `optimizer.py`, `db_writer.py`)
  is decoupled from HTTP; `analysis_service.py` orchestrates without reimplementing.
  Schema discipline is additive-only. The upload envelope is a stable, documented contract.
- **Verified, not assumed.** `smoke_test.py` covers the full path with 24 assertions;
  error paths (413, 422, 404, CORS-on-500) were exercised live.
- **UPL posture matches the PRD.** Non-dismissable disclaimer (AC-X01/X02), Consult-a-Lawyer
  CTA on high-risk clauses (AC-X03).
- **The hard ML work is already done — on an unmerged branch.** `osher-step-2` contains:
  - Layer 1: trained clause classifier, macro-F1 **0.929** (target: 0.85), LEDGAR-trained,
    CUAD OOD-evaluated, with a full training sandbox and a production `classifier.py`.
  - Layer 3: `scoring.py` hybrid scorer (L1 confidence + L2 risk + factor density +
    severity prior), pure module with unit tests.

### The real gaps, ranked by product impact

| # | Gap | Violates | Severity |
|---|-----|----------|----------|
| 1 | Synchronous, serial analysis — one HTTP request held open for the whole LLM loop | AC-U02 (p95 ≤ 60s), AC-API02 (≤ 2s), KPI latency | **Critical** |
| 2 | Three-layer AI architecture scattered across branches; main runs keyword matching | PRD O2, O5 (F1 ≥ 0.85, 3-layer depth) | **Critical** |
| 3 | Clause segmentation is a regex heuristic — the quality ceiling for everything downstream | AC-S02/S03 at risk on real contracts | High |
| 4 | No missing-clause detection — absence of protections (late-fee, IP carve-out, liability cap) is the freelancer's biggest risk and is invisible today | AC-R04 (5 pain points) | High |
| 5 | No migrations — `create_all` cannot evolve existing tables (already caused the index workaround) | blocks every schema change below | High |
| 6 | No real auth — osher-step-2's is a mock JWT | AC-A01–A04 (P1) | Medium |
| 7 | UPL mechanics incomplete: no progressive disclosure, no `disclaimer_logs`, no automated prescriptive-language check | AC-X04, X05, AC-P02 | Medium |
| 8 | LLM cost/reliability: re-analysis re-bills identical text; no retries; no cost accounting; shallow optimizer metric (length-based) | AC-A03 reproducibility; PRD L2 differentiators | Medium |
| 9 | No CI, no lockfile, no branch protection, no Dockerfiles | Definition of Done §5 | Medium |
| 10 | `risk_percentile` never populated → no comparative framing | AC-R02 | Low |
| 11 | Frontend: hand-rolled fetch layer, hand-mirrored API types, no evaluation dashboard | AC dashboard §4 | Low |

**KPI scorecard today:** F1 ≥ 0.85 ✅ (once merged) · p95 ≤ 60s ❌ · UPL 0 violations ✅ (manual) ·
API ≤ 2s analysis fetch ✅ · disclaimer log coverage ❌ (no table).

---

## 2. Design decisions recommended (and why)

1. **Adopt the PRD's own `analysis_runs` table as the job model.** Don't bolt on Celery/Redis
   yet — a DB-backed state machine (`pending → running → completed/failed`) plus an
   `asyncio` background task with bounded parallelism gets p95 under 60s for 5–20 page
   contracts with zero new infrastructure. The table is *already specified* in
   `PRD/DataModel.md` §2.6. The upgrade path to a real queue stays open.
2. **Parallelize per clause, persist per clause.** `process_clauses` is a serial loop;
   6 concurrent workers ≈ 6× faster. Persist each result as it lands so a crash loses
   one clause, not the run. Progress = `analyzed / total` straight from the DB.
3. **Cache by content hash.** `sha256(raw_text + model + program_version)` on `risk_scores`
   (additive column). Re-analysis of an unchanged clause is free and instant. This also
   satisfies AC-A03 (reproducibility) more honestly than re-calling the LLM.
4. **Merge osher-step-2 in two moves, backend first.** The ML directories are brand-new
   paths (zero conflict); only `classifier.py` wiring and 4 shared files collide. The
   frontend auth work conflicts structurally (`results/[contractId]` + route groups vs
   `contracts/[id]`) and needs a human decision with Osher — do not let it block the ML.
5. **Segmentation v2 = layout, not regex.** PyMuPDF already returns blocks, font sizes and
   bold flags — detect headings structurally, merge orphan fragments, fall back to
   sentence-window splitting (spaCy arrives with the Layer-1 merge anyway). Build a tiny
   eval corpus (10 real contracts, hand-counted clause boundaries) *first*; without it,
   segmentation tuning is blind.
6. **Missing-clause detection is a checklist, not ML.** After classification, diff the
   found clause types against the expected-protections list per pain point (late-payment
   penalty, IP carve-out, liability cap, termination notice symmetry, revision limits).
   Absences become contract-level risk cards. One extra LLM call for an executive
   summary. Highest value-per-line-of-code item in this plan.
7. **Auth: build it, small.** Argon2 password hashing + httpOnly session cookies +
   `users` table via Alembic. AC-A04 names the hash requirement explicitly; a mock JWT
   cannot ship. Clerk/Auth0 is the fallback if time runs short.
8. **Generate frontend types from OpenAPI** (`openapi-typescript`). The hand-mirrored
   `types/contracts.ts` already drifted once (missing `clause_type`); generation makes
   that class of bug impossible.

---

## 3. Implementation plan

Phases are dependency-ordered. Effort assumes one developer, focused.

### Phase A — Unify the AI you already own (1–2 days)
> Outcome: the PRD's 3-layer architecture live on `main`; F1 KPI met with a real model.

- [ ] Put a real `OPENAI_API_KEY` in `backend/.env`; run `smoke_test.py` → first verified live DSPy run.
- [ ] Merge from `osher-step-2` (backend only): `ml_inference/`, `ml_training/`, `models/`,
      `classifier.py`, `scoring.py`, `tests/`. Resolve the 4 shared-file collisions in favor of `main`.
- [ ] Fix the import seam: `main.py` calls `mock_classify` → new `classify()`; keep
      `mock_classify` as a fallback when the joblib artifact is absent (CI won't carry 18.8 MB).
- [ ] Add `spacy`, `en_core_web_lg`, `joblib`, `scikit-learn==1.5.2` (pin: pickle compat) to requirements.
- [ ] Wire Layer 3: `analysis_service` computes `compute_hybrid_score(...)` after DSPy and
      persists the blended `risk_level` (keep raw `dspy_risk_score` in the `risk_score` column).
- [ ] Extend `smoke_test.py`: assert classifier confidence varies (not the mock's fixed values)
      and hybrid level matches `scoring.py` thresholds.

**Exit gate:** upload → clauses classified by the trained model → analyze → hybrid risk levels persisted.

### Phase B — Foundations (1 day)
> Outcome: schema can evolve; regressions are caught by a machine, not by Snir.

- [ ] Alembic init; baseline migration reflecting the current schema; port the `init_db()` index DDL.
- [ ] GitHub Actions: `ruff` + `pytest` (scoring, segmentation, parsers) · `tsc && eslint && next build` ·
      optional job: dockerized Postgres + `smoke_test.py` (skips analyze without a key).
- [ ] Lockfiles: `uv pip compile` (or pip-tools) for backend; frontend already has `package-lock.json`.
- [ ] Protect `main`: require PR + green CI (after the merge flow is agreed).

### Phase C — Asynchronous analysis (2–3 days)
> Outcome: AC-U02/API02 met; analysis survives restarts; progress is visible.

- [ ] Migration: `analysis_runs` exactly per DataModel §2.6 + `content_hash` column on `risk_scores`.
- [ ] `POST /analyze` → creates a run, returns `202 {run_id}` immediately; keep sync mode behind
      `?wait=true` for the smoke test.
- [ ] Background executor: `asyncio.create_task` + semaphore(6) over `anyio.to_thread(analyzer(...))`;
      per-clause upsert on completion; run row updated with `processing_time_ms`, `clause_count`, errors.
- [ ] Cache hit path: skip clauses whose `content_hash` matches (config flag to force re-analysis).
- [ ] Retries with exponential backoff on transient LLM errors (3 attempts, jitter).
- [ ] Cost accounting: DSPy `track_usage` → tokens/cost into `analysis_runs.metadata`.
- [ ] Frontend: `GET /api/contracts/{id}` polling (TanStack Query), progress bar `analyzed/total`,
      per-clause skeletons filling in as results land.

**Exit gate:** 20-page contract completes p95 ≤ 60s; kill the server mid-run → completed clauses persist; re-run costs ≈ $0.

### Phase D — Analysis quality (2–3 days)
> Outcome: the product stops being a per-clause tool and understands the *contract*.

- [ ] Segmentation eval corpus: 10 real freelance agreements, hand-annotated boundaries;
      a script reporting boundary precision/recall + text coverage (AC-S03).
- [ ] Segmentation v2: PyMuPDF block/font-based heading detection → merge fragments →
      spaCy sentence fallback. Ship only if it beats v1 on the corpus.
- [ ] Missing-clause detection: expected-protections checklist per pain point → absence risks
      persisted (new `contract_findings` table) and rendered as contract-level cards.
- [ ] Executive summary: one DSPy call over clause summaries + findings; UPL-framed.
- [ ] `risk_percentile`: percentile rank of the hybrid score within the contract (AC-R02).
- [ ] DSPy optimizer upgrade: replace the length-based metric with a faithfulness/UPL-aware judge
      metric, grow the trainset to 20+ examples, run MIPROv2, commit a versioned artifact +
      before/after doc (PRD L2 differentiator).

**Exit gate:** a contract with no payment-terms clause shows a "missing protection" card; all 5 pain points demonstrably detectable (AC-R04).

### Phase E — Compliance & UX polish (1–2 days)
> Outcome: every UPL acceptance criterion is machine-checkable.

- [ ] Progressive disclosure (AC-X04): default clause card = summary + badge; factors/full text behind expand.
- [ ] `disclaimer_logs` table + log-on-render endpoint (AC-X05).
- [ ] Automated prescriptive-language check (AC-P02): post-generation filter in the pipeline +
      CI test over golden outputs; violations rewritten to observational framing.
- [ ] Evaluation dashboard page (`/dashboard`): classifier per-class F1 (from the metadata JSON),
      run latency p50/p95, active model + DSPy program versions (AcceptanceCriteria §4).
- [ ] `openapi-typescript` generation replacing the hand-written `types/contracts.ts`.
- [ ] Accessibility pass + RTL-readiness: swap physical CSS (`ml-`, `pl-`) for logical (`ms-`, `ps-`) — cheap now, expensive later.

### Phase F — Auth & multi-user (2–3 days)
> Outcome: AC-A01–A04 pass; contracts scoped to their owner.

- [ ] Migration: `users` per DataModel §2.1; nullable `user_id` on `contracts` → backfill → enforce.
- [ ] Argon2 hashing, httpOnly session cookie, register/login/logout endpoints, rate-limited.
- [ ] Scope every contract endpoint by the session user.
- [ ] **Decision with Osher:** reconcile frontend structures — keep `contracts/[id]` (main) vs
      `results/[contractId]` + `(auth)`/`(protected)` groups (osher-step-2). Recommendation:
      keep main's routes, port osher's auth screens/store into them.

**Exit gate:** two users cannot see each other's contracts; passwords verified Argon2 in DB.

### Phase G — Ship (1–2 days)
> Outcome: a URL you can put in a portfolio.

- [ ] Backend Dockerfile (multi-stage; model artifact via build arg or volume) + frontend Dockerfile.
- [ ] Full-stack `docker-compose.yml` (db + api + web) for a one-command local run.
- [ ] Deploy: API + Postgres on Railway/Fly/Render; frontend on Vercel; secrets via platform env.
- [ ] Uptime + error monitoring (healthcheck ping + Sentry free tier).
- [ ] Stretch: `ocrmypdf` fallback for scanned PDFs (today they fail with a clear error).

**Total: ~10–16 focused days.**

---

## 4. Explicitly deferred (post-MVP, per PRD §4.2)

- Hebrew/RTL end-to-end (the LEDGAR model won't transfer; needs an LLM-classification path for
  Hebrew; the RTL layout work is pre-paid by the logical-CSS item in Phase E).
- Lease/employment/NDA contract types (schema-ready via a future `contract_type` column).
- Template comparison; alternative clause drafting stays out forever (UPL, AC-X06).

## 5. Open decisions

| Decision | Options | Needed by |
|----------|---------|-----------|
| Frontend structure reconciliation | main routes (recommended) vs osher-step-2 routes | Phase F |
| Auth build vs buy | Argon2 + sessions in-house (recommended) vs Clerk | Phase F |
| Deploy target | Railway (recommended: managed PG) / Fly / Render | Phase G |
| Queue upgrade trigger | stay on asyncio until a multi-instance deploy | Phase G+ |

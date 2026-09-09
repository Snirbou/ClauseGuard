# ClauseGuard — Project Status

**As of:** 2026-09-09
**Branch:** `main` (the only branch)
**Verify anything on this page yourself:**

```bash
powershell -ExecutionPolicy Bypass -File .claude/skills/verify-clauseguard/run_checks.ps1
```

This is the "start here" document. `README.md` explains how to run the
product; `docs/DEPLOY.md` how to host it; `docs/ROADMAP.md` is the technical
review that drove the build. This file answers three questions: what exists,
what remains, and what future work must not rediscover.

---

## 1. What exists today

The product is **feature-complete and works end to end out of the box.** With
no API key it runs in offline demo mode; pasting a real `OPENAI_API_KEY` into
`backend/.env` is the only step needed for real AI analysis.

| Area | State |
|---|---|
| Upload → PDF extraction → layout-aware clause segmentation | ✅ |
| **Layer 1** trained clause classifier (macro-F1 **0.929**, LEDGAR) with keyword fallback | ✅ |
| **Layer 2** DSPy + LLM plain-language summaries and risk factors | ✅ |
| **Layer 3** hybrid risk scoring (classifier confidence + LLM signals) | ✅ |
| Asynchronous analysis runs: `202` + run id, live progress, per-clause persistence, content-hash cache, retries, crash recovery | ✅ |
| Contract-level intelligence: missing-protection findings (5 pain points), executive summary, risk percentiles | ✅ |
| Authentication: Argon2 passwords, httpOnly cookie sessions, per-user data isolation, rate limiting | ✅ |
| UPL safeguards: non-dismissable disclaimer + audit log, prescriptive-language filter, progressive disclosure, Consult-a-Lawyer CTA | ✅ |
| Evaluation dashboard (per-class F1, latency percentiles, compliance counters) | ✅ |
| Alembic migrations (7 revisions), GitHub Actions CI (lint, tests, migration drift, **image boot test**), ruff, lockfile | ✅ |
| One-command verification skill (`verify-clauseguard`) | ✅ |
| **Deploy-ready images**: reproducible lockfile install, pinned spaCy model layer, non-root, IPv4+IPv6 listener, `$PORT`, health that fails loudly (503), database retry at boot, Railway config-as-code (`backend/railway.json`, `frontend/railway.json`) and runbook (`docs/DEPLOY.md`) | ✅ |
| **spaCy model-size ablation**: `en_core_web_sm` serves the classifier at a 0.001 macro-F1 cost vs `en_core_web_lg` (official LEDGAR test split, n=10 000) for a third of the memory — now the default | ✅ |
| **Hebrew UI + RTL (Layer 1)**: cookie-based EN/HE switch, `<html lang dir>` from the root layout, Heebo font, typed dictionaries (`frontend/src/i18n`), Hebrew findings and localized API errors via stable error codes (`backend/error_codes.py`); contract text and AI output stay English and render as isolated LTR blocks | ✅ |
| **Evaluation completeness**: p99 latency, summary readability (AC-P04), the Layer 1 held-out confusion matrix and per-class precision/recall, one annotation format serving both the segmentation benchmark and the risk labels (`backend/eval/`, see its README), AC-R05 risk scaffolding that refuses to publish unmeasured numbers, and DSPy program identity + optimizer history — all surfaced on the dashboard in both locales | ✅ |

### Verification evidence (2026-09-09)

| Check | Result |
|---|---|
| Backend unit tests (`pytest tests/`) | 291 passing, 1 skipped (the private-corpus test) |
| ML training tests (`pytest ml_training/tests/`) | 19 passing |
| End-to-end smoke test (`smoke_test.py`) against the full Docker stack — through the Next rewrite (`:3000`) **and** directly (`:8000`) | 63 + 63 checks passing |
| Database stopped under the running API → `/api/health` | `503`, back to `200` when the database returns |
| Container identity | `uid=10001(app)`, listening on `0.0.0.0` and `[::]` |
| Frontend `tsc` / `eslint` / `next build` | clean (dictionary parity is type-checked) |
| Hebrew/RTL live check (dev server + browser) | `lang=he dir=rtl`, Heebo applied, he-IL dates, English clause/summary blocks LTR, mirrored disclosure glyph, no horizontal overflow at 375 px |
| Migration drift (`alembic check`) | none |
| spaCy ablation (`07_spacy_model_ablation.py`, sm / md / lg) | served macro-F1 0.8801 / 0.8808 / 0.8811; RSS 328 / 527 / 902 MB |

Two independent adversarial reviews were run against the build earlier (a
5-dimension backend/security/data pass and a deep frontend-correctness
pass). Every confirmed finding was fixed and regression-tested.

---

## 2. What remains — the execution plan

Phases run in this order (portfolio URL first). Each ends with the full
verification set and one commit on `main`.

| # | Phase | Gate | State |
|---|---|---|---|
| 1A | Deploy hardening (code) | — | ✅ done |
| 1B | spaCy model-size experiment | — | ✅ done — `en_core_web_sm` |
| 1C | Railway deployment (API + web + Postgres), CD on push | **you:** Railway project (see `docs/DEPLOY.md` §1) | ⏳ next |
| 2 | Hebrew UI + RTL (Layer 1: Hebrew interface for English contracts; findings and API errors translated; LLM output stays English) | — | ✅ done |
| 3 | Evaluation & dashboard completeness that needs no key: p99, readability (AC-P04), L1 confusion matrix, one annotation format for the real-contract corpus, segmentation boundary P/R gate, risk-eval scaffolding (AC-R05), DSPy program identity + optimizer history plumbing | **you:** ~10 anonymized contracts in `backend/eval/corpus/` (gitignored) | ✅ built — awaiting your contracts to produce numbers |
| 4 | Key-gated LLM work: real-path validation, optimizer upgrade (judge metric, 24+ examples, valset, before/after harness), AC-R05 end-to-end | **you:** `OPENAI_API_KEY` in `backend/.env` and on Railway + a spend cap | ⏳ |
| 5 | OCR for scanned PDFs (Tesseract via PyMuPDF, page cap, inline) | — | ⏳ |

### Only you can do these
- **Create the Railway project** and paste the variables — the click-path is
  `docs/DEPLOY.md` §1. Until a key exists the site runs the labeled demo
  analyzer (`DSPY_PROVIDER=fake`); afterwards pin `openai`.
- **Protect `main`** in GitHub → *Settings → Branches* (require PR + green
  CI, including the new `api-image` job). Cannot be done from the CLI here.
- **Provide the contracts** (Phase 3): drop ~10 anonymised PDFs into
  `backend/eval/corpus/` (gitignored), run `eval/annotate.py` on each and
  correct the draft — `backend/eval/README.md` is the walkthrough. Until
  they exist the harness runs and reports "nothing to evaluate"; with them
  it produces the segmentation benchmark and the risk gold set.
- **The OpenAI key** (Phase 4) — it goes in `backend/.env` / Railway
  variables, never in chat.
- **Review the Hebrew dictionary** (Phase 2) for tone and UPL-safe phrasing.

### Explicitly deferred (not built)
- Hebrew LLM output (needs Hebrew prescriptive patterns in `upl.py` first).
- Hebrew *contracts* (Layer 2), multi-replica hosting, custom domain, async
  extraction runs.

---

## 3. Housekeeping done (2026-09-07)

All of this is recoverable from git history; nothing was force-deleted.

- **Branches consolidated.** `Snir-Phase-1`, `osher-step-1`, and
  `osher-step-2` were each verified to be full ancestors of `main` and then
  deleted from `origin` and locally. **`main` is the only branch.**
- **Superseded documents removed:** `docs/raw/` and `docs/snapshots/`
  described the pre-integration system; `README.md` + `docs/ROADMAP.md` are
  the current truth. Recover with `git show <commit>:<path>` if needed.
- **Install logs untracked** and covered by `.gitignore`; build caches are
  gitignored and regenerate automatically.

---

## 4. Things future work must not rediscover

Short versions; the README has the details.

- `dspy.configure()` is single-owner — it runs exactly once per process.
- `numpy` must import before `dspy`/`litellm`, or a later spaCy import
  crashes predict (`"data type 'bool' not understood"`). Pinned at the top of
  `main.py` and `classifier.py`.
- The classifier artifact was trained on Python 3.11 / sklearn 1.5.2 /
  `en_core_web_lg` and runs here on 3.13 / newer sklearn / `en_core_web_sm`;
  loading is validated with a smoke prediction and falls back to keyword
  rules on failure. `SPACY_MODEL` is read from the environment when the
  pickle first imports `ml_inference/src/nlp_singleton.py`; `classifier.py`
  exports the `backend/.env` value there before loading.
- **`uvicorn --host ::` is IPv6-only** under asyncio (it sets
  `IPV6_V6ONLY`), which silently breaks IPv4 clients such as Docker's port
  proxy and compose. `backend/serve.py` binds both families explicitly —
  Railway's private network needs IPv6, everything else needs IPv4.
- **Next.js buffers the body of rewritten requests with a 10 MB cap** and
  truncates silently; `experimental.proxyClientMaxBodySize: "12mb"` in
  `next.config.ts` lets the API's own 10 MB limit answer with a proper 413.
- **`requirements.lock.txt` must be regenerated when `requirements.txt`
  changes.** The image installs from the lock; a dependency added only to
  `requirements.txt` (this happened with `argon2-cffi`) crash-loops the
  container while the dev venv keeps working.
- **PDF text extraction lives in exactly one place** (`backend/pdf_extract.py`).
  The gold annotations of the evaluation corpus are anchored to the text that
  function returns, so a second extraction path would silently invalidate the
  benchmark. The upload endpoint, the segmentation tests and every script in
  `backend/eval/` call it.
- **The compiled DSPy program is identified by a content hash**, not by mtime:
  git does not preserve file times, so an mtime tag would invalidate every
  cached clause result on each fresh clone. Bumping `_PIPELINE_VERSION`
  (`analysis_service.py`) is the deliberate way to force re-analysis.
- The verification PowerShell script must stay **ASCII-only** (PS 5.1 reads
  `.ps1` as the system codepage without a BOM).
- The two pytest roots (`tests/`, `ml_training/tests/`) must run **separately**
  — both expose a top-level `src`/`features` module.
- Schema changes are additive only and go through Alembic; startup stamps
  pre-Alembic databases automatically.

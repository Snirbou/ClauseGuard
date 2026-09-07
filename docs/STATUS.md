# ClauseGuard — Project Status

**As of:** 2026-09-07
**Branch:** `main` (the only branch — see *Housekeeping* below)
**Verify anything on this page yourself:**

```bash
powershell -ExecutionPolicy Bypass -File .claude/skills/verify-clauseguard/run_checks.ps1
```

This is the "start here" document. `README.md` explains how to run the
product; `docs/ROADMAP.md` is the technical review that drove the build. This
file answers three questions: what exists, what remains, and what was cleaned
up.

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
| Alembic migrations (7 revisions), GitHub Actions CI, ruff, lockfile | ✅ |
| One-command verification skill (`verify-clauseguard`) | ✅ |
| Docker images + full-stack `docker-compose.full.yml` | ✅ |

### Verification evidence

| Check | Result |
|---|---|
| Backend unit tests (`pytest tests/`) | 102 passing |
| ML training tests (`pytest ml_training/tests/`) | 19 passing |
| End-to-end smoke test (`smoke_test.py`, live API + DB) | 63 checks passing |
| Frontend `tsc` / `eslint` / `next build` | clean, 8 routes |
| Migration drift (`alembic check`) | none |
| Full skill run on a fresh clone of `main` (2026-09-07) | **13 passed, 0 failed** |

**Latest full run (2026-09-07, fresh clone at `C:\Users\snirb\repos\ClauseGuard`):**
`SUMMARY: 13 passed, 0 failed` — all four sections green. Docker was not
running when the run started; the skill's own recovery path (`docker compose
up -d` + retry) brought Postgres up and the run completed in full, so that
branch of the skill is verified too.

Two independent adversarial reviews were run against the build (a 5-dimension
backend/security/data pass and a deep frontend-correctness pass). Every
confirmed finding was fixed and regression-tested; **no critical or high
defects remained**.

---

## 2. What remains

### The one thing only you can do
- **Paste a real OpenAI key** into `backend/.env` (`OPENAI_API_KEY=sk-...`) and
  restart the backend. `DSPY_PROVIDER=auto` detects it and switches from the
  labeled demo analyzer to `gpt-4o-mini`. Then run `python smoke_test.py` once
  more — with a real key it exercises the actual LLM path end to end.

### Deliberately deferred (not built — see `docs/ROADMAP.md` §4)
| Item | Why deferred | Effort |
|---|---|---|
| Cloud deployment (API + Postgres on Railway/Fly/Render, web on Vercel) | needs your hosting accounts and secrets | 1–2 days |
| DSPy optimizer upgrade (judge-based metric, 20+ examples, MIPROv2) | needs a real API key to run | 1 day |
| OCR for scanned PDFs (`ocrmypdf` fallback) | needs the tesseract system dependency; today scanned PDFs fail with a clear error | ½ day |
| Real-contract segmentation eval corpus (10 hand-annotated contracts) | needs real contracts; a synthetic corpus ships instead | ½ day + your contracts |
| Hebrew / RTL end-to-end | post-MVP per PRD; the LEDGAR classifier won't transfer, RTL layout is pre-paid via logical CSS | large |
| Risk precision/recall on the dashboard (AC-R05) | needs labeled risk data (CUAD/UNFAIR-ToS) | 1 day |

### Housekeeping still needing the GitHub UI
- **Protect `main`** (require PR + green CI). Cannot be done from the CLI here
  (no `gh`); do it in *Settings → Branches*. Recommended now that the merge
  flow is finished.

---

## 3. Housekeeping done (2026-09-07)

All of this is recoverable from git history; nothing was force-deleted.

- **Branches consolidated.** `Snir-Phase-1`, `osher-step-1`, and
  `osher-step-2` were each verified to be full ancestors of `main` (every
  commit already merged) and then deleted from `origin` and locally. **`main`
  is now the only branch** — everything lives in one place.
- **Superseded documents removed:** `docs/raw/` (a raw AI chat dump and the
  Step-1 developer handoff notes) and `docs/snapshots/` (three architecture
  snapshots from March–May). They described the pre-integration system and
  could mislead a reader; `README.md` + `docs/ROADMAP.md` are the current
  truth. Recover any of them with `git show <commit>:<path>` if needed.
- **Install logs untracked** (`pip.log`, `pip_install.log`, `npm_out.txt`)
  and covered by `.gitignore`; build caches (`__pycache__`, `.pytest_cache`,
  `.ruff_cache`, `tsconfig.tsbuildinfo`) cleared from disk — all are
  gitignored and regenerate automatically.

---

## 4. Things future work must not rediscover

Short versions; the README has the details.

- `dspy.configure()` is single-owner — it runs exactly once per process.
- `numpy` must import before `dspy`/`litellm`, or a later spaCy import
  crashes predict (`"data type 'bool' not understood"`). Pinned at the top of
  `main.py` and `classifier.py`.
- The classifier artifact was trained on Python 3.11 / sklearn 1.5.2 and runs
  here on 3.13 / newer sklearn; loading is validated with a smoke prediction
  and falls back to keyword rules on failure.
- The verification PowerShell script must stay **ASCII-only** (PS 5.1 reads
  `.ps1` as the system codepage without a BOM).
- The two pytest roots (`tests/`, `ml_training/tests/`) must run **separately**
  — both expose a top-level `src`/`features` module.
- Schema changes are additive only and go through Alembic; startup stamps
  pre-Alembic databases automatically.

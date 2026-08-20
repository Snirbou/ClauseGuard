---
name: verify-clauseguard
description: Run the full ClauseGuard verification suite across the whole project — Postgres reachability, backend lint + unit tests + migration integrity, a live 63-check end-to-end API smoke test, and frontend typecheck + lint + build. Use whenever asked to verify, test, check, or validate the ClauseGuard project end to end, or before committing/merging a significant change.
---

# Verify ClauseGuard

One command that checks every automated-verifiable element of the project and
prints a single PASS/FAIL summary. Use this to confirm the whole system is
healthy after changes, before a merge, or when the user asks to "test
everything."

## How to run it

The runner is a PowerShell script (the project's primary shell). From the repo
root:

```bash
powershell -ExecutionPolicy Bypass -File .claude/skills/verify-clauseguard/run_checks.ps1
```

It exits `0` only if every check passes, non-zero otherwise. Run it and report
the summary; if anything fails, read the failing section's detail line and
investigate the specific check.

Useful flags:
- `-SkipFrontendBuild` — skip the ~1–2 min `next build` (still runs tsc + eslint).
- `-SkipDocker` — don't try to start Postgres (assume it's already up).
- `-Port 8000` — backend port for the live-API section.

Example (fast inner-loop, no production build):

```bash
powershell -ExecutionPolicy Bypass -File .claude/skills/verify-clauseguard/run_checks.ps1 -SkipFrontendBuild
```

## What it checks (in dependency order)

1. **Database** — Postgres is reachable at `DATABASE_URL`. If not and Docker is
   allowed, it runs `docker compose up -d` and waits.
2. **Backend (static)** — `ruff check`, the full unit suite
   (`pytest tests/ ml_training/tests/`), and that `main` imports cleanly. With a
   database it also runs `alembic upgrade head`, `alembic check` (fails on any
   ORM-vs-migration drift), and asserts a single migration head.
3. **Live API** — starts `uvicorn` if nothing healthy is on the port, waits for
   `/api/health`, then runs `smoke_test.py` (63 end-to-end assertions: auth,
   upload, error paths, asynchronous analysis with progress polling, caching,
   findings, percentiles, cross-user isolation, delete cascade). Stops the
   server only if the skill started it.
4. **Frontend** — `tsc --noEmit`, `eslint src`, and (unless skipped) a
   production `next build`. Runs `npm ci` first if `node_modules` is absent.

## Interpreting results

- A green `SUMMARY: N passed, 0 failed` means the whole project verifies.
- Each failing check prints a `detail` line (the last lines of its output) —
  start there. Common causes:
  - *Postgres reachable* fails → `docker compose up -d`.
  - *smoke test* needs a running DB **and** works in demo mode without an API
    key (`DSPY_PROVIDER=auto`); it does not require OpenAI.
  - *no model/migration drift* fails → a model changed without a matching
    Alembic migration; generate one with
    `alembic revision --autogenerate -m "..."`.

## Notes

- Verification runs against `backend/.env`. With the placeholder OpenAI key the
  app runs in offline demo mode and every check still passes — no real API key
  is required to verify the system.
- The script is read-only with respect to source; it only touches the database
  (migrations/smoke-test rows, which the smoke test cleans up after itself) and
  may start/stop a local uvicorn and the Postgres container.

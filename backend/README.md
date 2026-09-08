# ClauseGuard Backend (FastAPI)

Full setup, architecture, API reference and configuration live in the
[root README](../README.md). This file is the short version.

## Install

```powershell
python -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\python -m spacy download en_core_web_sm   # optional, ~12MB (SPACY_MODEL picks the pipeline)
```

Without the spaCy model the trained classifier falls back to keyword rules
(`/api/health` reports `"mode": "mock"`); everything else works.

If the install fails with `OSError: [Errno 2] No such file or directory`
while unpacking litellm, that is the Windows 260-character path limit — see
the note in `requirements.txt`.

## Configure

```powershell
copy .env.example .env
```

With the placeholder key the app runs in offline demo mode. Paste a real
`OPENAI_API_KEY` to switch to real analysis (`DSPY_PROVIDER=auto` picks it
up on restart).

## Run

```powershell
venv\Scripts\python -m uvicorn main:app --reload --port 8000
```

Startup runs Alembic migrations (`database.init_db`), recovers stale
analysis runs, and warms the classifier. Interactive docs:
<http://127.0.0.1:8000/docs>

## Verify

```powershell
venv\Scripts\python -m pytest tests\          # 127 unit tests
venv\Scripts\python smoke_test.py             # 63 end-to-end checks (needs DB + server)
venv\Scripts\python -m ruff check .
```

## Migrations

```powershell
venv\Scripts\python -m alembic upgrade head
venv\Scripts\python -m alembic revision --autogenerate -m "describe change"
```

The URL comes from `config.settings` (backend/.env); `ALEMBIC_DATABASE_URL`
overrides it for scratch databases. Databases created before Alembic are
detected and stamped automatically at startup.

## CLI (offline pipeline runs)

```powershell
venv\Scripts\python run_pipeline.py --mock                      # no DB needed
venv\Scripts\python run_pipeline.py --db --contract-id <UUID> --save
venv\Scripts\python run_pipeline.py --mock --optimize           # BootstrapFewShot
```

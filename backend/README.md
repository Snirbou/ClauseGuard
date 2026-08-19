# ClauseGuard Backend (FastAPI)

Full setup, architecture, API reference and configuration live in the
[root README](../README.md). This file is the short version.

## Install

```powershell
pip install -r requirements.txt
```

If the install fails with `OSError: [Errno 2] No such file or directory` while
unpacking `litellm`, that is the Windows 260-character path limit — see the
"Windows install note" section of the root README.

## Configure

```powershell
copy .env.example .env
```

Set a real `OPENAI_API_KEY` to enable AI analysis. Everything else works
without one.

## Run

```powershell
uvicorn main:app --reload --port 8000
```

Interactive docs: <http://127.0.0.1:8000/docs>

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/health` | Database reachability, LLM configuration, upload limit |
| `POST` | `/api/contracts/upload` | Upload a PDF → extract, segment, classify, persist |
| `GET` | `/api/contracts` | List contracts with clause counts and analysis status |
| `GET` | `/api/contracts/{id}` | Contract detail with clauses joined to their risk scores |
| `POST` | `/api/contracts/{id}/analyze` | Run the DSPy pipeline and persist `risk_scores` |
| `DELETE` | `/api/contracts/{id}` | Delete a contract (clauses and scores cascade) |

## CLI

```powershell
python run_pipeline.py --mock                      # offline, no DB needed
python run_pipeline.py --db --contract-id <UUID> --save
python run_pipeline.py --mock --optimize           # BootstrapFewShot
```

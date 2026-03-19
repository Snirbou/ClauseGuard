# ClauseGuard - AI-Powered Contract Clause Analyzer

## Overview
ClauseGuard is an AI-powered platform for analyzing contracts and extracting meaningful clause-level text segments from uploaded PDF documents.

## Current Status
**Phase 0 (Walking Skeleton) Complete - Baseline established. No DB, Auth, or AI yet.**

This phase focuses on a bare-minimum end-to-end pipeline:
1. Next.js UI uploads a PDF via `multipart/form-data`.
2. FastAPI backend extracts text from the PDF (PyMuPDF).
3. The text is segmented into “clauses” using a naive heuristic.
4. The backend returns JSON to the frontend for rendering.

## Architecture Map
Repository layout:

- `frontend/` (Next.js, App Router, Tailwind)
  - Upload UI (drag-and-drop + file picker)
  - Calls the backend upload endpoint
  - Renders `parsed_clauses`
- `backend/` (FastAPI)
  - Implements `POST /api/contracts/upload`
  - Validates PDF upload
  - Extracts PDF text with PyMuPDF
  - Segments text into clauses (currently naive heuristic)
  - Returns JSON with a strict contract schema (see below)

## Strict API Contract (Must Preserve)
Endpoint:
`POST /api/contracts/upload`

### Request
`Content-Type: multipart/form-data`

- `file`: PDF binary (field name is exactly `file`)

### Response (Success)
`200 OK`

```json
{
  "status": "success",
  "filename": "msa.pdf",
  "parsed_clauses": [
    {
      "clause_index": 1,
      "raw_text": "This Agreement starts on the Effective Date..."
    },
    {
      "clause_index": 2,
      "raw_text": "Either party may terminate with 30 days notice..."
    }
  ]
}
```

### Response (Error)
`400 Bad Request` (and other non-2xx cases as applicable)

Error envelope (structure is intentionally consistent):

```json
{
  "status": "error",
  "filename": "msa.pdf",
  "parsed_clauses": [],
  "detail": "Invalid file type. PDF required."
}
```

### Schema Rules (For Developer 2)
- `status`: `"success" | "error"`
- `filename`: string (echo of the uploaded filename)
- `parsed_clauses`:
  - must always exist
  - for `"success"`: array of objects
  - for `"error"`: must be an empty array `[]`
- `parsed_clauses[]` object:
  - `clause_index`: integer, **1-based**, monotonic increasing
  - `raw_text`: string clause text as produced by the segmentation/classification pipeline
- `detail`:
  - present for errors
  - can be a human-readable message

## Run Instructions (Local)
### 1. Start FastAPI backend

From the repo root:

```powershell
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Backend listens on:
- `http://127.0.0.1:8000`

### 2. Start Next.js frontend

Open another terminal from the repo root:

```powershell
cd frontend
npm install
npm run dev
```

Frontend listens on:
- `http://localhost:3000`

### 3. Connecting frontend to backend (API base URL)
By default, the frontend expects the backend at `http://localhost:8000`.

Optional:
Set `NEXT_PUBLIC_API_BASE_URL` before running the frontend if your backend is elsewhere.

## Developer 2 Orientation (Crucial)
Your immediate job is to upgrade the backend from a naive clause segmentation heuristic to a real NLP pipeline (spaCy + Clause Classification with scikit-learn), **without breaking the strict API response structure** documented above.

### What to change
Go to:
`backend/main.py`

Locate the naive segmentation step that currently splits extracted text using a blank-line heuristic:

- `re.split(r"\n\s*\n", full_text)`

### What to replace it with
Replace that logic with:
1. Proper text preprocessing + segmentation using **spaCy** (or a spaCy-based strategy).
2. Clause classification using **scikit-learn** (or an sklearn-based strategy).
3. Output a list of clause texts, preserving the same “clause ordering” behavior (your system can re-order, but you must still return `clause_index` as a monotonic 1-based sequence).

### What must NOT change
Despite any internal refactor, the `POST /api/contracts/upload` endpoint must continue to return **exactly** the same top-level envelope and schema:
- `status`
- `filename`
- `parsed_clauses[] { clause_index, raw_text }`
- error envelope must keep: `status`, `filename`, `parsed_clauses: []`, and `detail`.

### Output stability checklist
When you implement the NLP/classification pipeline:
- Always return `parsed_clauses` (never omit it).
- Always keep `clause_index` 1-based and monotonic.
- Always keep `raw_text` as a string.
- Never add new required top-level keys to the success/error envelope.

## Manual Smoke Test (Suggested)
After both servers are running:

### Backend-only (example with curl)
```powershell
curl -X POST http://127.0.0.1:8000/api/contracts/upload `
  -F "file=@C:/path/to/your/contract.pdf"
```

### Frontend
- Open `http://localhost:3000`
- Upload a PDF
- Confirm `parsed_clauses` render in the UI


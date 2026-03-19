# ClauseGuard Backend (FastAPI) - Step 0

## Install
```powershell
pip install -r requirements.txt
```

## Run
```powershell
uvicorn main:app --reload --port 8000
```

## Upload endpoint
`POST /api/contracts/upload`

Request: `multipart/form-data` with a `file` field containing a PDF.

Response JSON matches the contract described in the Step 0 plan.


# FlowGuard

FlowGuard is a configurable workflow decision platform. Phases 1-3 provide the FastAPI
health endpoint, versioned YAML configuration and pure rule engine, SQLite persistence,
idempotent request intake, workflow discovery, and request status retrieval. Intake creates a
`RECEIVED` request only; workflow stage execution, decision evaluation, retries, audit reads,
reviews, and configuration activation are later-phase work.

## Requirements and installation

- Python 3.11 or newer
- pip

Windows PowerShell from the repository root:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

If the `py` launcher is unavailable, use `python -m venv .venv` after confirming
`python --version` reports Python 3.11 or newer. Commands below use the venv interpreter
directly, so activation is optional.

## Database setup and run

SQLAlchemy creates the SQLite schema and stores validated workflow snapshots on application
startup. The default database is `flowguard.db` in the current working directory. To select a
different location in PowerShell:

```powershell
$env:FLOWGUARD_DATABASE_URL = "sqlite:///./local-flowguard.db"
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

If unset, just run:

```powershell
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Swagger UI: `http://127.0.0.1:8000/docs`. Health: `http://127.0.0.1:8000/health`.
For SQLite, FlowGuard enables foreign keys and serializes write transactions with
`BEGIN IMMEDIATE`; SQLite therefore supports one writer at a time. Do not run multiple
application worker processes against this MVP database.

## API examples

Create a request (new request returns `202`; an equivalent idempotent replay returns `200`):

```powershell
$body = @{
  workflow_id = "loan_approval"
  data = @{
    applicant = @{
      age = 24
      monthly_income = 60000
      credit_score = 750
    }
  }
} | ConvertTo-Json -Depth 8

$created = Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/api/v1/requests" `
  -Headers @{ "Idempotency-Key" = "loan-demo-001" } `
  -ContentType "application/json" `
  -Body $body
$created
```

Read request status and configured workflow versions:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000$($created.status_url)"
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/workflows"
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/workflows/loan_approval/versions"
```

Errors use `{ "error": { "code": "...", "message": "..." } }` (validation errors also
include details). The `Idempotency-Replayed: true` response header marks a replay. Request
payload hashes include workflow ID and canonical JSON `data`; keys are scoped by workflow ID.

## Configuration and version selection

Workflow definitions live in `configs/workflows/`; versioned structural request schemas live
in `configs/input_schemas/`. At startup, all definitions are validated by the Phase 2 loader,
combined with their input schemas, checksummed and persisted. The highest configured integer
version for each workflow is deterministically selected as active. Existing snapshots are
immutable: if an on-disk definition changes without a new version, startup fails with a
checksum mismatch. Requests store their selected `workflow_id` and `config_version`. Phase 5
will add explicit activation; this phase intentionally has no activation endpoint.

## Test

```powershell
.venv\Scripts\python.exe -m pytest -q
```

Integration tests use isolated temporary, file-backed SQLite databases and never the
developer's default database.

## Project map

- `app/api/`: HTTP schemas, routes and error mapping
- `app/engine/`: Phase 2 configuration loader and pure rules
- `app/persistence/`: SQLAlchemy models, sessions and repositories
- `app/services/`: configuration snapshotting, input validation and intake
- `configs/workflows/`: loan v1/v2 and vendor v1 definitions
- `configs/input_schemas/`: version-specific structural input schemas
- `tests/`: unit and integration suites
- `docs/`, `project_management/`: design, decisions, evidence and handoff

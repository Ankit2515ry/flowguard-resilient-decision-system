# FlowGuard

FlowGuard is a configurable workflow decision platform. Phases 1-4 provide FastAPI, a
versioned YAML rule engine, SQLite-backed idempotent intake, explicit workflow execution,
audit events, decision explanations, an external verification simulator, and persisted
bounded retries. Requests are accepted first and execute only when explicitly triggered.

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
`python --version` reports Python 3.11 or newer. Activation is optional; commands below use
the virtual environment interpreter directly.

## Database and server

SQLAlchemy initializes the SQLite schema and persists validated workflow snapshots when the
application starts. The default database is `flowguard.db` in the current working directory.
Choose a database explicitly in PowerShell:

```powershell
$env:FLOWGUARD_DATABASE_URL = "sqlite:///./flowguard.db"
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Swagger UI: `http://127.0.0.1:8000/docs`. Health: `http://127.0.0.1:8000/health`.
SQLite enables foreign keys and uses `BEGIN IMMEDIATE`, which serializes database transactions.
The MVP supports a single retry worker process. Schema changes are applied with additive
startup upgrades; Alembic is deferred.

## Submit and execute a request

`POST /api/v1/requests` requires `Idempotency-Key`. A new request returns HTTP 202 with
status `RECEIVED`; equivalent replays return 200 and `Idempotency-Replayed: true`; a changed
payload under the same scoped key returns 409.

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

$executed = Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000$($created.status_url)/execute"
$executed.status
$executed.decision.outcome
```

`POST /api/v1/requests/{request_id}/execute` is safe to repeat. It returns the current
persisted state if the request is already processing, waiting for retry, under manual review,
or complete. `GET /api/v1/requests/{request_id}` returns the status, current stage, revision,
pinned config version, and decision explanation when available. Typical outcomes are
`APPROVED`, `REJECTED`, `MANUAL_REVIEW`, and `RETRY_WAIT`; technical workflow errors end at
`FAILED`.

The sample loan v2 is active by default. With age 24, income 60000, and credit score 750,
the completed result is `APPROVED`. A valid request with credit score 710 enters
`MANUAL_REVIEW`; an age below 18 is `REJECTED`. The vendor example uses its configured
registration, compliance, turnover and verification stages.

## Simulate an external dependency and run retries

The simulator is configured by the server environment, never by client payload fields. Set
the scenario before starting/restarting the API process:

```powershell
$env:FLOWGUARD_SIMULATOR_SCENARIO = "FAIL_THEN_RECOVER"
$env:FLOWGUARD_SIMULATOR_FAIL_ATTEMPTS = "1"
$env:FLOWGUARD_RETRY_MAX_ATTEMPTS = "3"
$env:FLOWGUARD_RETRY_BASE_DELAY_SECONDS = "0"
$env:FLOWGUARD_RETRY_MAX_DELAY_SECONDS = "60"
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Submit and execute a request as above. Its first external verification fails and the status
becomes `RETRY_WAIT`. Process due work with:

```powershell
.venv\Scripts\python.exe -m app.workers.retry_worker --once
```

The worker uses the same `FLOWGUARD_DATABASE_URL` and simulator/retry environment. Check the
request again with `GET /api/v1/requests/{request_id}`; `FAIL_THEN_RECOVER` succeeds on the
next attempt. `TEMPORARY_FAILURE` continues failing until the configured limit; `SUCCESS`
passes immediately; `PERMANENT_FAILURE` follows the configured `FAILURE` transition.

`FLOWGUARD_RETRY_MAX_ATTEMPTS` counts the initial external call as attempt 1. A retryable
failure schedules another attempt only while the total remains below that limit. Delay is
`min(max_delay, base_delay * 2^(failed_attempt - 1))`. Defaults are 3 total attempts, 1 second
base delay, 60 second cap, and a 120 second execution/retry lease.

## Inspect explanations and audit events

The request status response includes `decision.explanation.rule_traces` after a decision:

```powershell
$status = Invoke-RestMethod "http://127.0.0.1:8000$($created.status_url)"
$status.decision.explanation.rule_traces | ConvertTo-Json -Depth 8
```

Audit events are stored in ordered `audit_events` rows. Inspect them for a request ID with
the project ORM (using the same `FLOWGUARD_DATABASE_URL`):

```powershell
$env:FLOWGUARD_REQUEST_ID = $created.request_id
.venv\Scripts\python.exe -c "import os; from sqlalchemy import select; from app.persistence.database import Database; from app.persistence.models import AuditEvent; db=Database(); s=db.session_factory(); rows=s.scalars(select(AuditEvent).where(AuditEvent.request_id == os.environ['FLOWGUARD_REQUEST_ID']).order_by(AuditEvent.sequence)).all(); print([(e.sequence, e.event_type, e.old_state, e.new_state, e.details) for e in rows]); s.close(); db.dispose()"
```

API errors use `{ "error": { "code": "...", "message": "..." } }`; request validation
errors include field details. Workflow and schema versions are listed by
`GET /api/v1/workflows` and `GET /api/v1/workflows/{workflow_id}/versions`.

## Configuration and version selection

Definitions live in `configs/workflows/`; structural input schemas live in
`configs/input_schemas/`. Startup validates and snapshots each pair with a checksum. The
highest configured integer version is active until Phase 5 adds explicit activation. Changing
content under an existing version fails startup. Each accepted request remains pinned to its
persisted config version.

## Test

```powershell
.venv\Scripts\python.exe -m pytest -q
```

Integration tests use isolated temporary file-backed databases, including the concurrency
and worker restart cases; they do not use the developer's default database.

## Limitations

- Run one retry worker. Durable leases recover after a crash, but there is no lease heartbeat.
- A crash after a provider side effect and before local commit can repeat the provider call.
  Stable operation keys help only when the provider honors idempotency; exactly-once effects
  are not claimed.
- SQLite serializes writers and limits throughput. The demo adapter is deterministic, not a
  substitute for testing a real identity/vendor provider.
- Manual review is a holding outcome. Review resolution and explicit config activation are
  Phase 5 work.

## Project map

- `app/api/`: request, execution, status and workflow discovery endpoints
- `app/engine/`: existing Phase 2 config loader and pure rule engine
- `app/services/`: intake, snapshots, workflow orchestration and retry processing
- `app/adapters/`: provider contract and deterministic simulator
- `app/persistence/`: SQLAlchemy models, sessions and repositories
- `app/workers/`: one-shot persisted retry worker
- `configs/`: immutable workflow versions and per-version input schemas
- `tests/`: unit, integration and failure-path suites
- `docs/`, `project_management/`: architecture, decisions, evidence and handoff

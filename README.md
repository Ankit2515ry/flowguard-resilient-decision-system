# FlowGuard

FlowGuard is a configurable workflow decision platform. Phases 1-5 provide FastAPI, a
versioned YAML rule engine, SQLite-backed idempotent intake, explicit workflow execution,
audit and explanation APIs, manual review, explicit workflow version activation, an external
verification simulator, and persisted bounded retries. Requests are accepted first and
execute only when explicitly triggered.

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
$env:FLOWGUARD_ADMIN_TOKEN = "local-demo-token-change-me"
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

## Inspect explanations and audit history

Use the persisted read APIs:

```powershell
$requestId = $created.request_id
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/requests/$requestId/explanation" |
  ConvertTo-Json -Depth 10
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/requests/$requestId/audit" |
  ConvertTo-Json -Depth 10
```

Nonfinal states report `pending: true` and no final decision outcome. Explanations reuse
stored rule traces, stage results and provider attempts; rules are never re-evaluated under a
newer version. Audit responses contain only persisted events, ordered by per-request sequence.
Older events may have no stage field when that event did not record one.

## Manual review and admin authentication

Set the server-side `FLOWGUARD_ADMIN_TOKEN` before starting the API. Review queue reads and
privileged writes use `X-Admin-Token`. A valid token maps to fixed actor `demo-admin`; the
client cannot submit a reviewer identity. Do not commit a real credential. Example:

```powershell
$headers = @{ "X-Admin-Token" = $env:FLOWGUARD_ADMIN_TOKEN }
$queue = Invoke-RestMethod "http://127.0.0.1:8000/api/v1/reviews" -Headers $headers
$reviewId = $queue[0].request_id
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/api/v1/reviews/$reviewId/resolve" `
  -Headers $headers -ContentType "application/json" `
  -Body (@{ action = "APPROVE"; reason = "Documents checked" } | ConvertTo-Json)
```

Only pending `MANUAL_REVIEW` requests can be resolved. The action, reason, status, decision
and audit event commit together. Repeating the same action and reason is safe; a conflicting
resolution after finalization returns 409. Missing and incorrect tokens return 401 and 403.
If no token is configured, protected endpoints return 503. This shared demo credential is not
production identity management.

## Activate workflow versions

Activation persists in SQLite. A first-time database selects the highest validated version
once; later startup preserves its active selection and registers newly discovered versions as
inactive. Existing request pins and snapshots do not change. Score 710 passes loan v1's 700
threshold and is sent to review under v2's 720 threshold:

```powershell
$headers = @{ "X-Admin-Token" = $env:FLOWGUARD_ADMIN_TOKEN }
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/v1/admin/workflows/activate" `
  -Headers $headers -ContentType "application/json" `
  -Body (@{ workflow_id = "loan_approval"; version = 1 } | ConvertTo-Json)

$body = @{ workflow_id = "loan_approval"; data = @{ applicant = @{
  age = 24; monthly_income = 60000; credit_score = 710
} } } | ConvertTo-Json -Depth 8
$first = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/v1/requests" `
  -Headers @{ "Idempotency-Key" = "version-demo-v1" } -ContentType "application/json" -Body $body
$firstResult = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000$($first.status_url)/execute"

Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/v1/admin/workflows/activate" `
  -Headers $headers -ContentType "application/json" `
  -Body (@{ workflow_id = "loan_approval"; version = 2 } | ConvertTo-Json)
$second = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/v1/requests" `
  -Headers @{ "Idempotency-Key" = "version-demo-v2" } -ContentType "application/json" -Body $body
$secondResult = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000$($second.status_url)/execute"
$first.config_version; $firstResult.status; $second.config_version; $secondResult.status
```

Expected output: `1`, `APPROVED`, `2`, `MANUAL_REVIEW`. The first request remains pinned to
version 1. `GET /api/v1/workflows/loan_approval/versions` shows active selection. Repeating
the current activation is idempotent and creates no duplicate admin audit event. Unknown
resources return 404, invalid bodies return 422, and state conflicts return 409.

Definitions live in `configs/workflows/`; structural input schemas live in
`configs/input_schemas/`. Startup validates and snapshots each pair with a checksum. Changing
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
- SQLite schema creation is additive at startup; Alembic migration history is deferred.
- Admin authentication is a shared demo credential, not production identity management.

## Project map

- `app/api/`: request, execution, audit, explanation, review and workflow endpoints
- `app/engine/`: existing Phase 2 config loader and pure rule engine
- `app/services/`: intake, snapshots, workflow orchestration and retry processing
- `app/adapters/`: provider contract and deterministic simulator
- `app/persistence/`: SQLAlchemy models, sessions and repositories
- `app/workers/`: one-shot persisted retry worker
- `configs/`: immutable workflow versions and per-version input schemas
- `tests/`: unit, integration and failure-path suites
- `docs/`: architecture plus `REQUIREMENTS_TRACEABILITY.md` mapping assignment criteria to code/tests
- `project_management/`: phase tracking, decisions, verification evidence and handoff

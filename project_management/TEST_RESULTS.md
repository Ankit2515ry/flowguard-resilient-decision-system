# Test Results

## Phase 1 smoke verification

- Environment setup: `python -m venv .venv` — succeeded with Python 3.11.9.
- Install command: `.venv\Scripts\python.exe -m pip install -e ".[dev]"` — succeeded;
  editable package and dependencies installed in the project environment.
- Test command: `.venv\Scripts\python.exe -m pytest -q`
- Result at Phase 1: **1 passed, 1 warning**.
- Coverage: FastAPI `GET /health` returns HTTP 200 and `{"status":"ok"}` through the
  in-process HTTP client.
- Warning: upstream Starlette reports its TestClient/httpx deprecation; test succeeds.

## Phase 2 configuration and rule engine

- Command: `.venv\Scripts\python.exe -m pytest -q`
- Result: **27 passed, 1 warning**.
- Coverage includes all nine operators, nested `all`/`any`, missing fields, type mismatch,
  rule failure precedence, trace contents/config version, malformed and duplicate-key YAML,
  invalid operator/entry/stage reference/rule set, duplicate rule IDs, unreachable stage,
  unsupported cycle, immutable versions, loan score 710 version difference, vendor example
  evaluation, and the Phase 1 health endpoint.
- Warning: upstream Starlette reports its TestClient/httpx deprecation; the tests pass.
- No later-phase API, persistence, workflow execution or retry tests were added because those
  features are out of Phase 2 scope.

## Phase 3 persistence and request intake

- Final command: `.venv\Scripts\python.exe -m pytest -q`
- Result: **47 passed, 1 warning** (27 Phase 1/2 tests plus 20 Phase 3 integration tests).
- Additional command: `.venv\Scripts\python.exe -m compileall -q app tests` — passed.
- Phase 3 coverage: 202 intake and 200 idempotent replay; persisted status after session
  closure; atomic request/execution/audit records; required nested input/type validation;
  unknown workflow, missing key, malformed JSON and invalid UUID errors; 404 unknown request;
  same-key conflict; reordered-key canonical replay; different keys; active-version listing
  and request pinning; immutable snapshot checksum; foreign-key pragma; injected commit
  rollback; and two-thread duplicate submissions against a temporary file-backed SQLite DB.
- All API tests use a fresh temporary database. No test opens the default developer database.
- Final health/import check used `create_app(database_url="sqlite:///:memory:")` and
  FastAPI `TestClient` — HTTP 200, `{"status":"ok"}`.
- Final `git diff --check` — clean.
- Confirmed verification did not create the default developer `flowguard.db`.
- Warning remains the upstream Starlette TestClient/httpx deprecation.
- Deferred: workflow stage execution, decision creation, audit/status history endpoints,
  activation API, retries and external dependency calls.

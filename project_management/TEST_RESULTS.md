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

# Progress

## Current status

Phases 1 and 2 are complete and verified. The repository includes the FastAPI health route,
versioned YAML workflow loader, graph validation, pure rule engine and three example workflow
versions. Persistence, workflow stage execution, retry worker, intake API and review API have
not been implemented yet.

## Phase 1 evidence

- Workspace was initially empty apart from `.git`.
- Python available: 3.11.9.
- Created root `.venv` with Python 3.11.9; the `py` launcher was unavailable, so creation used
  `python -m venv .venv` after checking the interpreter version.
- `.venv\Scripts\python.exe -m pip install -e ".[dev]"` succeeded after package-index access
  was approved.
- `.venv\Scripts\python.exe -m pytest -q` passed the Phase 1 health test.
- README contains Windows PowerShell setup/run/test commands and VS Code selects `.venv`.

## Phase 2 evidence

- Added frozen Pydantic workflow definitions and safe YAML loading with duplicate-key,
  schema, stage, transition, rule, reachability, terminal-outcome and cycle validation.
- Added deterministic operators (`eq`, `ne`, `gt`, `gte`, `lt`, `lte`, `in`, `not_in`,
  `exists`) plus nested `all`/`any` and dot-path resolution.
- Added loan approval versions 1 and 2 (credit thresholds 700 and 720) and vendor approval v1.
- `.venv\Scripts\python.exe -m pytest -q` — **27 passed, 1 warning**. The warning is the
  upstream Starlette TestClient/httpx deprecation.
- No database, HTTP intake, orchestration, retries or persisted audit behavior was added.

## Next

Phase 3 is next, only when requested: SQLite/SQLAlchemy persistence and idempotent intake.
See `TASKS.md` and `HANDOFF.md` for exact scope.

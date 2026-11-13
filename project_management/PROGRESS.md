# Progress

## Current status

Phases 1, 2 and 3 are complete and verified. The current application provides FastAPI health,
configuration discovery, SQLite-backed request intake, idempotency, and status retrieval.
Workflow stage execution, decisions, audit reads, retries and review operations remain later
phase work.

## Phase 1 evidence

- Workspace started empty apart from `.git`.
- Python 3.11.9 and project-root `.venv` are available.
- Editable package/dev install succeeded in `.venv`.
- README includes PowerShell setup/run/test commands and VS Code selects the venv.

## Phase 2 evidence

- Added frozen Pydantic workflow definitions and safe YAML loading with graph, reference,
  operator and cycle validation.
- Added pure rule operators, nested groups, deterministic traces and loan/vendor examples.
- Phase 2 verification: 27 passed, 1 upstream Starlette deprecation warning.

## Phase 3 evidence

- Added SQLAlchemy 2 models for workflow requests, executions, audit events, decisions,
  retry jobs and immutable workflow config snapshots.
- SQLite enables foreign keys, UTC-aware timestamp conversion, a unique active config index,
  and serialized write transactions with `BEGIN IMMEDIATE`.
- Startup persists checksummed workflow+input-schema snapshots. The highest configured
  version is active until Phase 5 activation; changing an existing version's content fails
  startup.
- Added version-specific structural input schema files; business eligibility remains in
  workflow rule config.
- Added POST request, GET request status, GET workflows, and GET workflow versions APIs.
- New requests atomically create request+execution+initial audit at `RECEIVED`; there is no
  rule/stage execution or decision in this phase. A composite FK enforces that each request's
  pinned workflow/version snapshot exists.
- Final suite: `.venv\Scripts\python.exe -m pytest -q` — **47 passed, 1 warning**. Warning:
  upstream Starlette TestClient/httpx deprecation.
- File-backed concurrency test submits two simultaneous duplicate requests and verifies one
  request, one execution and one audit event (one 202, one 200 replay).
- Final `git diff --check` clean; temporary in-memory FastAPI `/health` smoke returned 200.

## Next

Phase 4 is next, only when requested: workflow state transitions, configured rule execution,
deterministic external dependency simulation, and persisted bounded retries. See `TASKS.md`
and `HANDOFF.md` for exact scope.

# Progress

## Current status

Phases 1-4 are complete and verified. FlowGuard accepts idempotent requests, executes
explicitly triggered pinned workflows, records transitions/traces/decisions, and resumes
persisted retries with a one-shot worker. Audit history and manual review/config activation
APIs remain Phase 5 work.

## Phase 1 evidence

- Python 3.11.9 and project `.venv` are available.
- Editable project/dev install succeeded in `.venv`.
- README includes PowerShell setup/run/test commands and VS Code selects the venv.

## Phase 2 evidence

- Frozen versioned workflow definitions, safe YAML loading, graph validation, pure rules and
  loan/vendor examples are implemented.
- Phase 2 verification: 27 passed, 1 upstream Starlette TestClient/httpx deprecation warning.

## Phase 3 evidence

- SQLAlchemy/SQLite request, execution, audit, decision, retry and configuration models are
  initialized with additive startup upgrades and UTC-aware timestamps.
- Request/execution/audit intake is atomic; idempotency, status, workflow and version APIs
  are implemented. Each request has a composite FK to its pinned config snapshot.
- Highest configured version remains the deterministic active version until Phase 5.

## Phase 4 evidence

- Added explicit `POST /api/v1/requests/{id}/execute`; intake still returns 202, idempotent
  replay 200, and conflicting replay 409.
- Executor verifies and loads the pinned immutable config, evaluates configured rule stages,
  resolves transitions from YAML, handles external/human/terminal stages, and holds
  MANUAL_REVIEW for Phase 5.
- Request and execution use a single legal lifecycle state; each state/stage change is
  transactionally audited. Rule traces, provider outcomes, and one decision are persisted.
- Added typed deterministic simulator scenarios (`SUCCESS`, `TEMPORARY_FAILURE`,
  `FAIL_THEN_RECOVER`, `PERMANENT_FAILURE`) controlled by server environment.
- Retries persist attempt count, next due UTC time, stable operation key, and claims. Max
  attempts includes initial call. A 120s lease supports expired-claim recovery; operation
  calls occur after DB transaction closure.
- Added one-shot CLI worker and an additive upgrade from the Phase 3 SQLite table shape.
- Regression and Phase 4 suite: **72 passed, 1 warning**. The warning remains the upstream
  Starlette TestClient/httpx deprecation.
- Documented API exercise: happy loan `RECEIVED -> APPROVED`; transient retry
  `RETRY_WAIT -> APPROVED`. Retry worker CLI is also exercised in a subprocess integration test.

## Next

Phase 5 is next, only when requested: audit/explanation APIs, review queue/resolution, and
explicit workflow configuration activation. See `TASKS.md` and `HANDOFF.md`.

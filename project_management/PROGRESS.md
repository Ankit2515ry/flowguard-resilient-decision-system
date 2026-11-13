# Progress

## Current status

Phases 1-6 are complete and verified. FlowGuard accepts idempotent requests, executes
explicitly triggered pinned workflows, exposes persisted audit/explanation, resolves manual
review atomically, persists admin version activation, and resumes bounded retries with a
one-shot worker.

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
- First-time database initialization selects highest configured version; later activation is
  persisted and preserved across application restarts.

## Phase 4 evidence

- Added explicit `POST /api/v1/requests/{id}/execute`; intake still returns 202, idempotent
  replay 200, and conflicting replay 409.
- Executor verifies and loads the pinned immutable config, evaluates configured rule stages,
  resolves transitions from YAML, handles external/human/terminal stages, and persists
  MANUAL_REVIEW for authorized Phase 5 resolution.
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

## Phase 5 evidence

- Added ordered persisted audit retrieval and deterministic explanation reads from stored
  traces/results. Nonfinal requests are explicitly pending; no rules are re-evaluated.
- Added admin-token-protected review queue and resolution. A fixed `demo-admin` actor is
  derived from the server credential. Review action/reason, status, unique Decision update
  and audit event commit atomically; identical resolution is replay-safe.
- Added persisted configuration activation and administrative audit rows. First initialization
  defaults to highest validated version, later starts preserve active selection, and newly
  discovered versions remain inactive. Old requests remain pinned.
- Added a 710 credit-score integration demonstration: loan v1 is approved; loan v2 enters
  MANUAL_REVIEW; v1 request remains pinned after the switch.
- Phase 5 tests: **85 passed, 1 warning**; compile and whitespace checks passed (see
  `TEST_RESULTS.md`).
- The health smoke test now uses in-memory SQLite; the final suite does not open the local
  `flowguard.db`. That ignored file contains one existing APPROVED request and was left intact
  because its ownership is uncertain.

## Phase 6 evidence

- Audited assignment requirements against implementation and existing test coverage; added
  `docs/REQUIREMENTS_TRACEABILITY.md` with code locations, named tests and limitations.
- Added six isolated failure tests for incorrect/unconfigured admin tokens, failed review and
  activation commits, newly discovered config version registration, and finalized execution
  replay. No production logic defect was confirmed, so runtime code was not changed.
- Original Phase 5 baseline: **85 passed, 1 warning**. Phase 6 final suite: **91 passed,
  1 warning**. The single warning remains Starlette's upstream TestClient/httpx deprecation.
- Tests use temporary or in-memory databases and do not use the developer's persistent DB.
- At-least-once external execution remains a documented limitation; see `DECISIONS.md` and
  `HANDOFF.md`.

## Next

Phase 7 is next, only when requested: final clean-environment verification and submission
readiness. See `TASKS.md` and `HANDOFF.md`.

# Handoff

## State

Phases 1-3 are complete. The project venv is Python 3.11.9. Phase 3 added SQLAlchemy/SQLite
records, startup schema/snapshot initialization, versioned structural input schemas, atomic
request/execution/audit creation, database-scoped idempotency, request status, and workflow
discovery APIs. The complete suite passed: 47 passed, 1 upstream Starlette deprecation
warning. See `TEST_RESULTS.md` for commands and coverage.

## Exact next phase (not started)

Phase 4 only after explicit instruction:

1. Define and enforce legal execution/request state transitions.
2. Orchestrate configured stages, using the existing rule engine without moving business rules
   into API controllers.
3. Keep external calls outside database transactions and use stable operation keys.
4. Implement the deterministic dependency simulator.
5. Persist bounded retry jobs and add a retry command or endpoint.
6. Add deterministic success, failure, retry, and recovery tests.

Do not add Phase 5 review/activation behavior or Phase 6 broad regression scope unless asked.

## Phase 3 contracts to preserve

- Unique `(workflow_id, idempotency_key)` is database-enforced. Canonical hash covers
  workflow ID + JSON data. Matching replay returns HTTP 200 and `Idempotency-Replayed: true`;
  changed payload returns 409.
- Request + execution + initial audit record commit atomically in state `RECEIVED`.
- A request pins a persisted, checksummed `(workflow_id, config_version)` snapshot.
- Until activation is added, highest configured version is selected at application startup.
- SQLite foreign keys are on; writes use `BEGIN IMMEDIATE`. Concurrency verification used a
  temporary file-backed SQLite database and two simultaneous client submissions.
- Tests must use isolated temporary databases, never the default `flowguard.db`.

## Known limitations / unresolved defects

- No known Phase 3 defects.
- Phase 3 intentionally does not execute stages, evaluate rules for requests, create decisions,
  expose audit history, retry dependencies, or provide explicit config activation.
- SQLite serializes writers and is a single-process MVP store; move to a server DB/leased job
  claim design only when scaling requirements warrant it.
- Schema is initialized through SQLAlchemy `create_all`; Alembic migrations are deferred.
- The suite reports the existing upstream Starlette TestClient/httpx deprecation warning.

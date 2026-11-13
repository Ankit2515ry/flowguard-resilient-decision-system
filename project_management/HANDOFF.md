# Handoff

## State

Phases 1 and 2 are complete. A project-root `.venv` using Python 3.11.9 is installed and
ready. The FastAPI `/health` route remains intact. `app.engine.config` loads and validates
immutable YAML workflow definitions; `app.engine.rules` evaluates rule sets and returns
deterministic traces. The three example versions are under `configs/workflows/`. The full
suite passed: 27 passed, with one upstream Starlette deprecation warning (see
`TEST_RESULTS.md`).

## Exact next phase (not started)

Phase 3: introduce SQLAlchemy 2/SQLite persistence records and repository transaction scopes;
implement request creation with required Idempotency-Key and canonical request hashing;
enforce uniqueness on `(workflow_id, idempotency_key)` in the database; return existing
requests for equivalent replays and 409 for same-key/different-payload; add request API and
integration/failure tests. Preserve config version IDs for later request pinning. Do not
begin Phase 3 until explicitly requested.

## Known limitations / unresolved defects

- No known Phase 1 or Phase 2 defects.
- Persistence, request intake, workflow execution, audit storage, retry handling and review
  operations remain unimplemented and must not be presented as complete.
- Rule evaluation raises `RuleEvaluationError` for incompatible operand types; API error
  mapping will be defined in a later phase.
- Retry processing, when implemented, will initially assume one worker process; multi-worker
  claiming/leases and exactly-once external side effects are outside the MVP contract.

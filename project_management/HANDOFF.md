# Handoff

## State

Phases 1-4 are complete. Intake remains explicit and idempotent; `POST /api/v1/requests/{id}/execute`
walks the pinned workflow and persists lifecycle state, audit events, rule traces, decisions,
and retry jobs. The suite passes: 72 passed, 1 upstream Starlette TestClient/httpx warning.
See `TEST_RESULTS.md` for exact commands and evidence.

## Exact next phase (not started)

Phase 5 only after explicit instruction:

1. Add `GET /api/v1/requests/{id}/audit` with ordered events and stable response schemas.
2. Add `GET /api/v1/requests/{id}/explanation`, returning persisted decision, pinned config
   version and rule trace evidence.
3. Add review queue and `POST /api/v1/reviews/{id}/resolve` with legal MANUAL_REVIEW
   transitions, atomic decision update and audit append. Preserve one Decision per request;
   update the held decision or deliberately revise the uniqueness contract before resolution.
4. Add explicit workflow version activation/rollback; never edit an existing persisted
   workflow/config snapshot to represent a rule change.
5. Add temporary-database tests for audit/explanation reads, review outcomes, and activation
   while verifying that in-flight requests remain pinned.

Do not begin Phase 6 broad failure/regression scope until Phase 5 is done and requested.

## Phase 4 contracts to preserve

- POST request intake stays storage-only and returns 202; equivalent idempotent replay stays
  200; conflicting replay stays 409.
- Execution is an explicit trigger. Request/execution statuses remain canonical and state
  changes plus audit events commit atomically.
- Existing rule engine/config loader remain the source of business rules and transitions.
  Execution uses the request's exact checksummed pinned snapshot.
- HUMAN_TASK follows its configured MANUAL_REVIEW transition to a holding state. No review
  resolution is currently available.
- `max_attempts` includes the first call. The worker is one-shot and reclaims expired durable
  leases. Provider calls are outside DB transactions and use stable operation keys.
- Tests use temporary SQLite databases. Do not run integration tests against `flowguard.db`.

## Known limitations / unresolved defects

- No known Phase 4 defects.
- The simulator is deterministic and server-configured; real provider behavior is not covered.
- SQLite uses `BEGIN IMMEDIATE`, serializing transactions and limiting throughput.
- Only one retry worker process is supported. Leases have no heartbeat; calls exceeding the
  lease can be repeated. A crash after provider success but before local commit can repeat a
  call, so exactly-once external effects are not claimed.
- Audit/explanation REST endpoints, manual review resolution, explicit config activation,
  human review UI, and production Alembic migrations remain Phase 5 or later.
- The test run still reports the upstream Starlette TestClient/httpx deprecation warning.

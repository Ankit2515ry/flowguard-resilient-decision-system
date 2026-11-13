# Handoff

## Verified state

Phases 1-5 are implemented. Phase 5 adds ordered audit and explanation APIs, admin-token
protected review listing/resolution, and persistent workflow version activation. The full
suite currently reports 85 passed, one upstream Starlette TestClient/httpx deprecation
warning; final commands/results are recorded in `TEST_RESULTS.md`.

Important contracts: intake remains 202 for new requests and 200 for equivalent replay;
execution is explicit; every state change is audited atomically; requests retain their pinned
config version; review updates the existing unique Decision; and only the server-configured
admin token establishes the fixed `demo-admin` actor. Startup preserves the active version
after first initialization and registers newly found versions inactive.

## Exact next work (Phase 6, not started)

Proceed only after an explicit Phase 6 request:

1. Expand deterministic failure/regression coverage across malformed and changed config,
   provider exceptions/permanent failures, retry exhaustion/recovery, duplicate and concurrent
   intake/execution/review actions, invalid lifecycle transitions, and activation pinning.
2. Keep each test on an isolated temporary SQLite database; never use the local `flowguard.db`.
3. Fix only defects demonstrated by tests while preserving Phase 1-5 endpoint and persistence
   contracts.
4. Run the full suite and required compile/whitespace checks; record exact outcomes and any
   unresolved defects in project memory.

Phase 7 remains after Phase 6: final README/evidence review, fresh-environment verification,
known-limitations summary and submission readiness.

## Known limitations

- Admin authorization is a shared demo token mapped to one fixed actor, not production
  authentication or role-based access control. The review queue is protected by this token;
  audit and explanation reads remain request-ID scoped demo endpoints.
- SQLite uses `BEGIN IMMEDIATE` and serializes writers; only one retry worker process is
  supported. Retry/execution leases have no heartbeat.
- A crash after provider success but before local commit can repeat an external call.
  Exactly-once external effects are not claimed.
- Audit stage fields can be null for historical events that did not persist a stage reference.
- Alembic migration history, a human reviewer UI, and production identity integration remain
  out of scope.
- The suite reports one upstream Starlette TestClient/httpx deprecation warning.
- An ignored `flowguard.db` exists locally with one APPROVED request and three workflow config
  snapshots. It was inspected read-only after a test-isolation leak was found and fixed; the
  final suite no longer opens it. Ownership of that row is uncertain, so inspect/backup before
  any cleanup. Never delete it automatically.

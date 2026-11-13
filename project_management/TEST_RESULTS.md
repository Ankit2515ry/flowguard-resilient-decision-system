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

## Phase 4 workflow execution and retries

- Final regression command: `.venv\Scripts\python.exe -m pytest -q`
- Result: **72 passed, 1 warning** (47 baseline tests plus 25 Phase 4 tests).
- Additional checks: `.venv\Scripts\python.exe -m compileall -q app tests` — passed;
  `git diff --check` — passed.
- Health import/smoke: in-memory SQLite `create_app` + FastAPI TestClient returned HTTP 200
  and `{"status":"ok"}`.
- Demo HTTP flows: loan request `RECEIVED -> APPROVED`; simulated transient failure
  `RETRY_WAIT -> APPROVED` after one due retry. These were exercised with temporary
  in-memory SQLite databases and a controlled due time, without sleeping.
- Worker CLI was run from an integration test as
  `.venv\Scripts\python.exe -m app.workers.retry_worker --once` against a temporary file DB;
  it processed one persisted due job and completed the request as APPROVED in a new process.
- Coverage includes rule rejection/manual review, vendor approval, pinned loan v1/v2 behavior,
  immediate/permanent/transient provider outcomes, recovery/exhaustion, stable operation keys,
  duplicate execution, concurrent execution trigger, status/audit/trace consistency, external
  call transaction boundary, commit rollback, restart/expired-lease recovery, additive SQLite
  upgrade, missing request, invalid stage/transition, and max-attempt/backoff semantics.
- Warning: upstream Starlette TestClient reports the existing httpx deprecation.
- Phase 5 remains deferred: audit/explanation read endpoints, review resolution, and explicit
  config activation are not implemented.

## Phase 5 audit, review and activation

- Final full regression command: `.venv\Scripts\python.exe -m pytest -q`
- Result: **85 passed, 1 warning** (72 prior tests plus 13 Phase 5 integration tests).
- Compile command: `.venv\Scripts\python.exe -m compileall -q app` — passed.
- Whitespace command: `git diff --check` — passed; Git printed LF-to-CRLF normalization
  notices for changed files, with no whitespace errors.
- `tests/integration/test_phase5_api.py` uses a unique temporary file-backed SQLite DB per
  test and a test-only admin credential. Coverage includes ordered approval audit, rule and
  external events, retry schedule/processing/recovery, unknown request 404, approved/rejected/
  pending/retry explanations, review approve/reject, auth, idempotent replay, conflicts,
  concurrent opposing reviewers, loan v1/v2 activation with score 710, request pin retention,
  restart persistence, invalid version and snapshot corruption, activation idempotency, and
  admin event actor/version records.
- A real in-process HTTP integration flow verifies loan v1 score 710 -> APPROVED, loan v2
  score 710 -> MANUAL_REVIEW, and the original request remains pinned to v1.
- Warning remains the upstream Starlette TestClient/httpx deprecation warning.
- The first Phase 5 full-suite attempt exposed that the health test still used the module-level
  app and opened the default `flowguard.db`. `tests/integration/test_health.py` now creates an
  in-memory app. All Phase 6 test fixtures use an in-memory or `tmp_path` database URL.
  Read-only inspection found one APPROVED request and three config snapshots in the ignored
  local file; ownership is uncertain, so it was left untouched rather than deleted.
- Phase 6 broad failure/regression scope remains not started.

## Phase 6 robustness audit and failure paths

- Original test baseline: **85 passed, 1 warning**. Added six deterministic failure/integration
  cases; final result: **91 passed, 1 warning**.
- New test file: `tests/failure/test_phase6_failure_paths.py`. Its targeted run passed **6/6**.
  Cases cover wrong and unconfigured admin credentials, atomic rollback after review and
  activation commit failures, newly discovered versions remaining inactive, and repeated
  execution of a finalized request preserving one decision and unchanged audit history.
- Existing tests were audited for invalid schema, idempotency conflict/replay, concurrent
  submissions, dependency timeouts/permanent failures, retry recovery/exhaustion, worker
  process restart/expired lease, partial intake/execution DB failures, activation restart and
  version pinning, manual review conflict/concurrency, and audit/explanation consistency.
- Requirement mapping: `docs/REQUIREMENTS_TRACEABILITY.md`.
- Confirmed runtime defect: none. Remaining at-least-once provider limitation is documented;
  local transactions cannot undo an external side effect after a crash.
- Final commands:
  `.venv\Scripts\python.exe -m pytest -q` — 91 passed, 1 warning;
  `.venv\Scripts\python.exe -m compileall -q app` — passed;
  `git diff --check` — passed with LF-to-CRLF normalization notices and no whitespace errors.
- The final health test uses an in-memory database. The local ignored `flowguard.db` remains
  outside test fixtures and is not used by test cases; its ownership remains uncertain (see
  `HANDOFF.md`).

## Phase 7 final submission verification

- `.venv\Scripts\python.exe --version` — Python 3.11.9.
- Initial editable install was blocked by sandbox network restrictions while pip attempted to
  download isolated build requirements. Retried with approved network access:
  `.venv\Scripts\python.exe -m pip install -e ".[dev]"` — succeeded; FlowGuard and dev
  dependencies were installed/confirmed in `.venv`.
- `.venv\Scripts\python.exe -m pytest -q` — **91 passed, 1 upstream deprecation warning**.
- `.venv\Scripts\python.exe -m compileall -q app` — passed.
- `git diff --check` — passed; Git emitted LF-to-CRLF normalization notices only.
- Isolated in-process FastAPI smoke used `create_app(database_url="sqlite:///:memory:")`:
  `/health` returned 200 with `{"status":"ok"}`, `/docs` returned 200, `/openapi.json`
  returned 200 with 11 paths, request intake returned 202, and explicit execution returned
  200 with `APPROVED`. The persistent developer database was not used.
- A GitHub remote is not configured; GitHub publishing and email submission were not
  performed. See `docs/SUBMISSION_CHECKLIST.md` for manual steps and blockers.
- Hygiene review: `.gitignore` excludes `.venv`, `.env` (except the blank `.env.example`),
  SQLite database/WAL/SHM/journal files, Python/test/tool caches, and common secret/key files.
  No tracked local database or `.env` was found. Credential-pattern matches were limited to
  clearly labeled local-demo/test-only placeholder tokens; no real credential or local
  absolute Windows path/personal name was found in final-facing docs.
- Git state: branch `main`, base commit `2633a26`, no configured remote. Phase 7 working-tree
  changes are documentation and project memory; they remain uncommitted for owner review.

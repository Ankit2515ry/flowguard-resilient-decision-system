# Task Tracking

## Phase 1 - scaffold and architecture

- [x] Inspect workspace and Python environment (empty repository; Python 3.11.9 available).
- [x] Add package metadata, runtime/dev dependencies and pytest configuration.
- [x] Create modular app and test package directories.
- [x] Add FastAPI application and `/health` endpoint.
- [x] Add environment example and safe ignore rules.
- [x] Add architecture, HLD, LLD and tradeoff documents.
- [x] Add repository instructions and project memory files.
- [x] Add README setup/run/test instructions.
- [x] Run health smoke test and record result.

## Phase 2 - configuration and rule engine

- [x] Define versioned workflow YAML format and frozen Pydantic validation models.
- [x] Implement safe loader with duplicate YAML key detection and descriptive errors.
- [x] Validate rule/stage uniqueness, references, stage-specific transitions, terminal outcomes,
  reachability and acyclic workflow graphs.
- [x] Implement declarative operators and nested all/any evaluation with traces.
- [x] Define missing-field, type mismatch, and failure precedence behavior.
- [x] Add loan approval v1/v2 and vendor approval v1 examples.
- [x] Add deterministic configuration/rule tests and preserve the health test.
- [x] Run the complete test suite and record results.

## Phase 3 - persistence and request intake

- [x] Add SQLAlchemy 2 models for requests, executions, audit events, decisions, retry jobs,
  and workflow config snapshots.
- [x] Add SQLite session lifecycle, foreign-key enforcement and UTC timestamp handling.
- [x] Persist validated versioned config snapshots/checksums with deterministic first-start
  selection and later explicit activation.
- [x] Add version-specific structural input schemas.
- [x] Implement atomic request/execution/initial-audit intake with scoped database
  idempotency and canonical payload hashing.
- [x] Add request POST/status and workflow list/version endpoints with structured errors.
- [x] Test API validation, persistence, replay, conflict, rollback, config pinning and
  controlled file-backed concurrent duplicate submissions.
- [x] Run full regression suite and final health/import checks.

## Phase 4 - orchestration and retries

- [x] Implement canonical request/execution states and legal transition validation.
- [x] Add explicit repeat-safe execution trigger; preserve POST intake behavior.
- [x] Execute pinned YAML rule, external, human-task and terminal stages without hardcoding
  business eligibility rules.
- [x] Persist traces, stage results, decisions and ordered audit events transactionally.
- [x] Add typed provider contract and deterministic success/temporary/recovery/permanent
  simulator scenarios configured server-side.
- [x] Add stable external operation keys and bounded persisted retries with exponential
  backoff; first provider attempt counts toward max_attempts.
- [x] Add durable execution/retry leases and expired-claim recovery.
- [x] Add one-shot retry CLI and additive Phase 4 SQLite schema upgrade.
- [x] Add deterministic execution, rollback, concurrency, worker restart, and provider
  transaction-boundary tests.
- [x] Run the existing 47-test baseline plus Phase 4 tests and execute demo flows.

## Phase 5 - audit, review and configuration activation

- [x] Add ordered persisted audit and stored-decision explanation read APIs.
- [x] Add admin-protected review queue and atomic, replay-safe manual review resolution.
- [x] Add persisted workflow version activation and preserve active selection across restarts.
- [x] Preserve immutable request pins and record administrative activation events.
- [x] Add deterministic isolated HTTP integration tests for audit, explanation, retries,
  review authorization/replay/conflict/concurrency, activation, restart and version pinning.
- [x] Update operator/API docs, examples and project memory.
- [x] Run the full suite, compile check and whitespace check; see `TEST_RESULTS.md`.

## Phase 6 - failure and regression coverage (not started)

- [ ] Expand broad failure/integration/regression coverage for malformed configs, provider
  failures, duplicate requests, retry recovery, invalid lifecycle state and config changes.
- [ ] Fix defects evidenced by those failure tests; preserve Phase 1-5 contracts.
- [ ] Record exact verification and unresolved defects before Phase 7.

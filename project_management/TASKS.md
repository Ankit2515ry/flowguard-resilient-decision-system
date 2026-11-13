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

## Phase 3 - next (not started)

- [x] Add SQLAlchemy 2 models for requests, executions, audit events, decisions, retry jobs,
  and workflow config snapshots.
- [x] Add SQLite session lifecycle, foreign-key enforcement and UTC timestamp handling.
- [x] Persist validated versioned config snapshots/checksums; select the highest configured
  version deterministically until explicit activation exists.
- [x] Add version-specific structural input schemas.
- [x] Implement atomic request/execution/initial-audit intake with scoped database
  idempotency and canonical payload hashing.
- [x] Add request POST/status and workflow list/version endpoints with structured errors.
- [x] Test API validation, persistence, replay, conflict, rollback, config pinning and
  controlled file-backed concurrent duplicate submissions.
- [x] Run full regression suite and final health/import checks.

## Phase 4 - next (not started)

- [ ] Implement legal workflow state transitions and stage orchestration.
- [ ] Execute configured rule evaluation stages using the existing pure rule engine.
- [ ] Add deterministic external dependency simulator and stable operation keys.
- [ ] Persist bounded retry jobs and provide a retry processing command or endpoint.
- [ ] Add integration/failure tests for execution, dependency failures and retries.

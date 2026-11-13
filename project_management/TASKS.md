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

- [ ] Add SQLite/SQLAlchemy models and repository/transaction boundaries.
- [ ] Implement request intake with required Idempotency-Key and canonical payload hash.
- [ ] Enforce `(workflow_id, idempotency_key)` uniqueness in the database.
- [ ] Add request creation/status endpoint and idempotency integration/failure tests.

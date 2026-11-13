# FlowGuard Master Plan

## Objective

Build a runnable, configurable workflow decision platform using Python 3.11+, FastAPI,
Pydantic v2, SQLAlchemy 2, SQLite, YAML, and pytest. The MVP exposes Swagger UI and does
not require a separate frontend or distributed infrastructure.

## Phase sequence and timebox

1. **Repository scaffold, architecture, tracking** — 30 min. Complete; smoke test verified.
2. **Configuration and rule engine** — 60 min. Load/validate immutable YAML versions;
   implement deterministic safe operators and traces. Complete; 27 tests passed.
3. **Database, intake API, idempotency** — 70 min. Persistence models and atomic uniqueness;
   canonical payload hash and conflict behavior. Complete; Phase 3 evidence in `TEST_RESULTS.md`.
4. **Workflow orchestration and retries** — 65 min. Legal state transitions, stage execution,
   deterministic dependency simulator, persisted bounded retry worker. Complete; regression
   suite has 72 passing tests.
5. **Audit, manual review, configuration changes** — 45 min. Atomic state/audit writes,
   decision explanations, review API and activation/version behavior.
6. **Failure and integration tests, regression fixes** — 50 min. Cover retry, dependency,
   duplicate, invalid config and rule-change paths.
7. **README, evidence, verification, submission** — 40 min. Full operator docs, clean setup,
   final verification and known limitations.

## Release acceptance

Implement the API targets in the product brief, validate the full configured workflow graph
before activation, pin each request to its starting config version, and pass unit,
integration, failure and smoke tests. Every externally visible state change must be auditable.

## Deadline priorities

Correctness, deterministic behavior, idempotency, auditability, configuration validation,
and test evidence take precedence over deployment infrastructure and optional features.

## Current handoff

Phases 1-4 are complete. Phase 5 audit/explanation reads, manual review resolution, and
configuration activation is next but has not started; proceed only after explicit user
instruction.

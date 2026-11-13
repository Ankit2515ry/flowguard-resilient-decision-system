# Handoff

## State

Phase 1 scaffold and documents are complete. Editable installation succeeded, and the only
implemented runtime behavior is `GET /health`. Swagger UI is available at `/docs` when the
server is running. The smoke test passed in the current Python 3.11.9 environment (with one
upstream Starlette deprecation warning; see `TEST_RESULTS.md`).

## Exact next phase

Phase 2: define Pydantic v2 models for workflow configs and rules; add YAML examples for
loan approval v1/v2 and vendor approval; implement safe operator evaluation (`eq`, `ne`,
`gt`, `gte`, `lt`, `lte`, `in`, `not_in`, `exists`, `all`, `any`) with deterministic traces;
reject invalid/incompatible expressions; validate stage references and the complete graph;
test version pinning/config behavior where possible. Do not begin database/intake work from
Phase 3 until Phase 2 is complete and the user asks to proceed.

## Known limitations / unresolved defects

- There are no known Phase 1 defects.
- Runtime features described in the product goal are intentionally unimplemented and must
  not be presented as complete.
- A clean isolated virtual environment install was not exercised; the editable install was
  performed in the current interpreter.
- Retry processing will initially assume one worker process; multi-worker claiming/leases
  and external side-effect exactly-once guarantees are outside the MVP contract.

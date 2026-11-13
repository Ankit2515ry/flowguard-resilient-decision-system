# Low-Level Design

## Rule evaluation contract

Each rule is data: identifier, field/path, allowlisted operator, expected operand and optional
composition (`all`/`any`). Resolve paths without executing expressions. Validate operand types
against actual values and operator requirements. Emit stable ordered trace entries containing
rule ID, actual value, expected value, pass/fail, reason and config version. Invalid syntax or
incompatible types is a configuration error, never an implicit false decision.

## Workflow contract

Represent stages by stable IDs and one of `RULE_EVALUATION`, `EXTERNAL_CALL`, `HUMAN_TASK`, or
`TERMINAL`. Validate referenced targets and graph reachability/termination before activation.
Use an explicit transition table for success, reject, manual review, technical failure,
retry waiting and terminal outcomes. Pin the chosen config version on the request row.

## Idempotent intake

Normalize structured request data to canonical JSON (stable key ordering and defined numeric
serialization), hash with SHA-256, and insert under a unique `(workflow_id, idempotency_key)`
constraint. On uniqueness conflict, compare hashes: equal means return the stored request;
different means HTTP 409. Handle races by relying on the database constraint, not a prior
read alone.

## Persistence and atomicity

Use SQLAlchemy 2 typed mappings and short explicit transaction scopes. For every transition,
update execution/request state and append its audit event in the same commit. Store decision
and retry rows in that transaction when produced. External calls occur between transactions.

## Retry worker

Select due jobs, process with a bounded attempt policy, and update job plus workflow/audit
state transactionally. Stable operation key is derived from request, stage and operation
identity. The initial worker is single-process; without leases, running multiple workers is
unsupported. On restart, due persisted jobs can resume. A crash around external side effects
can repeat a call.

## HTTP mapping

Pydantic validation errors map to 422; absent resources to 404; idempotency hash mismatch to
409; invalid workflow config to a client-visible validation error; unexpected failures to
500 with internal details kept out of the public response and captured in logs/audit as
appropriate.

# Low-Level Design

## Rule evaluation contract

Each rule is data: identifier, condition and failure action (`REJECT` or `MANUAL_REVIEW`). A
condition is either a field test (`field`, `operator`, `value`) or a non-empty nested `all` or
`any` group. Field paths use dot notation. Supported operators are `eq`, `ne`, `gt`, `gte`,
`lt`, `lte`, `in`, `not_in`, and `exists`. `exists` requires an explicit boolean value, so an
optional field can be required (`true`) or forbidden (`false`).

Missing fields fail ordinary comparisons with an explicit trace reason; they are never skipped.
An absent field is distinguishable from a present field whose value is null through `exists`.
Incompatible actual/expected types raise `RuleEvaluationError` instead of being converted to a
business decision. Numeric integers and floats are comparable; booleans are not numbers for
this purpose. Conditions in a group and rules in a set are all evaluated in declaration order
to produce complete traces. If multiple rules fail, `REJECT` takes precedence over
`MANUAL_REVIEW` independent of order. Trace entries report rule ID, expression reference,
operator, actual/expected value, pass/fail, failure action, reason and configuration version.

## YAML workflow shape

A file contains `workflow_id`, positive integer `version`, `entry_stage`, `rule_sets`, `stages`,
and `transitions`. Stages are typed as `RULE_EVALUATION`, `EXTERNAL_CALL`, `HUMAN_TASK`, or
`TERMINAL`. Rule evaluation stages name a rule set; external stages name an operation;
terminal stages declare one of `APPROVED`, `REJECTED`, or `MANUAL_REVIEW`. A transition is
`from_stage` + `outcome` + `to_stage`. The loader rejects duplicate YAML keys, IDs, missing
references, invalid event/type combinations, unreachable nodes, and every directed cycle.
Cycles are unsupported in this MVP, so there are no exceptions to the acyclic graph rule.
Definitions use frozen Pydantic models and tuple collections; loaded config versions are
returned in a read-only mapping keyed by `(workflow_id, version)`.

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

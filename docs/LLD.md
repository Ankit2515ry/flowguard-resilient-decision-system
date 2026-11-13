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

Phase 3 creates the schema with SQLAlchemy metadata at startup; Alembic is deferred. Each
request transaction inserts `WorkflowRequest`, its one-to-one `WorkflowExecution`, and audit
sequence 1 together. UTC-aware application timestamps are normalized by a SQLAlchemy type
adapter because SQLite does not retain timezone metadata. SQLite foreign keys are enabled on
every connection. The test suite uses a separate temporary SQLite file per app instance.

Idempotency hashes canonical JSON containing `workflow_id` and `data` (`sort_keys=True`,
compact separators, UTF-8, non-finite numbers rejected). `config_version` is deliberately
excluded so a retry after an active-version change resolves to its already accepted request.
The database unique key is `(workflow_id, idempotency_key)`. A new request and execution are
created at `RECEIVED`, with the configured entry stage recorded but not executed. New intake
returns 202; same-hash replay returns 200 and the current stored state; changed-payload replay
returns 409. A composite foreign key from `(workflow_id, config_version)` to the immutable
workflow snapshot prevents requests from pinning an absent version.

## Retry worker

`RetryPolicy.max_attempts` includes the initial external attempt. For attempt `n` that fails,
the next delay is `min(max_delay, base_delay * 2^(n-1))`. Provider calls return typed success,
retryable, category and message fields. Unexpected adapter exceptions become retryable
technical failures; they never become rule rejection.

The executor claims work by committing a lease token before stage processing. RetryJob records
are unique per execution/stage and operation key. Due PENDING or expired CLAIMED jobs are
claimed transactionally. A retry transitions RETRY_WAIT to PROCESSING, then calls the adapter
outside the transaction. Success or fallback transition and retry-job completion commit
together. Lease expiry allows recovery after worker restart; stable operation keys permit
provider-side deduplication. No heartbeat or distributed exactly-once guarantee is provided.

The initial and retry worker each use fresh SQLAlchemy sessions for every DB transaction and
never pass a session to a provider. Only one retry worker process is supported.

## Lifecycle and audit

`RECEIVED -> PROCESSING`; `PROCESSING -> APPROVED | REJECTED | MANUAL_REVIEW | RETRY_WAIT |
FAILED`; `RETRY_WAIT -> PROCESSING | FAILED`; and an authorized reviewer can transition
`MANUAL_REVIEW -> APPROVED | REJECTED`.
Status changes update request and execution together and append the next per-request audit
sequence in the same transaction. Stage-only movement is recorded as an event with the state
unchanged. A held MANUAL_REVIEW decision is updated in place when resolved so one Decision
per request remains enforced. Its explanation retains pinned version, traces, stage results
and external categories.

`GET /requests/{id}/audit` returns only append-only rows in sequence order. Config version is
read from the request pin; stage comes from persisted event details and may be null for older
events. Explanation output reads the stored Decision and execution context. It never re-runs
rules; nonfinal states return `pending: true` and a null final outcome.

Review queue reads and privileged writes use environment-configured `X-Admin-Token`. The demo
token maps to a fixed actor; clients cannot choose `reviewer_id`. SQLite `BEGIN IMMEDIATE`
serializes reviewer actions. Same action/reason is an idempotent replay; a different final
action returns 409. Request/execution status, Decision update and audit append share one
transaction.

Workflow activation validates the stored snapshot checksum, workflow graph and input schema.
One transaction switches the active marker and writes an admin audit record; a partial unique
index enforces one active version. Startup selects highest only for a workflow with no active
row, while newly discovered versions are inactive. Selection survives restart and existing
requests keep their pinned version.

## HTTP mapping

Pydantic validation errors map to 422; absent resources to 404; idempotency hash mismatch to
409; invalid workflow config to a client-visible validation error; unexpected failures to
500 with internal details kept out of the public response and captured in logs/audit as
appropriate.

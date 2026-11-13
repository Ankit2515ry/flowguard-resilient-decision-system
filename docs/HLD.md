# High-Level Design

## Runtime flow (target architecture)

```mermaid
sequenceDiagram
  participant C as Client
  participant A as FastAPI
  participant S as Intake/Workflow Service
  participant R as SQLite Repositories
  participant E as Rule/Workflow Engine
  participant X as Dependency Adapter
  C->>A: POST request + Idempotency-Key
  A->>S: validated command
  S->>R: resolve idempotency + pin active config
  R-->>S: existing request or new request/version
  S->>E: evaluate rules and stages
  E-->>S: outcome + ordered trace
  S->>X: external check (outside DB transaction)
  X-->>S: success or retryable failure
  S->>R: persist transition, audit, decision/retry atomically
  S-->>A: request status and decision
  A-->>C: response
```

The sequence describes the intended complete platform; in Phase 1 only the API process and
health route exist. Later implementation may split intake persistence and stage execution
into multiple short transactions around external calls.

## Data records (planned)

Workflow configuration/version, request, execution, decision, audit event, retry job and,
if needed, external operation record. Relational constraints enforce idempotency and useful
referential integrity. Audit events record actor/source, transition, timestamp, config
version and relevant trace/metadata.

## State and decision outcomes

Business outcomes include approved/success, rejected, and manual review. Operational states
include in progress, retry waiting, technical failure, and terminal completion. The workflow
state machine explicitly defines allowed edges; API handlers do not mutate state directly.

## API surface (target)

`POST /api/v1/requests`, request status/audit/explanation reads, workflow list/version reads,
admin activation, review queue/resolve, retry processing, and `GET /health`. FastAPI Swagger
UI is the initial operator/client interface.

## Reliability boundary

The MVP assumes one application/retry worker against SQLite. Persisted retries survive
process restart, but a crash after an external side effect and before local commit can repeat
the call. Stable operation keys and an idempotent simulator reduce that risk; true exactly
once behavior requires cooperation from the dependency.

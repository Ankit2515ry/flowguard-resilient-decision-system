# Tradeoffs and Constraints

- **SQLite over a server database:** fast setup and reliable local transactions fit the
  deadline. Phase 3 uses `BEGIN IMMEDIATE` to make scoped idempotency races deterministic;
  writers are serialized, so throughput and horizontal scaling are limited.
- **Synchronous FastAPI plus persisted retry worker:** fewer moving parts than a queue stack.
  The MVP assumes one retry worker; durable leases recover expired work, but throughput and
  distributed claiming remain limited.
- **Declarative YAML:** workflow edits are reviewable and versionable. It requires strict
  validation and does not provide arbitrary user code, by design.
- **Immutable config versions:** history and in-flight behavior are reproducible, at the cost
  of storing more versions and explicit activation bookkeeping.
- **Simulated dependency:** deterministic evaluation and retry tests are possible without
  secrets or third-party availability. It does not prove real-provider behavior.
- **Swagger UI instead of frontend:** allows API exploration quickly, with less polished
  end-user experience.
- **Alembic deferred:** avoid migration overhead for the initial schema. If schema evolution
  becomes material, add versioned migrations before production use.
- **Automatic highest-version selection:** Phase 3 selects the highest valid version at app
  startup until explicit activation is implemented. This is deterministic and simple, but
  operators cannot pin a rollback through an activation API yet.
- **Exactly-once side effects are not promised:** a crash between dependency success and local
  commit can cause a retry. Stable operation keys help only when the dependency honors them.
- **Lease recovery has no heartbeat:** execution/retry claims expire after a configured
  interval. Provider calls must normally finish before that interval; a longer call can be
  repeated after lease expiry, using the same stable operation key.
- **Max attempts include attempt one:** the first external call consumes one configured
  attempt, making the number of scheduled retries `max_attempts - 1` at most.

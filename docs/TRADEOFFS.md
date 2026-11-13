# Tradeoffs and Constraints

- **SQLite over a server database:** fast setup and reliable local transactions fit the
  deadline. Write concurrency and horizontal scaling are limited.
- **Synchronous FastAPI plus persisted retry worker:** fewer moving parts than a queue stack.
  The MVP assumes one worker; throughput and distributed job claiming are limited.
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
- **Exactly-once side effects are not promised:** a crash between dependency success and local
  commit can cause a retry. Stable operation keys help only when the dependency honors them.

"""SQLite engine, foreign-key setup, and SQLAlchemy session lifecycle."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy import inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.persistence.models import Base


def default_database_url() -> str:
    return os.getenv("FLOWGUARD_DATABASE_URL", "sqlite:///./flowguard.db")


class Database:
    """Own an engine and session factory; tests should pass a temporary file URL."""

    def __init__(self, url: str | None = None):
        self.url = url or default_database_url()
        options: dict = {"future": True, "pool_pre_ping": True}
        if self.url.startswith("sqlite:"):
            options["connect_args"] = {"check_same_thread": False, "timeout": 10}
            if self.url in ("sqlite://", "sqlite:///:memory:"):
                options["poolclass"] = StaticPool
        self.engine: Engine = create_engine(self.url, **options)
        if self.url.startswith("sqlite:"):
            self._configure_sqlite(self.engine)
        self.session_factory = sessionmaker(
            bind=self.engine, class_=Session, expire_on_commit=False, autoflush=False
        )

    @staticmethod
    def _configure_sqlite(engine: Engine) -> None:
        @event.listens_for(engine, "connect")
        def enable_sqlite_invariants(connection, _record) -> None:
            # Explicit transaction control lets the begin hook serialize SQLite writers.
            connection.isolation_level = None
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=10000")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

        @event.listens_for(engine, "begin")
        def begin_immediate(connection) -> None:
            # SQLite permits only one writer. Acquiring the lock before reading the
            # idempotency scope avoids deferred read-to-write upgrade races.
            connection.exec_driver_sql("BEGIN IMMEDIATE")

    def create_schema(self) -> None:
        Base.metadata.create_all(self.engine)
        if self.engine.dialect.name == "sqlite":
            self._upgrade_phase4_sqlite_columns()

    def _upgrade_phase4_sqlite_columns(self) -> None:
        """Additive startup migration for Phase 4 fields without destructive changes."""
        additions = {
            "workflow_executions": {
                "context": "JSON NOT NULL DEFAULT '{}'",
                "lease_token": "VARCHAR(36)",
                "lease_until": "DATETIME",
            },
            "retry_jobs": {
                "operation_key": "VARCHAR(255)",
                "claim_token": "VARCHAR(36)",
                "lease_until": "DATETIME",
            },
        }
        with self.engine.begin() as connection:
            inspector = inspect(connection)
            tables = set(inspector.get_table_names())
            for table, columns in additions.items():
                if table not in tables:
                    continue
                existing = {column["name"] for column in inspector.get_columns(table)}
                for name, column_type in columns.items():
                    if name not in existing:
                        connection.exec_driver_sql(
                            f"ALTER TABLE {table} ADD COLUMN {name} {column_type}"
                        )
            if "retry_jobs" in tables:
                connection.exec_driver_sql(
                    "UPDATE retry_jobs SET operation_key = 'legacy:' || id "
                    "WHERE operation_key IS NULL"
                )
                unique_names = {
                    item["name"] for item in inspect(connection).get_unique_constraints("retry_jobs")
                }
                index_names = {
                    item["name"] for item in inspect(connection).get_indexes("retry_jobs")
                }
                if "uq_retry_execution_stage" not in (unique_names | index_names):
                    connection.exec_driver_sql(
                        "CREATE UNIQUE INDEX uq_retry_execution_stage "
                        "ON retry_jobs (execution_id, stage_id)"
                    )
                if "uq_retry_operation_key" not in (unique_names | index_names):
                    connection.exec_driver_sql(
                        "CREATE UNIQUE INDEX uq_retry_operation_key "
                        "ON retry_jobs (operation_key)"
                    )
                connection.exec_driver_sql(
                    "CREATE INDEX IF NOT EXISTS ix_retry_due "
                    "ON retry_jobs (status, next_run_at)"
                )

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self.session_factory()
        try:
            yield session
        finally:
            session.close()

    def dispose(self) -> None:
        self.engine.dispose()

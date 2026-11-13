"""SQLite engine, foreign-key setup, and SQLAlchemy session lifecycle."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, event
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

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self.session_factory()
        try:
            yield session
        finally:
            session.close()

    def dispose(self) -> None:
        self.engine.dispose()

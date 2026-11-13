"""The additive initializer upgrades a Phase 3 SQLite schema without dropping data."""

import sqlite3

from sqlalchemy import inspect

from app.persistence.database import Database


def test_phase3_database_receives_phase4_lease_and_context_columns(tmp_path):
    path = tmp_path / "old-phase3.sqlite3"
    connection = sqlite3.connect(path)
    connection.executescript("""
        CREATE TABLE workflow_executions (
            id VARCHAR(36) PRIMARY KEY,
            request_id VARCHAR(36) NOT NULL UNIQUE,
            current_stage VARCHAR(120) NOT NULL,
            status VARCHAR(40) NOT NULL,
            revision INTEGER NOT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL
        );
        CREATE TABLE retry_jobs (
            id VARCHAR(36) PRIMARY KEY,
            execution_id VARCHAR(36) NOT NULL,
            stage_id VARCHAR(120) NOT NULL,
            attempt_count INTEGER NOT NULL,
            next_run_at DATETIME NOT NULL,
            status VARCHAR(40) NOT NULL,
            created_at DATETIME NOT NULL
        );
    """)
    connection.commit()
    connection.close()

    database = Database(f"sqlite:///{path.as_posix()}")
    try:
        database.create_schema()
        inspector = inspect(database.engine)
        execution_columns = {column["name"] for column in inspector.get_columns("workflow_executions")}
        retry_columns = {column["name"] for column in inspector.get_columns("retry_jobs")}
        assert {"context", "lease_token", "lease_until"} <= execution_columns
        assert {"operation_key", "claim_token", "lease_until"} <= retry_columns
        assert "workflow_requests" in inspector.get_table_names()
    finally:
        database.dispose()

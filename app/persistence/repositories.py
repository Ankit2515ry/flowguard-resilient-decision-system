"""Small repository helpers for SQLAlchemy-backed application services."""

from __future__ import annotations

from typing import Any, Iterable

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.persistence.models import AuditEvent, Decision, WorkflowConfig, WorkflowExecution, WorkflowRequest


class RequestRepository:
    def __init__(self, session: Session):
        self.session = session

    def by_idempotency(self, workflow_id: str, key: str) -> WorkflowRequest | None:
        return self.session.scalar(select(WorkflowRequest).where(
            WorkflowRequest.workflow_id == workflow_id,
            WorkflowRequest.idempotency_key == key,
        ))

    def by_id(self, request_id: str) -> WorkflowRequest | None:
        return self.session.get(WorkflowRequest, request_id)

    def decision_for(self, request_id: str) -> Decision | None:
        return self.session.scalar(select(Decision).where(Decision.request_id == request_id))


class WorkflowConfigRepository:
    def __init__(self, session: Session):
        self.session = session

    def active(self, workflow_id: str) -> WorkflowConfig | None:
        return self.session.scalar(select(WorkflowConfig).where(
            WorkflowConfig.workflow_id == workflow_id,
            WorkflowConfig.is_active.is_(True),
        ))

    def active_workflows(self) -> list[WorkflowConfig]:
        return list(self.session.scalars(
            select(WorkflowConfig).where(WorkflowConfig.is_active.is_(True)).order_by(WorkflowConfig.workflow_id)
        ))

    def versions(self, workflow_id: str) -> list[WorkflowConfig]:
        return list(self.session.scalars(
            select(WorkflowConfig).where(WorkflowConfig.workflow_id == workflow_id)
            .order_by(WorkflowConfig.version.desc())
        ))


def synchronize_workflow_snapshots(
    session: Session,
    snapshots: Iterable[dict[str, Any]],
) -> None:
    """Insert immutable snapshots and activate each workflow's highest version.

    A stored version whose bytes/checksum changes is a startup error. Activation only flips
    the active marker; request rows continue to pin the old version number.
    """
    snapshot_list = list(snapshots)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for snapshot in snapshot_list:
        grouped.setdefault(snapshot["workflow_id"], []).append(snapshot)

    existing_rows = list(session.scalars(select(WorkflowConfig)))
    existing = {(row.workflow_id, row.version): row for row in existing_rows}
    for snapshot in snapshot_list:
        key = (snapshot["workflow_id"], snapshot["version"])
        row = existing.get(key)
        if row is None:
            session.add(WorkflowConfig(**snapshot, is_active=False))
        elif row.checksum != snapshot["checksum"]:
            raise ValueError(
                f"immutable workflow snapshot changed for {key[0]} version {key[1]}"
            )

    # Clear before setting a new active version to satisfy the partial unique index.
    session.execute(update(WorkflowConfig).values(is_active=False))
    session.flush()
    for workflow_id, versions in grouped.items():
        latest = max(versions, key=lambda item: item["version"])
        active_row = session.get(WorkflowConfig, (workflow_id, latest["version"]))
        assert active_row is not None
        active_row.is_active = True

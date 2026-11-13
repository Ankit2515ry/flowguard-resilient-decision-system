"""Atomic request creation, canonical idempotency, and status read use cases."""

from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.persistence.models import AuditEvent, Decision, WorkflowExecution, WorkflowRequest
from app.persistence.repositories import RequestRepository, WorkflowConfigRepository
from app.services.input_validation import InputSchemaError, validate_input


class UnknownWorkflowError(LookupError):
    pass


class IdempotencyConflictError(ValueError):
    pass


class IntakeValidationError(ValueError):
    pass


def canonical_payload_hash(workflow_id: str, data: dict[str, Any]) -> str:
    """Hash workflow identity and semantic input data, independent of object key order."""
    try:
        canonical = json.dumps(
            {"workflow_id": workflow_id, "data": data}, sort_keys=True,
            separators=(",", ":"), ensure_ascii=False, allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise IntakeValidationError("data must contain only finite JSON values") from exc
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def create_request(
    session: Session,
    *,
    workflow_id: str,
    data: dict[str, Any],
    idempotency_key: str,
) -> tuple[WorkflowRequest, bool]:
    key = idempotency_key.strip()
    if not key:
        raise IntakeValidationError("Idempotency-Key must not be blank")
    payload_hash = canonical_payload_hash(workflow_id, data)
    requests = RequestRepository(session)
    configs = WorkflowConfigRepository(session)

    try:
        with session.begin():
            existing = requests.by_idempotency(workflow_id, key)
            if existing is not None:
                if existing.canonical_payload_hash != payload_hash:
                    raise IdempotencyConflictError(
                        "Idempotency-Key was already used with a different request payload"
                    )
                return existing, True

            active_config = configs.active(workflow_id)
            if active_config is None:
                raise UnknownWorkflowError(workflow_id)
            schema = active_config.configuration.get("input_schema")
            if not isinstance(schema, dict):
                raise IntakeValidationError("active workflow version has no input schema")
            try:
                validate_input(data, schema)
            except InputSchemaError as exc:
                raise IntakeValidationError(str(exc)) from exc

            workflow_snapshot = active_config.configuration.get("workflow", {})
            entry_stage = workflow_snapshot.get("entry_stage")
            if not entry_stage:
                raise IntakeValidationError("active workflow snapshot has no entry stage")

            request = WorkflowRequest(
                id=str(uuid4()),
                workflow_id=workflow_id,
                config_version=active_config.version,
                idempotency_key=key,
                canonical_payload_hash=payload_hash,
                input_payload=data,
                status="RECEIVED",
            )
            execution = WorkflowExecution(
                id=str(uuid4()),
                request_id=request.id,
                current_stage=entry_stage,
                status="RECEIVED",
                revision=0,
            )
            audit = AuditEvent(
                id=str(uuid4()),
                request_id=request.id,
                sequence=1,
                event_type="REQUEST_RECEIVED",
                old_state=None,
                new_state="RECEIVED",
                details={"workflow_id": workflow_id, "config_version": active_config.version},
            )
            # Flush the parent explicitly: these records reference IDs via FK columns
            # rather than ORM relationships, so mapper ordering alone is not sufficient.
            session.add(request)
            session.flush()
            session.add_all((execution, audit))
            session.flush()
        return request, False
    except IntegrityError:
        # The scoped database uniqueness constraint remains authoritative during races.
        session.rollback()
        existing = requests.by_idempotency(workflow_id, key)
        if existing is None:
            raise
        if existing.canonical_payload_hash != payload_hash:
            raise IdempotencyConflictError(
                "Idempotency-Key was already used with a different request payload"
            )
        return existing, True


def get_request_status(
    session: Session, request_id: str
) -> tuple[WorkflowRequest, Decision | None, WorkflowExecution | None] | None:
    request = RequestRepository(session).by_id(request_id)
    if request is None:
        return None
    decision = RequestRepository(session).decision_for(request_id)
    execution = session.scalar(select(WorkflowExecution).where(
        WorkflowExecution.request_id == request_id
    ))
    return request, decision, execution


def get_execution(session: Session, request_id: str) -> WorkflowExecution | None:
    return session.scalar(select(WorkflowExecution).where(WorkflowExecution.request_id == request_id))

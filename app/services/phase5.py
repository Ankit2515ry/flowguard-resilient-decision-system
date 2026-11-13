"""Audit/explanation reads, review resolution, and config activation use cases."""

from __future__ import annotations

import copy
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.lifecycle import validate_transition
from app.engine.config import parse_workflow
from app.persistence.models import (
    AdminAuditEvent, AuditEvent, Decision, WorkflowConfig, WorkflowExecution,
    WorkflowRequest, utc_now,
)
from app.services.configuration_snapshots import configuration_checksum
from app.services.input_validation import InputSchemaError, validate_schema_definition


class ResourceNotFoundError(LookupError):
    pass


class Phase5ConflictError(ValueError):
    pass


def audit_history(session: Session, request_id: str) -> tuple[WorkflowRequest, list[AuditEvent]]:
    request = session.get(WorkflowRequest, request_id)
    if request is None:
        raise ResourceNotFoundError("Request not found")
    events = list(session.scalars(select(AuditEvent).where(
        AuditEvent.request_id == request_id
    ).order_by(AuditEvent.sequence)))
    return request, events


def decision_explanation(session: Session, request_id: str) -> dict[str, Any]:
    request = session.get(WorkflowRequest, request_id)
    if request is None:
        raise ResourceNotFoundError("Request not found")
    execution = session.scalar(select(WorkflowExecution).where(
        WorkflowExecution.request_id == request_id
    ))
    decision = session.scalar(select(Decision).where(Decision.request_id == request_id))
    persisted = decision.explanation if decision is not None else {}
    context = execution.context if execution is not None else {}
    traces = copy.deepcopy(persisted.get("rule_traces", context.get("rule_traces", [])))
    stages = copy.deepcopy(persisted.get("stage_results", context.get("stage_results", [])))
    external = copy.deepcopy(persisted.get("external_results", context.get("external_results", [])))
    resolution = persisted.get("review_resolution")

    final_outcome = request.status if request.status in {"APPROVED", "REJECTED", "FAILED"} else None
    if request.status == "MANUAL_REVIEW":
        final_outcome = None
        summary = "The workflow reached manual review and is awaiting a reviewer decision."
    elif request.status == "APPROVED" and resolution:
        summary = f"A reviewer approved the request: {resolution['reason']}"
    elif request.status == "REJECTED" and resolution:
        summary = f"A reviewer rejected the request: {resolution['reason']}"
    elif request.status == "APPROVED":
        summary = "All configured eligibility checks and required external verification succeeded."
    elif request.status == "REJECTED":
        failures = [trace for trace in traces if not trace.get("passed", True)]
        summary = "The request was rejected by configured rule(s): " + ", ".join(
            str(trace.get("rule_id", "unknown")) for trace in failures
        ) if failures else "The workflow reached its configured rejection outcome."
    elif request.status == "RETRY_WAIT":
        summary = "External verification is waiting for a scheduled retry; no final decision is available."
    elif request.status == "FAILED":
        summary = "Workflow execution failed for a technical reason; no business approval was produced."
    else:
        summary = "Workflow execution has not reached a final decision."

    return {
        "request_id": request.id,
        "workflow_id": request.workflow_id,
        "config_version": request.config_version,
        "status": request.status,
        "decision_outcome": final_outcome,
        "pending": final_outcome is None,
        "summary": summary,
        "rule_traces": traces,
        "stage_results": stages,
        "external_results": external,
        "review_resolution": copy.deepcopy(resolution),
    }


def list_pending_reviews(session: Session) -> list[dict[str, Any]]:
    rows = session.execute(
        select(WorkflowRequest, WorkflowExecution)
        .join(WorkflowExecution, WorkflowExecution.request_id == WorkflowRequest.id)
        .where(WorkflowRequest.status == "MANUAL_REVIEW")
        .order_by(WorkflowRequest.created_at, WorkflowRequest.id)
    ).all()
    return [{
        "request_id": request.id,
        "workflow_id": request.workflow_id,
        "config_version": request.config_version,
        "status": request.status,
        "current_stage": execution.current_stage,
        "created_at": request.created_at,
    } for request, execution in rows]


def resolve_review(
    session: Session, request_id: str, *, action: str, reason: str,
    actor: str = "demo-admin", now: datetime | None = None,
) -> dict[str, Any]:
    action = action.upper()
    reason = reason.strip()
    if action not in {"APPROVE", "REJECT"}:
        raise ValueError("action must be APPROVE or REJECT")
    if not reason:
        raise ValueError("reason must not be blank")
    outcome = "APPROVED" if action == "APPROVE" else "REJECTED"
    effective_now = now or utc_now()
    try:
        with session.begin():
            request = session.get(WorkflowRequest, request_id)
            if request is None:
                raise ResourceNotFoundError("Request not found")
            decision = session.scalar(select(Decision).where(Decision.request_id == request_id))
            if request.status in {"APPROVED", "REJECTED"}:
                prior = (decision.explanation if decision else {}).get("review_resolution")
                if prior and prior.get("action") == action and prior.get("reason") == reason:
                    return {"request_id": request_id, "status": request.status,
                            "decision_outcome": request.status, "replayed": True}
                raise Phase5ConflictError("Request has already been resolved differently")
            if request.status != "MANUAL_REVIEW" or decision is None or decision.outcome != "MANUAL_REVIEW":
                raise Phase5ConflictError("Only pending MANUAL_REVIEW requests may be resolved")
            execution = session.scalar(select(WorkflowExecution).where(
                WorkflowExecution.request_id == request_id
            ))
            if execution is None:
                raise Phase5ConflictError("Manual review execution record is missing")
            validate_transition(request.status, outcome)
            prior_state = request.status
            request.status = outcome
            request.updated_at = effective_now
            execution.status = outcome
            execution.updated_at = effective_now
            execution.revision += 1
            explanation = copy.deepcopy(decision.explanation or {})
            resolution = {
                "action": action, "reason": reason, "actor": actor,
                "resolved_at": effective_now.isoformat(),
            }
            explanation["review_resolution"] = resolution
            decision.outcome = outcome
            decision.explanation = explanation
            sequence = (session.scalar(select(func.max(AuditEvent.sequence)).where(
                AuditEvent.request_id == request_id
            )) or 0) + 1
            session.add(AuditEvent(
                id=str(uuid.uuid4()), request_id=request_id, sequence=sequence,
                event_type="REVIEW_RESOLVED", old_state=prior_state, new_state=outcome,
                details={"action": action, "reason": reason, "actor": actor,
                         "stage_id": execution.current_stage,
                         "config_version": request.config_version},
                created_at=effective_now,
            ))
            session.flush()
        return {"request_id": request_id, "status": outcome,
                "decision_outcome": outcome, "replayed": False}
    except Exception:
        session.rollback()
        raise


def activate_workflow_version(
    session: Session, *, workflow_id: str, version: int, actor: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    effective_now = now or utc_now()
    try:
        with session.begin():
            target = session.get(WorkflowConfig, (workflow_id, version))
            if target is None:
                raise ResourceNotFoundError(f"Unknown workflow version: {workflow_id} v{version}")
            if configuration_checksum(target.configuration) != target.checksum:
                raise ValueError("workflow snapshot checksum does not match")
            workflow_data = target.configuration.get("workflow")
            input_schema = target.configuration.get("input_schema")
            if not isinstance(workflow_data, dict) or not isinstance(input_schema, dict):
                raise ValueError("workflow snapshot is incomplete")
            definition = parse_workflow(workflow_data, source="persisted snapshot")
            try:
                validate_schema_definition(input_schema)
            except InputSchemaError as exc:
                raise ValueError(f"workflow input schema is invalid: {exc}") from exc
            if definition.workflow_id != workflow_id or definition.version != version:
                raise ValueError("workflow snapshot identity does not match activation target")

            current = session.scalar(select(WorkflowConfig).where(
                WorkflowConfig.workflow_id == workflow_id,
                WorkflowConfig.is_active.is_(True),
            ))
            old_version = current.version if current is not None else None
            if current is not None and current.version == version:
                return {"workflow_id": workflow_id, "active_version": version, "changed": False}
            if current is not None:
                current.is_active = False
                session.flush()
            target.is_active = True
            session.add(AdminAuditEvent(
                id=str(uuid.uuid4()), event_type="WORKFLOW_VERSION_ACTIVATED",
                workflow_id=workflow_id, actor=actor, old_version=old_version,
                new_version=version, created_at=effective_now,
            ))
            session.flush()
        return {"workflow_id": workflow_id, "active_version": version, "changed": True}
    except Exception:
        session.rollback()
        raise

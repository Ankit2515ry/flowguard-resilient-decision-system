"""Audit, explanation, review, and privileged workflow activation endpoints."""

from __future__ import annotations

import hmac
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.dependencies import get_session
from app.api.schemas import (
    AuditEventView, DecisionExplanationView, ReviewItemView,
    ReviewResolutionRequest, ReviewResolutionView,
    WorkflowActivationRequest, WorkflowActivationView,
)
from app.services.phase5 import (
    Phase5ConflictError, ResourceNotFoundError, activate_workflow_version,
    audit_history, decision_explanation, list_pending_reviews, resolve_review,
)


router = APIRouter(prefix="/api/v1", tags=["audit and administration"])


def _require_admin(request: Request, token: str | None) -> str:
    configured = request.app.state.admin_token
    if not configured:
        raise HTTPException(status_code=503, detail="Admin authentication is not configured")
    if token is None:
        raise HTTPException(status_code=401, detail="X-Admin-Token is required")
    if not hmac.compare_digest(token, configured):
        raise HTTPException(status_code=403, detail="Admin authentication failed")
    # The credential represents a single demo administrator; never trust a client actor field.
    return "demo-admin"


@router.get("/requests/{request_id}/audit", response_model=list[AuditEventView])
def read_audit(request_id: UUID, session: Annotated[Session, Depends(get_session)]):
    try:
        request_row, events = audit_history(session, str(request_id))
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    result = []
    for event in events:
        details = event.details or {}
        stage = details.get("stage_id") or details.get("stage") or details.get("from_stage")
        result.append(AuditEventView(
            sequence=event.sequence,
            event_type=event.event_type,
            old_state=event.old_state,
            new_state=event.new_state,
            stage=stage,
            created_at=event.created_at,
            config_version=request_row.config_version,
            details=details,
        ))
    return result


@router.get("/requests/{request_id}/explanation", response_model=DecisionExplanationView)
def read_explanation(request_id: UUID, session: Annotated[Session, Depends(get_session)]):
    try:
        return decision_explanation(session, str(request_id))
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/reviews", response_model=list[ReviewItemView])
def review_queue(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    admin_token: Annotated[str | None, Header(alias="X-Admin-Token")] = None,
):
    _require_admin(request, admin_token)
    return list_pending_reviews(session)


@router.post("/reviews/{request_id}/resolve", response_model=ReviewResolutionView)
def resolve_review_endpoint(
    request_id: UUID,
    body: ReviewResolutionRequest,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    admin_token: Annotated[str | None, Header(alias="X-Admin-Token")] = None,
):
    actor = _require_admin(request, admin_token)
    try:
        return resolve_review(
            session, str(request_id), action=body.action, reason=body.reason, actor=actor
        )
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Phase5ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/admin/workflows/activate", response_model=WorkflowActivationView)
def activate_workflow(
    body: WorkflowActivationRequest,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    admin_token: Annotated[str | None, Header(alias="X-Admin-Token")] = None,
):
    actor = _require_admin(request, admin_token)
    try:
        return activate_workflow_version(
            session, workflow_id=body.workflow_id, version=body.version, actor=actor
        )
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

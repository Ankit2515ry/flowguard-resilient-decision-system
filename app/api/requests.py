"""Request intake and status endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy.orm import Session

from app.api.dependencies import get_session
from app.api.schemas import RequestAccepted, RequestCreate, RequestStatus
from app.services.request_intake import (
    IdempotencyConflictError,
    IntakeValidationError,
    UnknownWorkflowError,
    create_request,
    get_request_status,
)


router = APIRouter(prefix="/api/v1/requests", tags=["requests"])


@router.post("", response_model=RequestAccepted, status_code=202)
def submit_request(
    body: RequestCreate,
    response: Response,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)],
    session: Annotated[Session, Depends(get_session)],
) -> RequestAccepted:
    try:
        request, replayed = create_request(
            session,
            workflow_id=body.workflow_id,
            data=body.data,
            idempotency_key=idempotency_key,
        )
    except UnknownWorkflowError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown workflow: {exc}") from exc
    except IdempotencyConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntakeValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if replayed:
        response.status_code = 200
        response.headers["Idempotency-Replayed"] = "true"
    return RequestAccepted(
        request_id=request.id,
        status=request.status,
        workflow_id=request.workflow_id,
        config_version=request.config_version,
        status_url=f"/api/v1/requests/{request.id}",
    )


@router.get("/{request_id}", response_model=RequestStatus)
def read_request(request_id: UUID, session: Annotated[Session, Depends(get_session)]) -> RequestStatus:
    result = get_request_status(session, str(request_id))
    if result is None:
        raise HTTPException(status_code=404, detail="Request not found")
    request, decision = result
    decision_view = None
    if decision is not None:
        decision_view = {
            "outcome": decision.outcome,
            "explanation": decision.explanation,
            "created_at": decision.created_at,
        }
    return RequestStatus(
        request_id=request.id,
        status=request.status,
        workflow_id=request.workflow_id,
        config_version=request.config_version,
        created_at=request.created_at,
        updated_at=request.updated_at,
        decision=decision_view,
    )

"""Workflow/version discovery endpoints backed by persisted snapshots."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_session
from app.api.schemas import WorkflowVersionView, WorkflowView
from app.persistence.repositories import WorkflowConfigRepository


router = APIRouter(prefix="/api/v1/workflows", tags=["workflows"])


@router.get("", response_model=list[WorkflowView])
def list_workflows(session: Annotated[Session, Depends(get_session)]) -> list[WorkflowView]:
    rows = WorkflowConfigRepository(session).active_workflows()
    return [WorkflowView(
        workflow_id=row.workflow_id, active_version=row.version, checksum=row.checksum
    ) for row in rows]


@router.get("/{workflow_id}/versions", response_model=list[WorkflowVersionView])
def list_workflow_versions(
    workflow_id: str, session: Annotated[Session, Depends(get_session)]
) -> list[WorkflowVersionView]:
    rows = WorkflowConfigRepository(session).versions(workflow_id)
    if not rows:
        raise HTTPException(status_code=404, detail=f"Unknown workflow: {workflow_id}")
    return [WorkflowVersionView(
        workflow_id=row.workflow_id,
        version=row.version,
        checksum=row.checksum,
        is_active=row.is_active,
    ) for row in rows]

"""HTTP request and response schemas for intake and workflow discovery."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workflow_id: str = Field(min_length=1, max_length=120)
    data: dict[str, Any]


class RequestAccepted(BaseModel):
    request_id: UUID
    status: str
    workflow_id: str
    config_version: int
    status_url: str


class DecisionView(BaseModel):
    outcome: str
    explanation: dict[str, Any]
    created_at: datetime


class RequestStatus(BaseModel):
    request_id: UUID
    status: str
    workflow_id: str
    config_version: int
    current_stage: str | None = None
    revision: int = 0
    created_at: datetime
    updated_at: datetime
    decision: DecisionView | None = None


class WorkflowView(BaseModel):
    workflow_id: str
    active_version: int
    checksum: str


class WorkflowVersionView(BaseModel):
    workflow_id: str
    version: int
    checksum: str
    is_active: bool

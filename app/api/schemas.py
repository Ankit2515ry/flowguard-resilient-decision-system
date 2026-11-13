"""HTTP request and response schemas for intake and workflow discovery."""

from datetime import datetime
from typing import Any, Literal
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


class AuditEventView(BaseModel):
    sequence: int
    event_type: str
    old_state: str | None
    new_state: str
    stage: str | None
    created_at: datetime
    config_version: int
    details: dict[str, Any]


class DecisionExplanationView(BaseModel):
    request_id: UUID
    workflow_id: str
    config_version: int
    status: str
    decision_outcome: str | None
    pending: bool
    summary: str
    rule_traces: list[dict[str, Any]]
    stage_results: list[dict[str, Any]]
    external_results: list[dict[str, Any]]
    review_resolution: dict[str, Any] | None = None


class ReviewItemView(BaseModel):
    request_id: UUID
    workflow_id: str
    config_version: int
    status: str
    current_stage: str
    created_at: datetime


class ReviewResolutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["APPROVE", "REJECT"]
    reason: str = Field(min_length=1, max_length=2000)


class ReviewResolutionView(BaseModel):
    request_id: UUID
    status: str
    decision_outcome: str
    replayed: bool


class WorkflowActivationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workflow_id: str = Field(min_length=1, max_length=120)
    version: int = Field(ge=1)


class WorkflowActivationView(BaseModel):
    workflow_id: str
    active_version: int
    changed: bool

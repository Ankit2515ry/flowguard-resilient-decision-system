"""Transactional workflow orchestration with external calls outside DB transactions."""

from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, sessionmaker

from app.adapters.verification import (
    DependencyCategory,
    VerificationProvider,
    VerificationResult,
)
from app.core.retry_policy import RetryPolicy
from app.domain.lifecycle import FINAL_STATES, validate_transition
from app.engine.config import (
    ConfigurationError,
    Stage,
    StageType,
    WorkflowDefinition,
    parse_workflow,
)
from app.engine.rules import RuleEvaluationError, evaluate_rules
from app.persistence.models import (
    AuditEvent,
    Decision,
    RetryJob,
    WorkflowConfig,
    WorkflowExecution,
    WorkflowRequest,
    utc_now,
)
from app.services.configuration_snapshots import configuration_checksum


class RequestNotFoundError(LookupError):
    pass


class ExecutionInvariantError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class _Claim:
    request_id: str
    execution_id: str
    token: str
    definition: WorkflowDefinition
    payload: dict[str, Any]
    config_version: int
    retry_job_id: str | None = None
    retry_stage_id: str | None = None
    retry_attempt_number: int | None = None


def _audit(
    session: Session,
    *,
    request_id: str,
    event_type: str,
    old_state: str | None,
    new_state: str,
    details: dict[str, Any],
    now: datetime,
) -> None:
    # A transaction can append more than one event (for example RECEIVED -> PROCESSING
    # followed by config validation -> FAILED). Flush earlier events before max(sequence).
    session.flush()
    last_sequence = session.scalar(
        select(func.max(AuditEvent.sequence)).where(AuditEvent.request_id == request_id)
    ) or 0
    session.add(AuditEvent(
        id=str(uuid.uuid4()),
        request_id=request_id,
        sequence=last_sequence + 1,
        event_type=event_type,
        old_state=old_state,
        new_state=new_state,
        details=details,
        created_at=now,
    ))


def _transition_state(
    session: Session,
    request: WorkflowRequest,
    execution: WorkflowExecution,
    new_state: str,
    *,
    event_type: str,
    details: dict[str, Any],
    now: datetime,
) -> None:
    if request.status != execution.status:
        raise ExecutionInvariantError(
            f"request/execution states diverged: {request.status} != {execution.status}"
        )
    old_state = request.status
    validate_transition(old_state, new_state)
    request.status = new_state
    execution.status = new_state
    request.updated_at = now
    execution.updated_at = now
    execution.revision += 1
    _audit(
        session, request_id=request.id, event_type=event_type,
        old_state=old_state, new_state=new_state, details=details, now=now,
    )


def _stage_event(
    session: Session,
    request: WorkflowRequest,
    execution: WorkflowExecution,
    *,
    event_type: str,
    old_stage: str,
    new_stage: str,
    details: dict[str, Any],
    now: datetime,
) -> None:
    request.updated_at = now
    execution.current_stage = new_stage
    execution.updated_at = now
    execution.revision += 1
    _audit(
        session, request_id=request.id, event_type=event_type,
        old_state=request.status, new_state=request.status,
        details={"from_stage": old_stage, "to_stage": new_stage, **details}, now=now,
    )


def _append_context(context: dict[str, Any], key: str, values: list[dict[str, Any]]) -> None:
    context.setdefault(key, [])
    context[key].extend(values)


def _read_claim_data(
    session: Session,
    request: WorkflowRequest,
) -> tuple[WorkflowDefinition, dict[str, Any]]:
    snapshot = session.get(WorkflowConfig, (request.workflow_id, request.config_version))
    if snapshot is None:
        raise ConfigurationError("pinned workflow configuration snapshot is missing")
    if configuration_checksum(snapshot.configuration) != snapshot.checksum:
        raise ConfigurationError("pinned workflow configuration checksum does not match")
    workflow_data = snapshot.configuration.get("workflow")
    if not isinstance(workflow_data, dict):
        raise ConfigurationError("pinned workflow snapshot has no workflow definition")
    workflow_data = copy.deepcopy(workflow_data)
    _normalize_snapshot_conditions(workflow_data)
    definition = parse_workflow(workflow_data, source="persisted snapshot")
    if definition.workflow_id != request.workflow_id or definition.version != request.config_version:
        raise ConfigurationError("pinned workflow snapshot identity does not match request")
    return definition, copy.deepcopy(request.input_payload)


def _normalize_snapshot_conditions(workflow_data: dict[str, Any]) -> None:
    """Remove Pydantic's serialized null defaults without changing explicit leaf nulls."""
    for rule_set in workflow_data.get("rule_sets", []):
        for rule in rule_set.get("rules", []):
            condition = rule.get("condition")
            if condition is not None:
                _normalize_condition(condition)


def _normalize_condition(condition: dict[str, Any]) -> None:
    if condition.get("field") is not None:
        condition.pop("all", None)
        condition.pop("any", None)
        return
    for default_key in ("field", "operator", "value"):
        condition.pop(default_key, None)
    for group in ("all", "any"):
        if condition.get(group) is None:
            condition.pop(group, None)
        else:
            for child in condition[group]:
                _normalize_condition(child)


def _fail_in_transaction(
    session: Session,
    request: WorkflowRequest,
    execution: WorkflowExecution,
    reason: str,
    now: datetime,
) -> None:
    if request.status == "RECEIVED":
        _transition_state(
            session, request, execution, "PROCESSING", event_type="EXECUTION_STARTED",
            details={"reason": "request accepted for execution"}, now=now,
        )
    if request.status in ("PROCESSING", "RETRY_WAIT"):
        _transition_state(
            session, request, execution, "FAILED", event_type="EXECUTION_FAILED",
            details={"reason": reason}, now=now,
        )
    execution.lease_token = None
    execution.lease_until = None


def _claim_execution(
    session_factory: sessionmaker[Session],
    request_id: str,
    policy: RetryPolicy,
    now: datetime,
) -> _Claim | None:
    claim: _Claim | None = None
    with session_factory() as session:
        with session.begin():
            request = session.get(WorkflowRequest, request_id)
            if request is None:
                raise RequestNotFoundError(request_id)
            execution = session.scalar(
                select(WorkflowExecution).where(WorkflowExecution.request_id == request_id)
            )
            if execution is None:
                _fail_without_execution(session, request, "execution record is missing", now)
                return None
            if request.status in FINAL_STATES or request.status == "RETRY_WAIT":
                return None
            if request.status == "PROCESSING" and execution.lease_until is not None \
                    and execution.lease_until > now:
                return None
            if request.status == "PROCESSING":
                claimed_retry = session.scalar(select(RetryJob.id).where(
                    RetryJob.execution_id == execution.id,
                    RetryJob.status == "CLAIMED",
                ).limit(1))
                if claimed_retry is not None:
                    # Retry workers own recovery of their durable claim; a demo execute
                    # trigger must not race a claimed retry after its lease expires.
                    return None
            if request.status == "RECEIVED":
                _transition_state(
                    session, request, execution, "PROCESSING", event_type="EXECUTION_STARTED",
                    details={"reason": "explicit execution trigger"}, now=now,
                )
            elif request.status == "PROCESSING":
                request.updated_at = now
                _audit(
                    session, request_id=request.id, event_type="EXECUTION_RECOVERED",
                    old_state="PROCESSING", new_state="PROCESSING",
                    details={"reason": "previous execution lease expired"}, now=now,
                )
            else:
                _fail_in_transaction(session, request, execution,
                                      f"unsupported lifecycle state {request.status!r}", now)
                return None

            token = str(uuid.uuid4())
            execution.lease_token = token
            execution.lease_until = now + timedelta(seconds=policy.lease_seconds)
            execution.updated_at = now
            execution.revision += 1
            try:
                definition, payload = _read_claim_data(session, request)
            except (ConfigurationError, ValueError) as exc:
                _fail_in_transaction(session, request, execution, str(exc), now)
                return None
            claim = _Claim(
                request_id=request.id,
                execution_id=execution.id,
                token=token,
                definition=definition,
                payload=payload,
                config_version=request.config_version,
            )
    return claim


def _fail_without_execution(
    session: Session, request: WorkflowRequest, reason: str, now: datetime
) -> None:
    if request.status == "RECEIVED":
        request.status = "FAILED"
        request.updated_at = now
        # The execution row is absent, so only the request row can be repaired/audited.
        last = session.scalar(select(func.max(AuditEvent.sequence)).where(
            AuditEvent.request_id == request.id
        )) or 0
        session.add(AuditEvent(
            id=str(uuid.uuid4()), request_id=request.id, sequence=last + 1,
            event_type="EXECUTION_FAILED", old_state="RECEIVED", new_state="FAILED",
            details={"reason": reason}, created_at=now,
        ))


def _load_execution(
    session_factory: sessionmaker[Session], claim: _Claim
) -> tuple[WorkflowRequest, WorkflowExecution] | None:
    with session_factory() as session:
        request = session.get(WorkflowRequest, claim.request_id)
        execution = session.get(WorkflowExecution, claim.execution_id)
        if request is None or execution is None:
            return None
        # Detach-safe values are copied before session close.
        request.input_payload = copy.deepcopy(request.input_payload)
        execution.context = copy.deepcopy(execution.context or {})
        return request, execution


def _advance_stage(
    session_factory: sessionmaker[Session],
    claim: _Claim,
    target_stage: str,
    *,
    event_type: str,
    details: dict[str, Any],
    traces: list[dict[str, Any]] | None = None,
    now: datetime,
    retry_job_id: str | None = None,
) -> bool:
    with session_factory() as session:
        with session.begin():
            request = session.get(WorkflowRequest, claim.request_id)
            execution = session.get(WorkflowExecution, claim.execution_id)
            if request is None or execution is None:
                return False
            if execution.lease_token != claim.token or request.status != "PROCESSING":
                return False
            old_stage = execution.current_stage
            context = copy.deepcopy(execution.context or {})
            if traces:
                _append_context(context, "rule_traces", traces)
            context.setdefault("stage_results", []).append({
                "stage_id": old_stage,
                "event": event_type,
                "outcome": details.get("outcome"),
                "config_version": claim.config_version,
            })
            execution.context = context
            _stage_event(
                session, request, execution, event_type=event_type,
                old_stage=old_stage, new_stage=target_stage, details=details, now=now,
            )
            if retry_job_id:
                retry_job = session.get(RetryJob, retry_job_id)
                if retry_job is not None:
                    retry_job.status = "COMPLETED"
                    retry_job.claim_token = None
                    retry_job.lease_until = None
            session.flush()
    return True


def _finish_decision(
    session_factory: sessionmaker[Session],
    claim: _Claim,
    stage: Stage,
    outcome: str,
    *,
    now: datetime,
    details: dict[str, Any] | None = None,
    retry_job_id: str | None = None,
) -> bool:
    with session_factory() as session:
        with session.begin():
            request = session.get(WorkflowRequest, claim.request_id)
            execution = session.get(WorkflowExecution, claim.execution_id)
            if request is None or execution is None:
                return False
            if execution.lease_token != claim.token or request.status != "PROCESSING":
                return False
            existing = session.scalar(select(Decision).where(Decision.request_id == request.id))
            if existing is not None and existing.outcome != outcome:
                raise ExecutionInvariantError("request already has a different final decision")
            context = copy.deepcopy(execution.context or {})
            explanation = {
                "config_version": claim.config_version,
                "rule_traces": context.get("rule_traces", []),
                "stage_results": context.get("stage_results", []),
                "external_results": context.get("external_results", []),
            }
            if details:
                explanation["final_details"] = details
            if existing is None:
                session.add(Decision(
                    id=str(uuid.uuid4()), request_id=request.id,
                    outcome=outcome, explanation=explanation, created_at=now,
                ))
            execution.current_stage = stage.id
            execution.context = context
            execution.lease_token = None
            execution.lease_until = None
            execution.updated_at = now
            _transition_state(
                session, request, execution, outcome, event_type="DECISION_RECORDED",
                details={"stage_id": stage.id, "outcome": outcome,
                         "config_version": claim.config_version}, now=now,
            )
            if retry_job_id:
                retry_job = session.get(RetryJob, retry_job_id)
                if retry_job is not None:
                    retry_job.status = "COMPLETED"
                    retry_job.claim_token = None
                    retry_job.lease_until = None
            session.flush()
    return True


def _fail_execution(
    session_factory: sessionmaker[Session],
    claim: _Claim,
    reason: str,
    *,
    now: datetime,
    retry_job_id: str | None = None,
) -> None:
    with session_factory() as session:
        with session.begin():
            request = session.get(WorkflowRequest, claim.request_id)
            execution = session.get(WorkflowExecution, claim.execution_id)
            if request is None or execution is None or execution.lease_token != claim.token:
                return
            _transition_state(
                session, request, execution, "FAILED", event_type="EXECUTION_FAILED",
                details={"reason": reason, "config_version": claim.config_version}, now=now,
            )
            execution.lease_token = None
            execution.lease_until = None
            if retry_job_id:
                retry_job = session.get(RetryJob, retry_job_id)
                if retry_job:
                    retry_job.status = "COMPLETED"
                    retry_job.claim_token = None
                    retry_job.lease_until = None


def _external_result(
    session_factory: sessionmaker[Session],
    claim: _Claim,
    stage: Stage,
    result: VerificationResult,
    *,
    attempt_number: int,
    operation_key: str,
    policy: RetryPolicy,
    now: datetime,
    retry_job_id: str | None,
) -> str:
    """Persist one provider result; return ADVANCED, WAITING, or LOST_CLAIM."""
    with session_factory() as session:
        with session.begin():
            request = session.get(WorkflowRequest, claim.request_id)
            execution = session.get(WorkflowExecution, claim.execution_id)
            if request is None or execution is None or execution.lease_token != claim.token:
                return "LOST_CLAIM"
            context = copy.deepcopy(execution.context or {})
            attempts = context.setdefault("external_attempts", {})
            attempts[stage.id] = max(int(attempts.get(stage.id, 0)), attempt_number)
            result_entry = {
                "stage_id": stage.id,
                "operation": stage.operation,
                "operation_key": operation_key,
                "attempt": attempt_number,
                "success": result.success,
                "retryable": result.retryable,
                "category": result.category.value,
                "message": result.message,
                "config_version": claim.config_version,
            }
            context.setdefault("external_results", []).append(result_entry)
            execution.context = context

            if not result.success and result.retryable and attempt_number < policy.max_attempts:
                next_run = now + timedelta(seconds=policy.delay_after(attempt_number))
                retry_job = session.get(RetryJob, retry_job_id) if retry_job_id else None
                if retry_job is None:
                    retry_job = RetryJob(
                        id=str(uuid.uuid4()), execution_id=execution.id, stage_id=stage.id,
                        operation_key=operation_key, attempt_count=attempt_number,
                        next_run_at=next_run, status="PENDING", created_at=now,
                    )
                    session.add(retry_job)
                else:
                    retry_job.attempt_count = attempt_number
                    retry_job.next_run_at = next_run
                    retry_job.status = "PENDING"
                    retry_job.claim_token = None
                    retry_job.lease_until = None
                execution.lease_token = None
                execution.lease_until = None
                _transition_state(
                    session, request, execution, "RETRY_WAIT", event_type="RETRY_SCHEDULED",
                    details={**result_entry, "next_run_at": next_run.isoformat(),
                             "max_attempts": policy.max_attempts}, now=now,
                )
                session.flush()
                return "WAITING"

            if result.success:
                transition_outcome = "SUCCESS"
            else:
                # Permanent errors and exhausted transient errors follow configured fallback.
                transition_outcome = "FAILURE"
            try:
                target = claim.definition.transition_target(stage.id, transition_outcome)
            except KeyError as exc:
                _transition_state(
                    session, request, execution, "FAILED", event_type="EXECUTION_FAILED",
                    details={"reason": str(exc), **result_entry}, now=now,
                )
                execution.lease_token = None
                execution.lease_until = None
                if retry_job_id:
                    job = session.get(RetryJob, retry_job_id)
                    if job:
                        job.status = "COMPLETED"
                        job.claim_token = None
                        job.lease_until = None
                session.flush()
                return "ADVANCED"

            _stage_event(
                session, request, execution,
                event_type="EXTERNAL_CALL_SUCCEEDED" if result.success else "EXTERNAL_CALL_FAILED",
                old_stage=stage.id, new_stage=target,
                details={**result_entry, "outcome": transition_outcome,
                         "retry_exhausted": bool(result.retryable and not result.success)}, now=now,
            )
            execution.context = context
            if retry_job_id:
                job = session.get(RetryJob, retry_job_id)
                if job:
                    job.attempt_count = attempt_number
                    job.status = "COMPLETED"
                    job.claim_token = None
                    job.lease_until = None
            session.flush()
            return "ADVANCED"


def _run_claimed(
    session_factory: sessionmaker[Session],
    claim: _Claim,
    provider: VerificationProvider,
    policy: RetryPolicy,
    clock: Callable[[], datetime],
) -> None:
    retry_job_id = claim.retry_job_id
    while True:
        current = _load_execution(session_factory, claim)
        if current is None:
            return
        request, execution = current
        if request.status != "PROCESSING" or execution.lease_token != claim.token:
            return
        stage_by_id = {stage.id: stage for stage in claim.definition.stages}
        stage = stage_by_id.get(execution.current_stage)
        now = clock()
        if stage is None:
            _fail_execution(session_factory, claim,
                            f"pinned config references missing stage {execution.current_stage!r}",
                            now=now, retry_job_id=retry_job_id)
            return

        if stage.type is StageType.TERMINAL:
            assert stage.outcome is not None
            _finish_decision(
                session_factory, claim, stage, stage.outcome.value,
                now=now, retry_job_id=retry_job_id,
            )
            return

        if stage.type is StageType.HUMAN_TASK:
            try:
                target = claim.definition.transition_target(stage.id, "MANUAL_REVIEW")
            except KeyError as exc:
                _fail_execution(session_factory, claim, str(exc), now=now,
                                retry_job_id=retry_job_id)
                return
            if not _advance_stage(
                session_factory, claim, target, event_type="MANUAL_REVIEW_REQUIRED",
                details={"outcome": "MANUAL_REVIEW", "stage_type": stage.type.value}, now=now,
                retry_job_id=retry_job_id,
            ):
                return
            retry_job_id = None
            continue

        if stage.type is StageType.RULE_EVALUATION:
            rule_sets = {rule_set.id: rule_set for rule_set in claim.definition.rule_sets}
            rule_set = rule_sets.get(stage.rule_set or "")
            if rule_set is None:
                _fail_execution(session_factory, claim,
                                f"stage {stage.id!r} references missing rule set", now=now,
                                retry_job_id=retry_job_id)
                return
            try:
                evaluated = evaluate_rules(
                    rule_set, request.input_payload, config_version=claim.config_version
                )
            except (RuleEvaluationError, ValueError) as exc:
                _fail_execution(session_factory, claim,
                                f"rule evaluation failed: {exc}", now=now,
                                retry_job_id=retry_job_id)
                return
            outcome = "SUCCESS" if evaluated.passed else evaluated.outcome
            try:
                target = claim.definition.transition_target(stage.id, outcome or "")
            except KeyError as exc:
                _fail_execution(session_factory, claim, str(exc), now=now,
                                retry_job_id=retry_job_id)
                return
            if not _advance_stage(
                session_factory, claim, target, event_type="RULES_EVALUATED",
                details={"outcome": outcome, "failed_rule_ids": list(evaluated.failed_rule_ids),
                         "config_version": claim.config_version},
                traces=[trace.as_dict() for trace in evaluated.traces], now=now,
                retry_job_id=retry_job_id,
            ):
                return
            retry_job_id = None
            continue

        if stage.type is StageType.EXTERNAL_CALL:
            operation_key = (
                f"flowguard:{claim.definition.workflow_id}:{claim.config_version}:"
                f"{claim.request_id}:{stage.id}:{stage.operation}"
            )
            external_attempts = execution.context.get("external_attempts", {})
            if claim.retry_stage_id == stage.id and claim.retry_attempt_number is not None:
                attempt_number = claim.retry_attempt_number
            else:
                attempt_number = int(external_attempts.get(stage.id, 0)) + 1
            try:
                result = provider.verify(
                    operation=stage.operation or "",
                    payload=request.input_payload,
                    operation_key=operation_key,
                    attempt_number=attempt_number,
                )
                if not isinstance(result, VerificationResult):
                    raise TypeError("verification provider returned an invalid result")
            except Exception as exc:  # Provider exceptions are technical and retryable, never business rejects.
                result = VerificationResult(
                    success=False, retryable=True, category=DependencyCategory.PROVIDER_ERROR,
                    message=f"provider exception: {type(exc).__name__}",
                )
            outcome = _external_result(
                session_factory, claim, stage, result,
                attempt_number=attempt_number, operation_key=operation_key,
                policy=policy, now=clock(), retry_job_id=retry_job_id,
            )
            if outcome in ("WAITING", "LOST_CLAIM"):
                return
            retry_job_id = None
            continue

        _fail_execution(session_factory, claim, f"unsupported stage type {stage.type!r}",
                        now=now, retry_job_id=retry_job_id)
        return


def execute_request(
    session_factory: sessionmaker[Session],
    request_id: str,
    provider: VerificationProvider,
    policy: RetryPolicy,
    *,
    clock: Callable[[], datetime] = utc_now,
) -> None:
    claim = _claim_execution(session_factory, request_id, policy, clock())
    if claim is not None:
        _run_claimed(session_factory, claim, provider, policy, clock)


@dataclass(frozen=True, slots=True)
class _DueClaimResult:
    claim: _Claim | None
    consumed: bool


def _claim_due_retry(
    session_factory: sessionmaker[Session],
    policy: RetryPolicy,
    now: datetime,
) -> _DueClaimResult:
    claim: _Claim | None = None
    consumed = False
    with session_factory() as session:
        with session.begin():
            eligible = or_(
                and_(RetryJob.status == "PENDING", RetryJob.next_run_at <= now),
                and_(RetryJob.status == "CLAIMED", RetryJob.lease_until <= now),
            )
            job = session.scalar(select(RetryJob).where(eligible).order_by(
                RetryJob.next_run_at, RetryJob.created_at
            ).limit(1))
            if job is None:
                return _DueClaimResult(None, False)
            consumed = True
            execution = session.get(WorkflowExecution, job.execution_id)
            request = session.get(WorkflowRequest, execution.request_id) if execution else None
            if execution is None or request is None:
                job.status = "COMPLETED"
                job.claim_token = None
                job.lease_until = None
                return _DueClaimResult(None, True)
            if request.status in FINAL_STATES:
                job.status = "COMPLETED"
                job.claim_token = None
                job.lease_until = None
                return _DueClaimResult(None, True)
            token = str(uuid.uuid4())
            job.status = "CLAIMED"
            job.claim_token = token
            job.lease_until = now + timedelta(seconds=policy.lease_seconds)
            if request.status == "RETRY_WAIT":
                _transition_state(
                    session, request, execution, "PROCESSING", event_type="RETRY_STARTED",
                    details={"retry_job_id": job.id, "attempt": job.attempt_count + 1}, now=now,
                )
            elif request.status == "PROCESSING":
                if execution.lease_until is not None and execution.lease_until > now:
                    job.status = "PENDING"
                    job.claim_token = None
                    job.lease_until = None
                    return _DueClaimResult(None, False)
                request.updated_at = now
                _audit(
                    session, request_id=request.id, event_type="RETRY_RECOVERED",
                    old_state="PROCESSING", new_state="PROCESSING",
                    details={"retry_job_id": job.id, "reason": "claim lease expired"}, now=now,
                )
            else:
                job.status = "COMPLETED"
                job.claim_token = None
                job.lease_until = None
                return _DueClaimResult(None, True)
            execution.lease_token = token
            execution.lease_until = job.lease_until
            execution.updated_at = now
            execution.revision += 1
            try:
                definition, payload = _read_claim_data(session, request)
            except (ConfigurationError, ValueError) as exc:
                _fail_in_transaction(session, request, execution, str(exc), now)
                job.status = "COMPLETED"
                job.claim_token = None
                job.lease_until = None
                return _DueClaimResult(None, True)
            if execution.current_stage != job.stage_id:
                _fail_in_transaction(session, request, execution,
                                     "retry job stage does not match execution stage", now)
                job.status = "COMPLETED"
                job.claim_token = None
                job.lease_until = None
                return _DueClaimResult(None, True)
            claim = _Claim(
                request_id=request.id,
                execution_id=execution.id,
                token=token,
                definition=definition,
                payload=payload,
                config_version=request.config_version,
                retry_job_id=job.id,
                retry_stage_id=job.stage_id,
                retry_attempt_number=job.attempt_count + 1,
            )
    return _DueClaimResult(claim, consumed)


def process_due_retries(
    session_factory: sessionmaker[Session],
    provider: VerificationProvider,
    policy: RetryPolicy,
    *,
    now: datetime | None = None,
    clock: Callable[[], datetime] = utc_now,
) -> int:
    """Process all jobs due at `now` (or current time), returning claims processed."""
    effective_now = now or clock()
    processed = 0
    while True:
        due = _claim_due_retry(session_factory, policy, effective_now)
        if not due.consumed:
            break
        if due.claim is None:
            continue
        processed += 1
        _run_claimed(session_factory, due.claim, provider, policy, clock)
    return processed

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import os
from pathlib import Path
import subprocess
import sys
import shutil
from threading import Event
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

from app.adapters.verification import (
    DependencyCategory,
    Scenario,
    SimulatedVerificationProvider,
    VerificationResult,
)
from app.core.retry_policy import RetryPolicy
from app.domain.lifecycle import validate_transition
from app.main import create_app
from app.persistence.models import (
    AuditEvent,
    Decision,
    RetryJob,
    WorkflowConfig,
    WorkflowExecution,
    WorkflowRequest,
)
from app.persistence.database import Database
from app.services.workflow_executor import _claim_due_retry, process_due_retries


LOAN_DATA = {"applicant": {"age": 24, "monthly_income": 60000, "credit_score": 750}}
VENDOR_DATA = {"vendor": {
    "registration_status": "VALID",
    "compliance": {"tax_clearance": True, "sanctions_clear": True},
    "annual_turnover": 800000,
}}
DEFAULT_POLICY = RetryPolicy(max_attempts=3, base_delay_seconds=15, max_delay_seconds=60)


class RecordingProvider:
    def __init__(self, result: VerificationResult):
        self.result = result
        self.calls: list[dict] = []

    def verify(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


def create_test_app(tmp_path: Path, *, name="execution", provider=None, policy=DEFAULT_POLICY):
    db_path = tmp_path / f"{name}.sqlite3"
    application = create_app(
        database_url=f"sqlite:///{db_path}",
        verification_provider=provider or SimulatedVerificationProvider(),
        retry_policy=policy,
    )
    return application, TestClient(application, raise_server_exceptions=False)


def submit_and_execute(client: TestClient, *, workflow_id="loan_approval", data=None, key="demo"):
    response = client.post("/api/v1/requests", json={
        "workflow_id": workflow_id,
        "data": LOAN_DATA if data is None else data,
    }, headers={"Idempotency-Key": key})
    assert response.status_code == 202, response.text
    accepted = response.json()
    executed = client.post(f"{accepted['status_url']}/execute")
    assert executed.status_code == 200, executed.text
    return accepted, executed.json()


def test_loan_happy_path_approves_and_persists_audited_rule_traces(tmp_path):
    app, client = create_test_app(tmp_path)
    with client:
        accepted, result = submit_and_execute(client)
        assert result["status"] == "APPROVED"
        assert result["current_stage"] == "approved"
        assert result["decision"]["outcome"] == "APPROVED"
        traces = result["decision"]["explanation"]["rule_traces"]
        assert len(traces) == 3
        assert all(trace["passed"] and trace["config_version"] == 2 for trace in traces)
        with app.state.database.session() as session:
            events = session.scalars(select(AuditEvent).where(
                AuditEvent.request_id == accepted["request_id"]
            ).order_by(AuditEvent.sequence)).all()
            assert [event.sequence for event in events] == list(range(1, len(events) + 1))
            assert [event.event_type for event in events] == [
                "REQUEST_RECEIVED", "EXECUTION_STARTED", "RULES_EVALUATED",
                "EXTERNAL_CALL_SUCCEEDED", "DECISION_RECORDED",
            ]
            request = session.get(WorkflowRequest, accepted["request_id"])
            execution = session.scalar(select(WorkflowExecution).where(
                WorkflowExecution.request_id == accepted["request_id"]
            ))
            assert request.status == execution.status == "APPROVED"


def test_rule_rejection_short_circuits_external_call(tmp_path):
    provider = RecordingProvider(VerificationResult(True, False, DependencyCategory.NONE, "ok"))
    app, client = create_test_app(tmp_path, provider=provider)
    rejected_data = {"applicant": {"age": 17, "monthly_income": 60000, "credit_score": 750}}
    with client:
        _accepted, result = submit_and_execute(client, data=rejected_data)
        assert result["status"] == "REJECTED"
        assert result["decision"]["outcome"] == "REJECTED"
        assert provider.calls == []
        traces = result["decision"]["explanation"]["rule_traces"]
        assert traces[0]["rule_id"] == "minimum_age" and not traces[0]["passed"]


def test_manual_review_rule_path_enters_holding_state(tmp_path):
    app, client = create_test_app(tmp_path)
    borderline = {"applicant": {"age": 28, "monthly_income": 50000, "credit_score": 710}}
    with client:
        _accepted, result = submit_and_execute(client, data=borderline)
        assert result["status"] == "MANUAL_REVIEW"
        assert result["current_stage"] == "manual_review"
        assert result["decision"]["outcome"] == "MANUAL_REVIEW"
        assert result["decision"]["explanation"]["rule_traces"][-1]["failure_action"] == "MANUAL_REVIEW"


def test_vendor_workflow_executes_configured_rules_and_external_stage(tmp_path):
    provider = RecordingProvider(VerificationResult(True, False, DependencyCategory.NONE, "verified"))
    app, client = create_test_app(tmp_path, provider=provider)
    with client:
        _accepted, result = submit_and_execute(
            client, workflow_id="vendor_approval", data=VENDOR_DATA
        )
        assert result["status"] == "APPROVED"
        assert [call["operation"] for call in provider.calls] == ["vendor_verification"]
        assert len(result["decision"]["explanation"]["rule_traces"]) == 4


def test_loan_versions_keep_distinct_decision_behavior(tmp_path):
    app, client = create_test_app(tmp_path)
    borderline = {"applicant": {"age": 28, "monthly_income": 50000, "credit_score": 710}}
    with client:
        with app.state.database.session() as session:
            with session.begin():
                v2 = session.get(WorkflowConfig, ("loan_approval", 2))
                v1 = session.get(WorkflowConfig, ("loan_approval", 1))
                v2.is_active = False
                session.flush()
                v1.is_active = True
        _one, v1_result = submit_and_execute(client, data=borderline, key="v1")
        assert v1_result["config_version"] == 1 and v1_result["status"] == "APPROVED"
        with app.state.database.session() as session:
            with session.begin():
                v1 = session.get(WorkflowConfig, ("loan_approval", 1))
                v2 = session.get(WorkflowConfig, ("loan_approval", 2))
                v1.is_active = False
                session.flush()
                v2.is_active = True
        _two, v2_result = submit_and_execute(client, data=borderline, key="v2")
        assert v2_result["config_version"] == 2 and v2_result["status"] == "MANUAL_REVIEW"


def test_permanent_external_failure_uses_configured_fallback_without_retry(tmp_path):
    provider = SimulatedVerificationProvider(Scenario.PERMANENT_FAILURE)
    app, client = create_test_app(tmp_path, provider=provider)
    with client:
        _accepted, result = submit_and_execute(client)
        assert result["status"] == "MANUAL_REVIEW"
        assert result["decision"]["outcome"] == "MANUAL_REVIEW"
        with app.state.database.session() as session:
            assert session.scalar(select(func.count()).select_from(RetryJob)) == 0


def test_temporary_failure_enters_durable_retry_wait_and_repeated_trigger_is_safe(tmp_path):
    provider = SimulatedVerificationProvider(Scenario.TEMPORARY_FAILURE)
    app, client = create_test_app(tmp_path, provider=provider)
    with client:
        accepted = client.post("/api/v1/requests", json={
            "workflow_id": "loan_approval", "data": LOAN_DATA
        }, headers={"Idempotency-Key": "temporary"}).json()
        first = client.post(f"{accepted['status_url']}/execute").json()
        assert first["status"] == "RETRY_WAIT"
        second = client.post(f"{accepted['status_url']}/execute").json()
        assert second["status"] == "RETRY_WAIT"
        with app.state.database.session() as session:
            job = session.scalar(select(RetryJob))
            assert job.status == "PENDING" and job.attempt_count == 1
            assert job.operation_key.startswith("flowguard:loan_approval:2:")
            assert job.next_run_at.tzinfo is not None


def test_retry_recovers_after_transient_failure_without_sleep(tmp_path):
    provider = SimulatedVerificationProvider(Scenario.FAIL_THEN_RECOVER, fail_attempts=1)
    app, client = create_test_app(tmp_path, provider=provider)
    with client:
        accepted = client.post("/api/v1/requests", json={
            "workflow_id": "loan_approval", "data": LOAN_DATA
        }, headers={"Idempotency-Key": "recover"}).json()
        waiting = client.post(f"{accepted['status_url']}/execute").json()
        assert waiting["status"] == "RETRY_WAIT"
        with app.state.database.session() as session:
            job = session.scalar(select(RetryJob))
            due_at = job.next_run_at + timedelta(seconds=1)
        count = process_due_retries(
            app.state.database.session_factory, provider, app.state.retry_policy,
            now=due_at, clock=lambda: due_at,
        )
        assert count == 1
        final = client.get(accepted["status_url"]).json()
        assert final["status"] == "APPROVED"
        assert final["decision"]["outcome"] == "APPROVED"
        with app.state.database.session() as session:
            job = session.scalar(select(RetryJob))
            assert job.status == "COMPLETED" and job.attempt_count == 2
            event_count = session.scalar(select(func.count()).select_from(AuditEvent).where(
                AuditEvent.request_id == accepted["request_id"]
            ))
        assert process_due_retries(
            app.state.database.session_factory, provider, app.state.retry_policy,
            now=due_at + timedelta(seconds=1), clock=lambda: due_at + timedelta(seconds=1),
        ) == 0
        with app.state.database.session() as session:
            assert session.scalar(select(func.count()).select_from(AuditEvent).where(
                AuditEvent.request_id == accepted["request_id"]
            )) == event_count
            assert session.scalar(select(func.count()).select_from(Decision)) == 1


def test_retry_exhaustion_follows_yaml_fallback_to_manual_review(tmp_path):
    provider = SimulatedVerificationProvider(Scenario.TEMPORARY_FAILURE)
    policy = RetryPolicy(max_attempts=2, base_delay_seconds=5, max_delay_seconds=20)
    app, client = create_test_app(tmp_path, provider=provider, policy=policy)
    with client:
        accepted = client.post("/api/v1/requests", json={
            "workflow_id": "loan_approval", "data": LOAN_DATA
        }, headers={"Idempotency-Key": "exhaust"}).json()
        assert client.post(f"{accepted['status_url']}/execute").json()["status"] == "RETRY_WAIT"
        with app.state.database.session() as session:
            due_at = session.scalar(select(RetryJob)).next_run_at + timedelta(seconds=1)
        assert process_due_retries(
            app.state.database.session_factory, provider, policy,
            now=due_at, clock=lambda: due_at,
        ) == 1
        final = client.get(accepted["status_url"]).json()
        assert final["status"] == "MANUAL_REVIEW"
        assert final["decision"]["outcome"] == "MANUAL_REVIEW"
        with app.state.database.session() as session:
            job = session.scalar(select(RetryJob))
            assert job.status == "COMPLETED" and job.attempt_count == 2
            assert len(session.scalars(select(Decision).where(
                Decision.request_id == accepted["request_id"]
            )).all()) == 1


def test_retry_job_survives_new_app_and_database_sessions(tmp_path):
    database_path = tmp_path / "restart.sqlite3"
    database_url = f"sqlite:///{database_path}"
    policy = RetryPolicy(max_attempts=3, base_delay_seconds=30, max_delay_seconds=60)
    first_provider = SimulatedVerificationProvider(Scenario.FAIL_THEN_RECOVER, fail_attempts=1)
    first_app = create_app(database_url=database_url, verification_provider=first_provider,
                           retry_policy=policy)
    with TestClient(first_app, raise_server_exceptions=False) as first_client:
        accepted = first_client.post("/api/v1/requests", json={
            "workflow_id": "loan_approval", "data": LOAN_DATA
        }, headers={"Idempotency-Key": "restart"}).json()
        assert first_client.post(f"{accepted['status_url']}/execute").json()["status"] == "RETRY_WAIT"
        with first_app.state.database.session() as session:
            due_at = session.scalar(select(RetryJob)).next_run_at + timedelta(seconds=1)

    recovered_provider = SimulatedVerificationProvider(Scenario.FAIL_THEN_RECOVER, fail_attempts=1)
    second_app = create_app(database_url=database_url, verification_provider=recovered_provider,
                            retry_policy=policy)
    with TestClient(second_app, raise_server_exceptions=False) as second_client:
        with second_app.state.database.session() as session:
            pending = session.scalar(select(RetryJob))
            assert pending.status == "PENDING" and pending.attempt_count == 1
        assert process_due_retries(
            second_app.state.database.session_factory, recovered_provider, policy,
            now=due_at, clock=lambda: due_at,
        ) == 1
        assert second_client.get(accepted["status_url"]).json()["status"] == "APPROVED"


def test_retry_worker_cli_processes_a_persisted_due_job(tmp_path):
    database_path = tmp_path / "worker-cli.sqlite3"
    database_url = f"sqlite:///{database_path.as_posix()}"
    policy = RetryPolicy(max_attempts=3, base_delay_seconds=0, max_delay_seconds=0)
    initial_provider = SimulatedVerificationProvider(Scenario.FAIL_THEN_RECOVER, fail_attempts=1)
    app = create_app(database_url=database_url, verification_provider=initial_provider,
                     retry_policy=policy)
    with TestClient(app, raise_server_exceptions=False) as client:
        accepted = client.post("/api/v1/requests", json={
            "workflow_id": "loan_approval", "data": LOAN_DATA
        }, headers={"Idempotency-Key": "cli-worker"}).json()
        assert client.post(f"{accepted['status_url']}/execute").json()["status"] == "RETRY_WAIT"

    environment = os.environ.copy()
    environment.update({
        "FLOWGUARD_DATABASE_URL": database_url,
        "FLOWGUARD_SIMULATOR_SCENARIO": "FAIL_THEN_RECOVER",
        "FLOWGUARD_SIMULATOR_FAIL_ATTEMPTS": "1",
        "FLOWGUARD_RETRY_MAX_ATTEMPTS": "3",
        "FLOWGUARD_RETRY_BASE_DELAY_SECONDS": "0",
        "FLOWGUARD_RETRY_MAX_DELAY_SECONDS": "0",
    })
    completed = subprocess.run(
        [sys.executable, "-m", "app.workers.retry_worker", "--once"],
        cwd=Path(__file__).parents[2], env=environment,
        capture_output=True, text=True, timeout=20, check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "processed 1 due retry job" in completed.stdout

    database = Database(database_url)
    try:
        with database.session() as session:
            request = session.get(WorkflowRequest, accepted["request_id"])
            job = session.scalar(select(RetryJob))
            decision = session.scalar(select(Decision).where(
                Decision.request_id == accepted["request_id"]
            ))
            assert request.status == "APPROVED"
            assert job.status == "COMPLETED" and job.attempt_count == 2
            assert decision.outcome == "APPROVED"
    finally:
        database.dispose()


def test_expired_worker_claim_is_recovered_after_crash(tmp_path):
    provider = SimulatedVerificationProvider(Scenario.FAIL_THEN_RECOVER, fail_attempts=1)
    app, client = create_test_app(tmp_path, provider=provider)
    with client:
        accepted = client.post("/api/v1/requests", json={
            "workflow_id": "loan_approval", "data": LOAN_DATA
        }, headers={"Idempotency-Key": "expired-lease"}).json()
        assert client.post(f"{accepted['status_url']}/execute").json()["status"] == "RETRY_WAIT"
        with app.state.database.session() as session:
            due_at = session.scalar(select(RetryJob)).next_run_at + timedelta(seconds=1)
        # Claim the retry as if a worker started, then simulate process death before
        # its provider result is committed. The durable leases expire and another worker recovers.
        claimed = _claim_due_retry(app.state.database.session_factory, app.state.retry_policy, due_at)
        assert claimed.claim is not None
        recovery_time = due_at + timedelta(seconds=app.state.retry_policy.lease_seconds + 1)
        with app.state.database.session() as session:
            with session.begin():
                job = session.scalar(select(RetryJob))
                execution = session.scalar(select(WorkflowExecution).where(
                    WorkflowExecution.request_id == accepted["request_id"]
                ))
                job.lease_until = recovery_time - timedelta(seconds=1)
                execution.lease_until = recovery_time - timedelta(seconds=1)
        assert process_due_retries(
            app.state.database.session_factory, provider, app.state.retry_policy,
            now=recovery_time, clock=lambda: recovery_time,
        ) == 1
        final = client.get(accepted["status_url"]).json()
        assert final["status"] == "APPROVED"
        with app.state.database.session() as session:
            recovery_events = session.scalars(select(AuditEvent).where(
                AuditEvent.request_id == accepted["request_id"],
                AuditEvent.event_type == "RETRY_RECOVERED",
            )).all()
            assert len(recovery_events) == 1


def test_duplicate_execution_does_not_duplicate_decision_or_audit(tmp_path):
    provider = RecordingProvider(VerificationResult(True, False, DependencyCategory.NONE, "ok"))
    app, client = create_test_app(tmp_path, provider=provider)
    with client:
        accepted, first = submit_and_execute(client)
        first_count = first["revision"]
        second = client.post(f"{accepted['status_url']}/execute").json()
        assert second["status"] == "APPROVED" and second["revision"] == first_count
        assert len(provider.calls) == 1
        with app.state.database.session() as session:
            assert session.scalar(select(func.count()).select_from(Decision)) == 1
            assert session.scalar(select(func.count()).select_from(AuditEvent)) == 5


def test_external_provider_is_called_with_no_checked_out_database_connection(tmp_path):
    class ConnectionCheckingProvider:
        engine = None
        observed: list[int] = []

        def verify(self, **_kwargs):
            checked_out = self.engine.pool.checkedout()
            self.observed.append(checked_out)
            assert checked_out == 0
            return VerificationResult(True, False, DependencyCategory.NONE, "ok")

    provider = ConnectionCheckingProvider()
    app, client = create_test_app(tmp_path, provider=provider)
    provider.engine = app.state.database.engine
    with client:
        _accepted, result = submit_and_execute(client)
        assert result["status"] == "APPROVED"
        assert provider.observed == [0]


def test_unexpected_provider_exception_is_treated_as_retryable_technical_failure(tmp_path):
    class BrokenProvider:
        def verify(self, **_kwargs):
            raise TimeoutError("private provider detail")

    app, client = create_test_app(tmp_path, provider=BrokenProvider())
    with client:
        accepted = client.post("/api/v1/requests", json={
            "workflow_id": "loan_approval", "data": LOAN_DATA
        }, headers={"Idempotency-Key": "provider-exception"}).json()
        result = client.post(f"{accepted['status_url']}/execute").json()
        assert result["status"] == "RETRY_WAIT"
        assert "private provider detail" not in str(result)
        assert result["decision"] is None


def test_execution_claim_commit_failure_rolls_back_status_and_audit(tmp_path):
    app, client = create_test_app(tmp_path)
    with client:
        accepted = client.post("/api/v1/requests", json={
            "workflow_id": "loan_approval", "data": LOAN_DATA
        }, headers={"Idempotency-Key": "execution-rollback"}).json()

        def fail_commit(_session):
            raise RuntimeError("injected execution transaction failure")

        event.listen(Session, "before_commit", fail_commit)
        try:
            response = client.post(f"{accepted['status_url']}/execute")
        finally:
            event.remove(Session, "before_commit", fail_commit)
        assert response.status_code == 500
        with app.state.database.session() as session:
            request = session.get(WorkflowRequest, accepted["request_id"])
            execution = session.scalar(select(WorkflowExecution).where(
                WorkflowExecution.request_id == accepted["request_id"]
            ))
            assert request.status == execution.status == "RECEIVED"
            assert execution.lease_token is None
            assert session.scalar(select(func.count()).select_from(AuditEvent).where(
                AuditEvent.request_id == request.id
            )) == 1


def test_lifecycle_rejects_illegal_transition():
    with pytest.raises(ValueError, match="illegal lifecycle transition"):
        validate_transition("RECEIVED", "APPROVED")
    validate_transition("RETRY_WAIT", "MANUAL_REVIEW")


def test_missing_execution_trigger_request_returns_404(tmp_path):
    _app, client = create_test_app(tmp_path)
    with client:
        response = client.post(f"/api/v1/requests/{UUID(int=999)}/execute")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"


def test_invalid_persisted_current_stage_fails_safely(tmp_path):
    app, client = create_test_app(tmp_path)
    with client:
        accepted = client.post("/api/v1/requests", json={
            "workflow_id": "loan_approval", "data": LOAN_DATA
        }, headers={"Idempotency-Key": "invalid-stage"}).json()
        with app.state.database.session() as session:
            with session.begin():
                execution = session.scalar(select(WorkflowExecution).where(
                    WorkflowExecution.request_id == accepted["request_id"]
                ))
                execution.current_stage = "not-in-pinned-config"
        result = client.post(f"{accepted['status_url']}/execute").json()
        assert result["status"] == "FAILED"
        assert result["current_stage"] == "not-in-pinned-config"
        assert result["decision"] is None


def test_missing_execution_record_is_repaired_to_failed_with_one_audit_event(tmp_path):
    app, client = create_test_app(tmp_path)
    with client:
        accepted = client.post("/api/v1/requests", json={
            "workflow_id": "loan_approval", "data": LOAN_DATA
        }, headers={"Idempotency-Key": "missing-execution"}).json()
        with app.state.database.session() as session:
            with session.begin():
                execution = session.scalar(select(WorkflowExecution).where(
                    WorkflowExecution.request_id == accepted["request_id"]
                ))
                session.delete(execution)
        result = client.post(f"{accepted['status_url']}/execute").json()
        assert result["status"] == "FAILED"
        with app.state.database.session() as session:
            audit = session.scalars(select(AuditEvent).where(
                AuditEvent.request_id == accepted["request_id"]
            ).order_by(AuditEvent.sequence)).all()
            assert [row.sequence for row in audit] == [1, 2]
            assert audit[-1].new_state == "FAILED"


def test_runtime_missing_configured_failure_transition_becomes_failed(tmp_path):
    import yaml

    source_root = Path(__file__).parents[2]
    workflow_dir = tmp_path / "workflows"
    schema_dir = tmp_path / "schemas"
    workflow_dir.mkdir()
    schema_dir.mkdir()
    workflow_data = yaml.safe_load(
        (source_root / "configs/workflows/loan_approval_v2.yaml").read_text(encoding="utf-8")
    )
    workflow_data["transitions"] = [
        edge for edge in workflow_data["transitions"]
        if not (edge["from_stage"] == "identity_check" and edge["outcome"] == "FAILURE")
    ]
    (workflow_dir / "loan_approval_v2.yaml").write_text(
        yaml.safe_dump(workflow_data), encoding="utf-8"
    )
    shutil.copyfile(source_root / "configs/input_schemas/loan_approval_v2.yaml",
                    schema_dir / "loan_approval_v2.yaml")
    app = create_app(
        database_url=f"sqlite:///{(tmp_path / 'bad-transition.sqlite3').as_posix()}",
        workflow_config_dir=workflow_dir,
        input_schema_dir=schema_dir,
        verification_provider=SimulatedVerificationProvider(Scenario.PERMANENT_FAILURE),
    )
    client = TestClient(app, raise_server_exceptions=False)
    with client:
        accepted = client.post("/api/v1/requests", json={
            "workflow_id": "loan_approval", "data": LOAN_DATA
        }, headers={"Idempotency-Key": "missing-transition"}).json()
        response = client.post(f"{accepted['status_url']}/execute")
        assert response.status_code == 200
        assert response.json()["status"] == "FAILED"


def test_concurrent_execute_triggers_claim_once(tmp_path):
    started = Event()
    release = Event()

    class BlockingProvider:
        calls = 0

        def verify(self, **_kwargs):
            self.calls += 1
            started.set()
            assert release.wait(timeout=5)
            return VerificationResult(True, False, DependencyCategory.NONE, "ok")

    provider = BlockingProvider()
    app, client = create_test_app(tmp_path, provider=provider)
    with client:
        accepted = client.post("/api/v1/requests", json={
            "workflow_id": "loan_approval", "data": LOAN_DATA
        }, headers={"Idempotency-Key": "concurrent-execution"}).json()
        url = f"{accepted['status_url']}/execute"
        with ThreadPoolExecutor(max_workers=1) as pool:
            first = pool.submit(client.post, url)
            assert started.wait(timeout=5)
            second = client.post(url)
            assert second.status_code == 200
            assert second.json()["status"] == "PROCESSING"
            release.set()
            completed = first.result(timeout=5)
        assert completed.status_code == 200
        assert completed.json()["status"] == "APPROVED"
        assert provider.calls == 1


def test_max_attempts_counts_initial_external_attempt(tmp_path):
    # With total attempts set to one, the initial call exhausts the limit and follows
    # the configured FAILURE fallback without scheduling a retry job.
    # A temp path isolates this check from the developer database.
    policy = RetryPolicy(max_attempts=1, base_delay_seconds=1)
    provider = SimulatedVerificationProvider(Scenario.TEMPORARY_FAILURE)
    app, client = create_test_app(tmp_path, name="attempt-count", provider=provider, policy=policy)
    with client:
        _accepted, result = submit_and_execute(client)
        assert result["status"] == "MANUAL_REVIEW"
        external = result["decision"]["explanation"]["external_results"]
        assert len(external) == 1 and external[0]["attempt"] == 1
        with app.state.database.session() as session:
            assert session.scalar(select(func.count()).select_from(RetryJob)) == 0


def test_retry_policy_uses_capped_exponential_backoff():
    policy = RetryPolicy(max_attempts=5, base_delay_seconds=10, max_delay_seconds=25)
    assert [policy.delay_after(attempt) for attempt in (1, 2, 3, 4)] == [10, 20, 25, 25]

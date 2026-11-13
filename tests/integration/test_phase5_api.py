from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.adapters.verification import DependencyCategory, VerificationResult
from app.core.retry_policy import RetryPolicy
from app.main import create_app
from app.persistence.models import AdminAuditEvent, AuditEvent, Decision, WorkflowConfig, WorkflowRequest
from app.services.workflow_executor import process_due_retries


TOKEN = "test-admin-token"
GOOD_LOAN = {"workflow_id": "loan_approval", "data": {"applicant": {
    "age": 24, "monthly_income": 60000, "credit_score": 750,
}}}
REVIEW_LOAN = {"workflow_id": "loan_approval", "data": {"applicant": {
    "age": 24, "monthly_income": 60000, "credit_score": 710,
}}}
ADMIN = {"X-Admin-Token": TOKEN}


def make_app(tmp_path: Path, *, name="phase5", provider=None, policy=None, token=TOKEN):
    app = create_app(
        database_url=f"sqlite:///{tmp_path / (name + '.sqlite3')}",
        verification_provider=provider,
        retry_policy=policy or RetryPolicy(max_attempts=3, base_delay_seconds=0,
                                          max_delay_seconds=0),
        admin_token=token,
    )
    return app, TestClient(app, raise_server_exceptions=False)


def post_request(client, payload=GOOD_LOAN, key=None):
    response = client.post("/api/v1/requests", json=payload,
                           headers={"Idempotency-Key": key or str(uuid4())})
    assert response.status_code == 202, response.text
    created = response.json()
    return created, client.post(f"{created['status_url']}/execute")


def activate(client, version):
    return client.post("/api/v1/admin/workflows/activate", json={
        "workflow_id": "loan_approval", "version": version,
    }, headers=ADMIN)


def test_audit_is_ordered_and_contains_rules_and_external_call(tmp_path):
    app, client = make_app(tmp_path)
    with client:
        created, execution = post_request(client)
        assert execution.status_code == 200 and execution.json()["status"] == "APPROVED"
        response = client.get(f"/api/v1/requests/{created['request_id']}/audit")
        assert response.status_code == 200
        events = response.json()
        assert [event["sequence"] for event in events] == list(range(1, len(events) + 1))
        assert events[0]["event_type"] == "REQUEST_RECEIVED"
        assert "RULES_EVALUATED" in [event["event_type"] for event in events]
        assert "EXTERNAL_CALL_SUCCEEDED" in [event["event_type"] for event in events]
        assert all(event["config_version"] == 2 for event in events)
        assert next(event for event in events if event["event_type"] == "RULES_EVALUATED")["stage"] == "eligibility"


def test_audit_contains_failed_attempt_retry_schedule_and_recovery(tmp_path):
    class FailOnce:
        def __init__(self):
            self.lock = Lock()
            self.calls = 0

        def verify(self, **_kwargs):
            with self.lock:
                self.calls += 1
                attempt = self.calls
            if attempt == 1:
                return VerificationResult(False, True, DependencyCategory.TIMEOUT,
                                          "temporary")
            return VerificationResult(True, False, DependencyCategory.NONE, "verified")

    app, client = make_app(tmp_path, provider=FailOnce())
    with client:
        created, result = post_request(client)
        assert result.json()["status"] == "RETRY_WAIT"
        assert process_due_retries(app.state.database.session_factory,
                                   app.state.verification_provider, app.state.retry_policy) == 1
        events = client.get(f"/api/v1/requests/{created['request_id']}/audit").json()
        names = [event["event_type"] for event in events]
        assert "RETRY_SCHEDULED" in names
        assert "EXTERNAL_CALL_SUCCEEDED" in names
        assert [event["sequence"] for event in events] == list(range(1, len(events) + 1))


def test_unknown_request_audit_and_explanation_are_404(tmp_path):
    _app, client = make_app(tmp_path)
    with client:
        missing = str(uuid4())
        assert client.get(f"/api/v1/requests/{missing}/audit").status_code == 404
        assert client.get(f"/api/v1/requests/{missing}/explanation").status_code == 404


def test_approved_and_rejected_explanations_are_persisted(tmp_path):
    _app, client = make_app(tmp_path)
    with client:
        approved, result = post_request(client)
        assert result.json()["status"] == "APPROVED"
        explanation = client.get(f"/api/v1/requests/{approved['request_id']}/explanation").json()
        assert explanation["decision_outcome"] == "APPROVED" and not explanation["pending"]
        assert len(explanation["rule_traces"]) == 3
        rejected_payload = {"workflow_id": "loan_approval", "data": {"applicant": {
            "age": 17, "monthly_income": 60000, "credit_score": 750,
        }}}
        rejected, result = post_request(client, rejected_payload)
        assert result.json()["status"] == "REJECTED"
        explanation = client.get(f"/api/v1/requests/{rejected['request_id']}/explanation").json()
        assert explanation["decision_outcome"] == "REJECTED"
        assert "minimum_age" in explanation["summary"]


def test_manual_review_explanation_is_pending_without_final_outcome(tmp_path):
    _app, client = make_app(tmp_path)
    with client:
        created, result = post_request(client, REVIEW_LOAN)
        assert result.json()["status"] == "MANUAL_REVIEW"
        explanation = client.get(f"/api/v1/requests/{created['request_id']}/explanation").json()
        assert explanation["decision_outcome"] is None
        assert explanation["pending"] is True
        assert "awaiting a reviewer" in explanation["summary"]


def test_retry_wait_explanation_is_pending(tmp_path):
    class AlwaysTemporary:
        def verify(self, **_kwargs):
            return VerificationResult(False, True, DependencyCategory.TIMEOUT,
                                      "temporary")

    _app, client = make_app(tmp_path, provider=AlwaysTemporary())
    with client:
        created, result = post_request(client)
        assert result.json()["status"] == "RETRY_WAIT"
        explanation = client.get(f"/api/v1/requests/{created['request_id']}/explanation").json()
        assert explanation["pending"] is True and explanation["decision_outcome"] is None
        assert len(explanation["external_results"]) == 1


def test_review_approve_reject_auth_replay_and_conflict(tmp_path):
    app, client = make_app(tmp_path)
    with client:
        approved, status = post_request(client, REVIEW_LOAN)
        rejected, _status = post_request(client, REVIEW_LOAN)
        assert status.json()["status"] == "MANUAL_REVIEW"
        assert len(client.get("/api/v1/reviews", headers=ADMIN).json()) == 2
        endpoint = f"/api/v1/reviews/{approved['request_id']}/resolve"
        assert client.post(endpoint, json={"action": "APPROVE", "reason": "verified documents"}).status_code == 401
        with app.state.database.session() as session:
            audit_before = session.scalar(select(func.count()).select_from(AuditEvent).where(
                AuditEvent.request_id == approved["request_id"]))
        response = client.post(endpoint, json={"action": "APPROVE", "reason": "verified documents"}, headers=ADMIN)
        assert response.status_code == 200 and response.json()["status"] == "APPROVED"
        with app.state.database.session() as session:
            decision_count = session.scalar(select(func.count()).select_from(Decision).where(
                Decision.request_id == approved["request_id"]))
            assert decision_count == 1
        replay = client.post(endpoint, json={"action": "APPROVE", "reason": "verified documents"}, headers=ADMIN)
        assert replay.status_code == 200 and replay.json()["replayed"] is True
        conflict = client.post(endpoint, json={"action": "REJECT", "reason": "changed mind"}, headers=ADMIN)
        assert conflict.status_code == 409
        rejected_response = client.post(
            f"/api/v1/reviews/{rejected['request_id']}/resolve",
            json={"action": "REJECT", "reason": "risk not accepted"}, headers=ADMIN,
        )
        assert rejected_response.status_code == 200 and rejected_response.json()["status"] == "REJECTED"
        with app.state.database.session() as session:
            audit_rows = session.scalars(select(AuditEvent).where(
                AuditEvent.request_id == approved["request_id"]).order_by(AuditEvent.sequence)).all()
            assert len(audit_rows) == audit_before + 1, [row.event_type for row in audit_rows]
            decision = session.scalar(select(Decision).where(Decision.request_id == approved["request_id"]))
            assert len(decision.explanation["rule_traces"]) == 3
            assert decision.explanation["review_resolution"]["actor"] == "demo-admin"


def test_concurrent_conflicting_review_actions_only_one_wins(tmp_path):
    _app, client = make_app(tmp_path)
    with client:
        created, _ = post_request(client, REVIEW_LOAN)
        path = f"/api/v1/reviews/{created['request_id']}/resolve"
        def resolve(action):
            return client.post(path, json={"action": action, "reason": action.lower()}, headers=ADMIN).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            codes = list(pool.map(resolve, ["APPROVE", "REJECT"]))
        assert sorted(codes) == [200, 409]


def test_review_requires_pending_manual_state(tmp_path):
    _app, client = make_app(tmp_path)
    with client:
        created, _ = post_request(client)
        response = client.post(f"/api/v1/reviews/{created['request_id']}/resolve",
                               json={"action": "APPROVE", "reason": "ok"}, headers=ADMIN)
        assert response.status_code == 409


def test_activation_changes_new_intake_preserves_old_pin_and_versions(tmp_path):
    app, client = make_app(tmp_path)
    with client:
        assert activate(client, 1).json()["active_version"] == 1
        old, old_result = post_request(client, REVIEW_LOAN, key="version-one")
        assert old_result.json()["status"] == "APPROVED"
        assert activate(client, 2).json()["active_version"] == 2
        new, new_result = post_request(client, REVIEW_LOAN, key="version-two")
        assert new_result.json()["status"] == "MANUAL_REVIEW"
        assert old["config_version"] == 1 and new["config_version"] == 2
        old_explanation = client.get(f"/api/v1/requests/{old['request_id']}/explanation").json()
        assert old_explanation["config_version"] == 1
        versions = client.get("/api/v1/workflows/loan_approval/versions").json()
        assert [(row["version"], row["is_active"]) for row in versions] == [(2, True), (1, False)]
        with app.state.database.session() as session:
            events = session.scalars(select(AdminAuditEvent).where(
                AdminAuditEvent.workflow_id == "loan_approval").order_by(AdminAuditEvent.created_at)).all()
            assert [(event.old_version, event.new_version, event.actor) for event in events] == [
                (2, 1, "demo-admin"), (1, 2, "demo-admin")]


def test_activation_persists_across_app_restart_and_startup_keeps_selection(tmp_path):
    database_path = tmp_path / "restart.sqlite3"
    url = f"sqlite:///{database_path}"
    app, client = make_app(tmp_path, name="restart")
    with client:
        assert activate(client, 1).status_code == 200
    app.state.database.dispose()
    restarted = create_app(database_url=url, admin_token=TOKEN)
    with TestClient(restarted) as restarted_client:
        versions = restarted_client.get("/api/v1/workflows/loan_approval/versions").json()
        assert next(row["version"] for row in versions if row["is_active"]) == 1
        created = restarted_client.post("/api/v1/requests", json=REVIEW_LOAN,
                                        headers={"Idempotency-Key": "after-restart"})
        assert created.json()["config_version"] == 1


def test_activation_validation_auth_and_idempotency(tmp_path):
    app, client = make_app(tmp_path)
    with client:
        unauthorized = client.post("/api/v1/admin/workflows/activate",
                                   json={"workflow_id": "loan_approval", "version": 1})
        assert unauthorized.status_code == 401
        bad = activate(client, 999)
        assert bad.status_code == 404
        assert activate(client, 1).json()["changed"] is True
        assert activate(client, 1).json()["changed"] is False
        with app.state.database.session() as session:
            assert session.scalar(select(func.count()).select_from(AdminAuditEvent)) == 1


def test_activation_rejects_tampered_snapshot(tmp_path):
    app, client = make_app(tmp_path)
    with client:
        with app.state.database.session() as session:
            row = session.get(WorkflowConfig, ("loan_approval", 1))
            row.configuration = {**row.configuration, "tampered": True}
            session.commit()
        response = activate(client, 1)
        assert response.status_code == 422

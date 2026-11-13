from __future__ import annotations

import copy
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

from app.main import create_app
from app.persistence.models import AdminAuditEvent, AuditEvent, Decision, WorkflowConfig, WorkflowRequest
from app.persistence.repositories import synchronize_workflow_snapshots
from app.services.configuration_snapshots import configuration_checksum


TOKEN = "phase6-test-token"
HEADERS = {"X-Admin-Token": TOKEN}
REVIEW_PAYLOAD = {"workflow_id": "loan_approval", "data": {"applicant": {
    "age": 24, "monthly_income": 60000, "credit_score": 710,
}}}
GOOD_PAYLOAD = {"workflow_id": "loan_approval", "data": {"applicant": {
    "age": 24, "monthly_income": 60000, "credit_score": 750,
}}}


def new_app(tmp_path: Path, name: str = "phase6", token: str | None = TOKEN):
    return create_app(database_url=f"sqlite:///{tmp_path / (name + '.sqlite3')}", admin_token=token)


def submit(client: TestClient, payload: dict, key: str):
    response = client.post("/api/v1/requests", json=payload,
                           headers={"Idempotency-Key": key})
    assert response.status_code == 202, response.text
    created = response.json()
    executed = client.post(f"{created['status_url']}/execute")
    assert executed.status_code == 200, executed.text
    return created, executed.json()


def test_admin_wrong_token_is_forbidden_and_never_echoed(tmp_path):
    app = new_app(tmp_path)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/v1/admin/workflows/activate",
            json={"workflow_id": "loan_approval", "version": 1},
            headers={"X-Admin-Token": "not-the-secret"},
        )
        assert response.status_code == 403
        assert "not-the-secret" not in response.text
        assert client.get("/api/v1/reviews", headers={"X-Admin-Token": "not-the-secret"}).status_code == 403


def test_admin_routes_fail_closed_when_server_token_is_unconfigured(tmp_path):
    app = new_app(tmp_path, token="")
    with TestClient(app, raise_server_exceptions=False) as client:
        headers = {"X-Admin-Token": "anything"}
        assert client.get("/api/v1/reviews", headers=headers).status_code == 503
        assert client.post("/api/v1/admin/workflows/activate", json={
            "workflow_id": "loan_approval", "version": 1,
        }, headers=headers).status_code == 503


def test_review_commit_failure_rolls_back_status_decision_and_audit(tmp_path):
    app = new_app(tmp_path)
    with TestClient(app, raise_server_exceptions=False) as client:
        created, result = submit(client, REVIEW_PAYLOAD, "review-rollback")
        assert result["status"] == "MANUAL_REVIEW"
        request_id = created["request_id"]
        with app.state.database.session() as session:
            audit_count_before = session.scalar(select(func.count()).select_from(AuditEvent).where(
                AuditEvent.request_id == request_id))

        def fail_commit(_session):
            raise RuntimeError("injected review commit failure")

        event.listen(Session, "before_commit", fail_commit)
        try:
            response = client.post(
                f"/api/v1/reviews/{request_id}/resolve",
                json={"action": "APPROVE", "reason": "checked"}, headers=HEADERS,
            )
        finally:
            event.remove(Session, "before_commit", fail_commit)
        assert response.status_code == 500
        with app.state.database.session() as session:
            request = session.get(WorkflowRequest, request_id)
            decision = session.scalar(select(Decision).where(Decision.request_id == request_id))
            assert request.status == "MANUAL_REVIEW"
            assert decision.outcome == "MANUAL_REVIEW"
            assert "review_resolution" not in decision.explanation
            assert session.scalar(select(func.count()).select_from(AuditEvent).where(
                AuditEvent.request_id == request_id)) == audit_count_before


def test_activation_commit_failure_preserves_old_active_version_and_no_admin_event(tmp_path):
    app = new_app(tmp_path)
    with TestClient(app, raise_server_exceptions=False) as client:
        def fail_commit(_session):
            raise RuntimeError("injected activation commit failure")

        event.listen(Session, "before_commit", fail_commit)
        try:
            response = client.post(
                "/api/v1/admin/workflows/activate",
                json={"workflow_id": "loan_approval", "version": 1}, headers=HEADERS,
            )
        finally:
            event.remove(Session, "before_commit", fail_commit)
        assert response.status_code == 500
        versions = client.get("/api/v1/workflows/loan_approval/versions").json()
        assert next(row["version"] for row in versions if row["is_active"]) == 2
        with app.state.database.session() as session:
            assert session.scalar(select(func.count()).select_from(AdminAuditEvent)) == 0


def test_newly_discovered_version_registers_inactive_without_overriding_active(tmp_path):
    app = new_app(tmp_path)
    with TestClient(app) as client:
        assert client.post("/api/v1/admin/workflows/activate", json={
            "workflow_id": "loan_approval", "version": 1,
        }, headers=HEADERS).status_code == 200
        v2 = next(copy.deepcopy(row) for row in app.state.config_snapshots
                  if row["workflow_id"] == "loan_approval" and row["version"] == 2)
        v3 = copy.deepcopy(v2)
        v3["version"] = 3
        v3["configuration"]["workflow"]["version"] = 3
        v3["checksum"] = configuration_checksum(v3["configuration"])
        with app.state.database.session() as session:
            with session.begin():
                synchronize_workflow_snapshots(session, [*app.state.config_snapshots, v3])
        versions = client.get("/api/v1/workflows/loan_approval/versions").json()
        assert [(row["version"], row["is_active"]) for row in versions] == [
            (3, False), (2, False), (1, True),
        ]


def test_finalized_execution_replay_keeps_single_decision_and_audit_history(tmp_path):
    app = new_app(tmp_path)
    with TestClient(app) as client:
        created, result = submit(client, GOOD_PAYLOAD, "final-replay")
        assert result["status"] == "APPROVED"
        request_id = created["request_id"]
        audit_before = client.get(f"/api/v1/requests/{request_id}/audit").json()
        replay = client.post(f"{created['status_url']}/execute")
        assert replay.status_code == 200 and replay.json()["status"] == "APPROVED"
        audit_after = client.get(f"/api/v1/requests/{request_id}/audit").json()
        assert audit_after == audit_before
        with app.state.database.session() as session:
            assert session.scalar(select(func.count()).select_from(Decision).where(
                Decision.request_id == request_id)) == 1

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.main import create_app
from app.persistence.models import AuditEvent, Decision, WorkflowConfig, WorkflowExecution, WorkflowRequest
from app.persistence.repositories import synchronize_workflow_snapshots
from app.services.request_intake import canonical_payload_hash


PAYLOAD = {
    "workflow_id": "loan_approval",
    "data": {"applicant": {"age": 24, "monthly_income": 60000, "credit_score": 750}},
}


@pytest.fixture
def running_app(tmp_path):
    database_path = tmp_path / "phase3.sqlite3"
    application = create_app(database_url=f"sqlite:///{database_path}")
    with TestClient(application, raise_server_exceptions=False) as client:
        yield application, client


def post(client: TestClient, payload: dict = PAYLOAD, key: str = "key-1"):
    return client.post(
        "/api/v1/requests", json=payload, headers={"Idempotency-Key": key}
    )


def test_valid_request_returns_202_and_status_url(running_app):
    _app, client = running_app
    response = post(client)
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "RECEIVED"
    assert body["workflow_id"] == "loan_approval"
    assert body["config_version"] == 2
    assert body["status_url"] == f"/api/v1/requests/{body['request_id']}"


def test_request_execution_and_initial_audit_commit_atomically_and_survive_session_close(running_app):
    application, client = running_app
    response = post(client)
    request_id = response.json()["request_id"]

    # Read through a new session after the request's dependency session has closed.
    with application.state.database.session() as session:
        request = session.get(WorkflowRequest, request_id)
        execution = session.scalar(select(WorkflowExecution).where(
            WorkflowExecution.request_id == request_id
        ))
        audit = session.scalars(select(AuditEvent).where(AuditEvent.request_id == request_id)).all()
        assert request is not None
        assert request.created_at.tzinfo is not None
        assert request.created_at.utcoffset().total_seconds() == 0
        assert execution is not None and execution.status == "RECEIVED"
        assert execution.current_stage == "eligibility" and execution.revision == 0
        assert len(audit) == 1
        assert (audit[0].sequence, audit[0].event_type, audit[0].new_state) == (
            1, "REQUEST_RECEIVED", "RECEIVED"
        )
        assert session.scalar(select(func.count()).select_from(Decision)) == 0


def test_get_returns_persisted_request_state_and_null_decision(running_app):
    _app, client = running_app
    created = post(client).json()
    response = client.get(created["status_url"])
    assert response.status_code == 200
    assert response.json()["request_id"] == created["request_id"]
    assert response.json()["status"] == "RECEIVED"
    assert response.json()["config_version"] == 2
    assert response.json()["decision"] is None


def test_missing_required_schema_input_returns_422(running_app):
    _app, client = running_app
    incomplete = {"workflow_id": "loan_approval", "data": {"applicant": {"age": 24}}}
    response = post(client, incomplete)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert "monthly_income" in response.json()["error"]["message"]


def test_unknown_workflow_returns_404(running_app):
    _app, client = running_app
    response = post(client, {"workflow_id": "not_configured", "data": {"anything": 1}})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_missing_idempotency_key_returns_structured_422(running_app):
    _app, client = running_app
    response = client.post("/api/v1/requests", json=PAYLOAD)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_same_key_and_same_payload_replays_original_without_duplicate_records(running_app):
    application, client = running_app
    first = post(client, key="same").json()
    replay = post(client, key="same")
    assert replay.status_code == 200
    assert replay.headers["Idempotency-Replayed"] == "true"
    assert replay.json()["request_id"] == first["request_id"]
    with application.state.database.session() as session:
        assert session.scalar(select(func.count()).select_from(WorkflowRequest)) == 1
        assert session.scalar(select(func.count()).select_from(WorkflowExecution)) == 1
        assert session.scalar(select(func.count()).select_from(AuditEvent)) == 1


def test_same_key_and_different_payload_returns_409(running_app):
    _app, client = running_app
    post(client, key="same")
    changed = {"workflow_id": "loan_approval", "data": {
        "applicant": {"age": 25, "monthly_income": 60000, "credit_score": 750}
    }}
    response = post(client, changed, key="same")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_equivalent_json_with_reordered_keys_replays_same_request(running_app):
    _app, client = running_app
    first = post(client, key="order").json()
    reordered = {
        "data": {"applicant": {"credit_score": 750, "age": 24, "monthly_income": 60000}},
        "workflow_id": "loan_approval",
    }
    replay = post(client, reordered, key="order")
    assert replay.status_code == 200
    assert replay.json()["request_id"] == first["request_id"]


def test_canonical_hash_includes_workflow_identity_and_ignores_key_order():
    data_a = {"applicant": {"age": 24, "credit_score": 750}}
    data_b = {"applicant": {"credit_score": 750, "age": 24}}
    assert canonical_payload_hash("loan_approval", data_a) == canonical_payload_hash(
        "loan_approval", data_b
    )
    assert canonical_payload_hash("loan_approval", data_a) != canonical_payload_hash(
        "vendor_approval", data_a
    )


def test_different_keys_create_separate_requests(running_app):
    application, client = running_app
    first = post(client, key="one").json()
    second = post(client, key="two").json()
    assert first["request_id"] != second["request_id"]
    with application.state.database.session() as session:
        assert session.scalar(select(func.count()).select_from(WorkflowRequest)) == 2


def test_config_version_is_pinned_and_versions_are_discoverable(running_app):
    application, client = running_app
    versions = client.get("/api/v1/workflows/loan_approval/versions")
    assert versions.status_code == 200
    assert [(v["version"], v["is_active"]) for v in versions.json()] == [(2, True), (1, False)]
    accepted = post(client).json()
    with application.state.database.session() as session:
        request = session.get(WorkflowRequest, accepted["request_id"])
        snapshot = session.get(WorkflowConfig, ("loan_approval", request.config_version))
        assert request.config_version == 2
        assert snapshot is not None and snapshot.checksum
        assert snapshot.configuration["workflow"]["version"] == 2
    workflows = client.get("/api/v1/workflows")
    assert workflows.status_code == 200
    assert {item["workflow_id"] for item in workflows.json()} == {"loan_approval", "vendor_approval"}


def test_existing_config_snapshot_checksum_cannot_be_rewritten(running_app):
    application, _client = running_app
    changed_snapshots = [dict(snapshot) for snapshot in application.state.config_snapshots]
    loan_v1 = next(item for item in changed_snapshots
                   if item["workflow_id"] == "loan_approval" and item["version"] == 1)
    loan_v1["checksum"] = "0" * 64
    with application.state.database.session() as session:
        with pytest.raises(ValueError, match="immutable workflow snapshot changed"):
            with session.begin():
                synchronize_workflow_snapshots(session, changed_snapshots)
        session.rollback()
        persisted = session.get(WorkflowConfig, ("loan_approval", 1))
        assert persisted.checksum != "0" * 64


def test_replay_keeps_original_version_after_active_marker_changes(running_app):
    application, client = running_app
    first = post(client, key="pinned-replay").json()
    with application.state.database.session() as session:
        with session.begin():
            v2 = session.get(WorkflowConfig, ("loan_approval", 2))
            v1 = session.get(WorkflowConfig, ("loan_approval", 1))
            v2.is_active = False
            session.flush()
            v1.is_active = True

    replay = post(client, key="pinned-replay")
    assert replay.status_code == 200
    assert replay.json()["request_id"] == first["request_id"]
    assert replay.json()["config_version"] == 2


def test_sqlite_foreign_keys_are_enabled(running_app):
    application, _client = running_app
    with application.state.database.session() as session:
        assert session.connection().exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1


def test_unknown_and_invalid_uuid_status_paths(running_app):
    _app, client = running_app
    assert client.get(f"/api/v1/requests/{uuid4()}").status_code == 404
    invalid = client.get("/api/v1/requests/not-a-uuid")
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "validation_error"


def test_malformed_json_returns_422_without_stack_trace(running_app):
    _app, client = running_app
    response = client.post(
        "/api/v1/requests", content="{bad json", headers={
            "Content-Type": "application/json", "Idempotency-Key": "malformed",
        }
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert "Traceback" not in response.text


def test_database_rolls_back_all_records_on_commit_failure(running_app):
    application, client = running_app

    def fail_commit(_session):
        raise RuntimeError("injected commit failure")

    from sqlalchemy import event

    event.listen(Session, "before_commit", fail_commit)
    try:
        response = post(client, key="commit-failure")
    finally:
        event.remove(Session, "before_commit", fail_commit)
    assert response.status_code == 500
    assert response.json() == {"error": {
        "code": "internal_error", "message": "An internal error occurred"
    }}
    with application.state.database.session() as session:
        assert session.scalar(select(func.count()).select_from(WorkflowRequest)) == 0
        assert session.scalar(select(func.count()).select_from(WorkflowExecution)) == 0
        assert session.scalar(select(func.count()).select_from(AuditEvent)) == 0


def test_concurrent_duplicate_submissions_use_database_uniqueness(running_app):
    application, client = running_app

    def submit():
        response = post(client, key="concurrent")
        return response.status_code, response.json()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _index: submit(), range(2)))

    assert sorted(status for status, _body in results) == [200, 202]
    assert len({body["request_id"] for _status, body in results}) == 1
    with application.state.database.session() as session:
        assert session.scalar(select(func.count()).select_from(WorkflowRequest)) == 1
        assert session.scalar(select(func.count()).select_from(WorkflowExecution)) == 1
        assert session.scalar(select(func.count()).select_from(AuditEvent)) == 1


def test_schema_validation_rejects_wrong_field_types(running_app):
    _app, client = running_app
    invalid = {"workflow_id": "loan_approval", "data": {
        "applicant": {"age": "24", "monthly_income": 60000, "credit_score": 750}
    }}
    response = post(client, invalid, key="wrong-type")
    assert response.status_code == 422
    assert "applicant.age" in response.json()["error"]["message"]

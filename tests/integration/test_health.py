from fastapi.testclient import TestClient

from app.main import create_app


def test_health_returns_ok() -> None:
    app = create_app(database_url="sqlite:///:memory:")
    with TestClient(app) as client:
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

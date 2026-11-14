from uuid import UUID

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok_and_request_id() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert isinstance(body["request_id"], str)
    assert str(UUID(body["request_id"])) == body["request_id"]
    assert response.headers["X-Request-ID"] == body["request_id"]


def test_health_generates_a_new_request_id_for_each_request() -> None:
    first = client.get("/api/v1/health")
    second = client.get("/api/v1/health")

    assert first.json()["request_id"] != second.json()["request_id"]

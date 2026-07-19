from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "application": "Utilities Platform",
    }


def test_platform_status_endpoint() -> None:
    response = client.get("/api/platform/status")
    payload = response.json()

    assert response.status_code == 200
    assert payload["database_connected"] is False
    assert "No production utility database" in payload["message"]

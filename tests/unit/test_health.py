from fastapi.testclient import TestClient

from src.core.app import create_app


def test_health_endpoint_basic():
    client = TestClient(create_app())
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "version" in data and isinstance(data["version"], str)

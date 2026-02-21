from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from src.api.maas import router
from src.database import User, get_db


app = FastAPI()
app.include_router(router)
client = TestClient(app)


def _set_db_user(user):
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = user
    app.dependency_overrides[get_db] = lambda: mock_db


def test_deploy_mesh_success():
    api_key = "valid-key-1234567"
    _set_db_user(User(id="u1", api_key=api_key, plan="pro", role="user"))

    response = client.post(
        "/api/v1/maas/deploy",
        json={
            "name": "test-mesh",
            "nodes": 25,
            "billing_plan": "pro",
        },
        headers={"X-API-Key": api_key},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "active"
    assert data["plan"] == "pro"
    assert "mesh_id" in data


def test_deploy_mesh_quota_exceeded():
    api_key = "starter-key-12345"
    _set_db_user(User(id="u1", api_key=api_key, plan="starter", role="user"))

    response = client.post(
        "/api/v1/maas/deploy",
        json={
            "name": "big-mesh",
            "nodes": 200,
            "billing_plan": "starter",
        },
        headers={"X-API-Key": api_key},
    )

    assert response.status_code == 402
    assert "Quota exceeded" in response.json()["detail"]


def test_deploy_mesh_invalid_key():
    _set_db_user(None)

    response = client.post(
        "/api/v1/maas/deploy",
        json={
            "name": "test-mesh",
            "nodes": 5,
            "billing_plan": "pro",
        },
        headers={"X-API-Key": "invalid-key-12345"},
    )

    assert response.status_code == 401


def test_deploy_mesh_plan_escalation_blocked():
    api_key = "starter-key-12345"
    _set_db_user(User(id="u1", api_key=api_key, plan="starter", role="user"))

    response = client.post(
        "/api/v1/maas/deploy",
        json={
            "name": "enterprise-attempt",
            "nodes": 1,
            "billing_plan": "enterprise",
        },
        headers={"X-API-Key": api_key},
    )

    assert response.status_code == 402
    assert "Plan escalation blocked" in response.json()["detail"]


def test_plan_catalog_endpoint():
    response = client.get("/api/v1/maas/plans")

    assert response.status_code == 200
    plans = response.json()["plans"]
    assert "starter" in plans
    assert "pro" in plans
    assert "enterprise" in plans

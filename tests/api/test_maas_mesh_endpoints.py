"""
Integration tests for currently exposed MaaS mesh endpoints.

These tests follow the actual app routing at runtime:
  - POST /api/v1/maas/mesh/deploy          (modular deploy endpoint)
  - GET  /api/v1/maas/list                 (legacy list endpoint)
  - GET  /api/v1/maas/{mesh_id}/status
  - GET  /api/v1/maas/{mesh_id}/metrics
  - POST /api/v1/maas/{mesh_id}/scale
  - DELETE /api/v1/maas/{mesh_id}
  - GET  /api/v1/maas/{mesh_id}/audit-logs
  - GET  /api/v1/maas/{mesh_id}/mapek/events
"""

from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import src.api.maas_legacy as legacy
from src.core.app import app
from src.database import Base, MeshInstance as DBMeshInstance, User, get_db


_TEST_DB_PATH = f"./test_mesh_endpoints_{uuid.uuid4().hex}.db"
_engine = create_engine(
    f"sqlite:///{_TEST_DB_PATH}", connect_args={"check_same_thread": False}
)
_TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def _override_get_db():
    db = _TestingSession()
    try:
        yield db
    finally:
        db.close()


def _register_user(client: TestClient, prefix: str) -> dict[str, str]:
    email = f"{prefix}-{uuid.uuid4().hex[:8]}@test.com"
    response = client.post(
        "/api/v1/maas/auth/register",
        json={"email": email, "password": "secret123", "name": prefix},
    )
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]

    db = _TestingSession()
    try:
        user = db.query(User).filter(User.api_key == token).first()
        assert user is not None
        return {"email": email, "token": token, "user_id": user.id}
    finally:
        db.close()


@pytest.fixture(scope="module")
def client():
    Base.metadata.create_all(bind=_engine)
    app.dependency_overrides[get_db] = _override_get_db

    # Clean in-memory registries for deterministic endpoint tests.
    legacy._mesh_registry.clear()
    legacy._pending_nodes.clear()
    legacy._node_telemetry.clear()
    legacy._mesh_audit_log.clear()
    legacy._mesh_mapek_events.clear()

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.pop(get_db, None)
    legacy._mesh_registry.clear()
    legacy._pending_nodes.clear()
    legacy._node_telemetry.clear()
    legacy._mesh_audit_log.clear()
    legacy._mesh_mapek_events.clear()
    Base.metadata.drop_all(bind=_engine)
    if os.path.exists(_TEST_DB_PATH):
        os.remove(_TEST_DB_PATH)


@pytest.fixture(scope="module")
def users(client):
    return {
        "a": _register_user(client, "mesh-user-a"),
        "b": _register_user(client, "mesh-user-b"),
    }


@pytest.fixture(scope="module")
def deployed_mesh(client, users):
    response = client.post(
        "/api/v1/maas/mesh/deploy",
        json={"name": "Mesh Alpha", "nodes": 3, "billing_plan": "starter"},
        headers={"X-API-Key": users["a"]["token"]},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert "mesh_id" in body
    return body


def test_mesh_deploy_persists_in_db(client, users):
    response = client.post(
        "/api/v1/maas/mesh/deploy",
        json={"name": "DB Persist", "nodes": 2, "billing_plan": "starter"},
        headers={"X-API-Key": users["a"]["token"]},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    mesh_id = body["mesh_id"]

    join_config = body.get("join_config", {})
    assert "token" in join_config or "enrollment_token" in join_config
    assert body["status"] == "active"

    db = _TestingSession()
    try:
        row = db.query(DBMeshInstance).filter(DBMeshInstance.id == mesh_id).first()
        assert row is not None
        assert row.owner_id == users["a"]["user_id"]
        assert row.name == "DB Persist"
        assert row.nodes == 2
    finally:
        db.close()


def test_mesh_list_returns_owner_meshes_only(client, users, deployed_mesh):
    mine = client.get("/api/v1/maas/list", headers={"X-API-Key": users["a"]["token"]})
    assert mine.status_code == 200, mine.text
    mine_body = mine.json()
    assert "meshes" in mine_body
    my_ids = [item["mesh_id"] for item in mine_body["meshes"]]
    assert deployed_mesh["mesh_id"] in my_ids

    other = client.get("/api/v1/maas/list", headers={"X-API-Key": users["b"]["token"]})
    assert other.status_code == 200, other.text
    other_ids = [item["mesh_id"] for item in other.json().get("meshes", [])]
    assert deployed_mesh["mesh_id"] not in other_ids


def test_mesh_status_and_metrics(client, users, deployed_mesh):
    mesh_id = deployed_mesh["mesh_id"]

    status_response = client.get(
        f"/api/v1/maas/{mesh_id}/status",
        headers={"X-API-Key": users["a"]["token"]},
    )
    assert status_response.status_code == 200, status_response.text
    status_body = status_response.json()
    assert status_body["mesh_id"] == mesh_id
    assert "nodes_total" in status_body
    assert "nodes_healthy" in status_body

    metrics_response = client.get(
        f"/api/v1/maas/{mesh_id}/metrics",
        headers={"X-API-Key": users["a"]["token"]},
    )
    assert metrics_response.status_code == 200, metrics_response.text
    metrics_body = metrics_response.json()
    assert metrics_body["mesh_id"] == mesh_id
    assert "consciousness" in metrics_body
    assert "mape_k" in metrics_body
    assert "network" in metrics_body


def test_mesh_scale_audit_and_mapek(client, users, deployed_mesh):
    mesh_id = deployed_mesh["mesh_id"]

    scale_response = client.post(
        f"/api/v1/maas/{mesh_id}/scale",
        json={"action": "scale_up", "count": 1},
        headers={"X-API-Key": users["a"]["token"]},
    )
    assert scale_response.status_code == 200, scale_response.text
    scale_body = scale_response.json()
    assert scale_body["mesh_id"] == mesh_id
    assert scale_body["current_nodes"] >= scale_body["previous_nodes"]

    audit_response = client.get(
        f"/api/v1/maas/{mesh_id}/audit-logs",
        headers={"X-API-Key": users["a"]["token"]},
    )
    assert audit_response.status_code == 403, audit_response.text

    mapek_response = client.get(
        f"/api/v1/maas/{mesh_id}/mapek/events?limit=10",
        headers={"X-API-Key": users["a"]["token"]},
    )
    assert mapek_response.status_code == 200, mapek_response.text
    mapek_body = mapek_response.json()
    assert mapek_body["mesh_id"] == mesh_id
    assert "events" in mapek_body


def test_mesh_access_control_and_auth_guard(client, users, deployed_mesh):
    mesh_id = deployed_mesh["mesh_id"]

    unauth = client.get("/api/v1/maas/list")
    assert unauth.status_code == 401

    foreign_status = client.get(
        f"/api/v1/maas/{mesh_id}/status",
        headers={"X-API-Key": users["b"]["token"]},
    )
    assert foreign_status.status_code in (403, 404)

    foreign_scale = client.post(
        f"/api/v1/maas/{mesh_id}/scale",
        json={"action": "scale_up", "count": 1},
        headers={"X-API-Key": users["b"]["token"]},
    )
    assert foreign_scale.status_code in (403, 404)


def test_mesh_terminate_lifecycle(client, users):
    deploy_response = client.post(
        "/api/v1/maas/mesh/deploy",
        json={"name": "Terminate Me", "nodes": 1, "billing_plan": "starter"},
        headers={"X-API-Key": users["a"]["token"]},
    )
    assert deploy_response.status_code == 200, deploy_response.text
    mesh_id = deploy_response.json()["mesh_id"]

    terminate_response = client.delete(
        f"/api/v1/maas/{mesh_id}",
        headers={"X-API-Key": users["a"]["token"]},
    )
    assert terminate_response.status_code == 200, terminate_response.text
    term_body = terminate_response.json()
    assert term_body["mesh_id"] == mesh_id
    assert term_body["status"] == "terminated"

    status_response = client.get(
        f"/api/v1/maas/{mesh_id}/status",
        headers={"X-API-Key": users["a"]["token"]},
    )
    assert status_response.status_code == 404

"""RBAC boundary tests for critical MaaS endpoints."""

import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.app import app
from src.database import Base, User, get_db

_TEST_DB_PATH = f"./test_maas_rbac_{uuid.uuid4().hex}.db"
_DB_URL = f"sqlite:///{_TEST_DB_PATH}"
engine = create_engine(_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def _register_user_with_role(client: TestClient, role: str) -> str:
    email = f"{role}-{uuid.uuid4().hex[:10]}@test.com"
    response = client.post(
        "/api/v1/maas/auth/register",
        json={"email": email, "password": "password123"},
    )
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]

    db = TestingSessionLocal()
    user = db.query(User).filter(User.api_key == token).first()
    user.role = role
    db.commit()
    db.close()
    return token


@pytest.fixture(scope="module")
def client():
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=engine)
    if os.path.exists(_TEST_DB_PATH):
        os.remove(_TEST_DB_PATH)


@pytest.fixture(scope="module")
def role_tokens(client):
    return {
        "admin": _register_user_with_role(client, "admin"),
        "operator": _register_user_with_role(client, "operator"),
        "user": _register_user_with_role(client, "user"),
    }


class TestCriticalEndpointRbac:
    def test_supply_chain_register_artifact_admin_only(self, client, role_tokens):
        assert (
            client.post(
                "/api/v1/maas/supply-chain/register-artifact",
                json={
                    "version": f"v-rbac-{uuid.uuid4().hex[:8]}",
                    "format": "CycloneDX-JSON",
                    "checksum_sha256": "sha256:abcdef1234567890",
                    "components": [{"name": "x0tta-agent", "version": "3.4.0", "type": "application"}],
                },
            ).status_code
            == 401
        )

        admin_response = client.post(
            "/api/v1/maas/supply-chain/register-artifact",
            headers={"X-API-Key": role_tokens["admin"]},
            json={
                "version": f"v-rbac-admin-{uuid.uuid4().hex[:8]}",
                "format": "CycloneDX-JSON",
                "checksum_sha256": "sha256:abcdef1234567890",
                "components": [{"name": "x0tta-agent", "version": "3.4.0", "type": "application"}],
            },
        )
        assert admin_response.status_code == 200, admin_response.text

        operator_response = client.post(
            "/api/v1/maas/supply-chain/register-artifact",
            headers={"X-API-Key": role_tokens["operator"]},
            json={
                "version": f"v-rbac-op-{uuid.uuid4().hex[:8]}",
                "format": "CycloneDX-JSON",
                "checksum_sha256": "sha256:abcdef1234567890",
                "components": [{"name": "x0tta-agent", "version": "3.4.0", "type": "application"}],
            },
        )
        assert operator_response.status_code == 403

        user_response = client.post(
            "/api/v1/maas/supply-chain/register-artifact",
            headers={"X-API-Key": role_tokens["user"]},
            json={
                "version": f"v-rbac-user-{uuid.uuid4().hex[:8]}",
                "format": "CycloneDX-JSON",
                "checksum_sha256": "sha256:abcdef1234567890",
                "components": [{"name": "x0tta-agent", "version": "3.4.0", "type": "application"}],
            },
        )
        assert user_response.status_code == 403

    def test_playbook_create_operator_or_admin_allowed(self, client, role_tokens):
        request_body = {
            "name": "RBAC regression playbook",
            "target_nodes": ["node-a"],
            "actions": [{"action": "restart", "params": {}}],
            "expires_in_sec": 3600,
        }
        mesh_id = f"mesh-rbac-{uuid.uuid4().hex[:8]}"

        assert (
            client.post(
                f"/api/v1/maas/playbooks/create?mesh_id={mesh_id}",
                json=request_body,
            ).status_code
            == 401
        )

        operator_response = client.post(
            f"/api/v1/maas/playbooks/create?mesh_id={mesh_id}",
            headers={"X-API-Key": role_tokens["operator"]},
            json=request_body,
        )
        assert operator_response.status_code == 200, operator_response.text

        admin_response = client.post(
            f"/api/v1/maas/playbooks/create?mesh_id={mesh_id}",
            headers={"X-API-Key": role_tokens["admin"]},
            json=request_body,
        )
        assert admin_response.status_code == 200, admin_response.text

        user_response = client.post(
            f"/api/v1/maas/playbooks/create?mesh_id={mesh_id}",
            headers={"X-API-Key": role_tokens["user"]},
            json=request_body,
        )
        assert user_response.status_code == 403

    def test_analytics_summary_denies_user_without_scope(self, client, role_tokens):
        mesh_id = f"mesh-analytics-{uuid.uuid4().hex[:8]}"

        assert client.get(f"/api/v1/maas/analytics/{mesh_id}/summary").status_code == 401
        assert (
            client.get(
                f"/api/v1/maas/analytics/{mesh_id}/summary",
                headers={"X-API-Key": role_tokens["user"]},
            ).status_code
            == 403
        )

        # 404 means authz passed and service returned "mesh not found".
        assert (
            client.get(
                f"/api/v1/maas/analytics/{mesh_id}/summary",
                headers={"X-API-Key": role_tokens["operator"]},
            ).status_code
            == 404
        )
        assert (
            client.get(
                f"/api/v1/maas/analytics/{mesh_id}/summary",
                headers={"X-API-Key": role_tokens["admin"]},
            ).status_code
            == 404
        )

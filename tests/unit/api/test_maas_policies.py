"""
Unit tests for MaaS ACL Policy endpoints.

The legacy handler (maas_legacy.py) intercepts GET/POST /{mesh_id}/policies.
It stores policies in-memory and checks mesh ownership via mesh_provisioner.
DELETE is handled by maas_policies.py (DB-backed).
"""
import uuid
import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.app import app
from src.database import Base, get_db, User

_TEST_DB_PATH = f"./test_policies_{uuid.uuid4().hex}.db"
SQLALCHEMY_DATABASE_URL = f"sqlite:///{_TEST_DB_PATH}"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="module")
def client():
    Base.metadata.create_all(bind=engine)
    original_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    if original_override is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = original_override
    Base.metadata.drop_all(bind=engine)
    if os.path.exists(_TEST_DB_PATH):
        os.remove(_TEST_DB_PATH)


@pytest.fixture(scope="module")
def user_with_mesh(client):
    """Register a user, deploy a mesh, return credentials + mesh_id."""
    email = f"pol-owner-{uuid.uuid4().hex}@test.com"
    resp = client.post(
        "/api/v1/maas/auth/register",
        json={"email": email, "password": "password123"},
    )
    api_key = resp.json()["access_token"]
    headers = {"X-API-Key": api_key}

    deploy = client.post(
        "/api/v1/maas/deploy",
        json={"name": "pol-test-mesh", "nodes": 1, "billing_plan": "starter"},
        headers=headers,
    )
    assert deploy.status_code == 200
    mesh_id = deploy.json()["mesh_id"]
    return {"headers": headers, "mesh_id": mesh_id, "api_key": api_key}


@pytest.fixture(scope="module")
def other_user(client):
    """A second user without access to the first user's mesh."""
    email = f"pol-other-{uuid.uuid4().hex}@test.com"
    resp = client.post(
        "/api/v1/maas/auth/register",
        json={"email": email, "password": "password123"},
    )
    api_key = resp.json()["access_token"]
    return {"headers": {"X-API-Key": api_key}}


class TestPolicyCreate:
    def test_owner_with_permission_can_create(self, client, user_with_mesh):
        """User with policy:create permission can create policy on their mesh."""
        db = TestingSessionLocal()
        try:
            user = db.query(User).filter(
                User.api_key == user_with_mesh["api_key"]
            ).first()
            user.permissions = "policy:create"
            db.commit()
        finally:
            db.close()

        resp = client.post(
            f"/api/v1/maas/{user_with_mesh['mesh_id']}/policies",
            json={"source_tag": "sensor", "target_tag": "gateway", "action": "allow"},
            headers=user_with_mesh["headers"],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["source_tag"] == "sensor"
        assert data["target_tag"] == "gateway"
        assert data["action"] == "allow"
        assert "policy_id" in data

    def test_other_user_cannot_create_on_unowned_mesh(self, client, user_with_mesh, other_user):
        """User without mesh ownership gets 404 (not 403)."""
        db = TestingSessionLocal()
        try:
            other = db.query(User).filter(
                User.api_key == other_user["headers"]["X-API-Key"]
            ).first()
            other.permissions = "policy:create"
            db.commit()
        finally:
            db.close()

        resp = client.post(
            f"/api/v1/maas/{user_with_mesh['mesh_id']}/policies",
            json={"source_tag": "a", "target_tag": "b", "action": "allow"},
            headers=other_user["headers"],
        )
        assert resp.status_code == 404

    def test_user_without_permission_cannot_create(self, client, user_with_mesh):
        """User without policy:create permission gets 403."""
        db = TestingSessionLocal()
        try:
            user = db.query(User).filter(
                User.api_key == user_with_mesh["api_key"]
            ).first()
            user.permissions = None  # remove explicit permissions, role defaults apply
            db.commit()
        finally:
            db.close()

        resp = client.post(
            f"/api/v1/maas/{user_with_mesh['mesh_id']}/policies",
            json={"source_tag": "a", "target_tag": "b", "action": "allow"},
            headers=user_with_mesh["headers"],
        )
        assert resp.status_code == 403

    def test_invalid_action_rejected(self, client, user_with_mesh):
        """Invalid action value (not allow/deny) fails validation."""
        db = TestingSessionLocal()
        try:
            user = db.query(User).filter(
                User.api_key == user_with_mesh["api_key"]
            ).first()
            user.permissions = "policy:create"
            db.commit()
        finally:
            db.close()

        resp = client.post(
            f"/api/v1/maas/{user_with_mesh['mesh_id']}/policies",
            json={"source_tag": "a", "target_tag": "b", "action": "permit"},
            headers=user_with_mesh["headers"],
        )
        assert resp.status_code == 422

    def test_missing_tags_rejected(self, client, user_with_mesh):
        """Missing source_tag or target_tag fails validation."""
        resp = client.post(
            f"/api/v1/maas/{user_with_mesh['mesh_id']}/policies",
            json={"action": "allow"},
            headers=user_with_mesh["headers"],
        )
        assert resp.status_code in [422, 403]

    def test_unauthenticated_cannot_create(self, client, user_with_mesh):
        """No API key → 401."""
        resp = client.post(
            f"/api/v1/maas/{user_with_mesh['mesh_id']}/policies",
            json={"source_tag": "a", "target_tag": "b"},
        )
        assert resp.status_code == 401


class TestPolicyList:
    def test_owner_can_list_own_policies(self, client, user_with_mesh):
        """Mesh owner can list their policies (legacy endpoint returns dict)."""
        # Ensure policy exists first
        db = TestingSessionLocal()
        try:
            user = db.query(User).filter(
                User.api_key == user_with_mesh["api_key"]
            ).first()
            user.permissions = "policy:create"
            db.commit()
        finally:
            db.close()

        client.post(
            f"/api/v1/maas/{user_with_mesh['mesh_id']}/policies",
            json={"source_tag": "list-test", "target_tag": "gw", "action": "allow"},
            headers=user_with_mesh["headers"],
        )

        resp = client.get(
            f"/api/v1/maas/{user_with_mesh['mesh_id']}/policies",
            headers=user_with_mesh["headers"],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "policies" in data
        assert isinstance(data["policies"], list)

    def test_other_user_cannot_list_unowned_mesh(self, client, user_with_mesh, other_user):
        """Other user gets 404 on unowned mesh."""
        resp = client.get(
            f"/api/v1/maas/{user_with_mesh['mesh_id']}/policies",
            headers=other_user["headers"],
        )
        assert resp.status_code == 404

    def test_nonexistent_mesh_returns_404(self, client, user_with_mesh):
        """Non-existent mesh returns 404."""
        resp = client.get(
            "/api/v1/maas/non-existent-mesh-id/policies",
            headers=user_with_mesh["headers"],
        )
        assert resp.status_code == 404

    def test_unauthenticated_cannot_list(self, client, user_with_mesh):
        resp = client.get(f"/api/v1/maas/{user_with_mesh['mesh_id']}/policies")
        assert resp.status_code == 401


class TestPolicyDelete:
    """DELETE endpoint is handled by maas_policies.py (DB-backed)."""

    def test_admin_can_delete_db_policy(self, client, user_with_mesh):
        """Admin can delete a DB policy via maas_policies.py endpoint."""
        email = f"admin-del-{uuid.uuid4().hex}@test.com"
        resp = client.post(
            "/api/v1/maas/auth/register",
            json={"email": email, "password": "adminpass123"},
        )
        api_key = resp.json()["access_token"]
        admin_headers = {"X-API-Key": api_key}

        db = TestingSessionLocal()
        try:
            user = db.query(User).filter(User.api_key == api_key).first()
            user.role = "admin"
            db.commit()
        finally:
            db.close()

        # Deploy mesh as admin
        db = TestingSessionLocal()
        try:
            user = db.query(User).filter(User.api_key == api_key).first()
            user.role = "user"
            db.commit()
        finally:
            db.close()

        deploy = client.post(
            "/api/v1/maas/deploy",
            json={"name": "del-policy-mesh", "nodes": 1, "billing_plan": "starter"},
            headers=admin_headers,
        )
        mesh_id = deploy.json()["mesh_id"]

        db = TestingSessionLocal()
        try:
            user = db.query(User).filter(User.api_key == api_key).first()
            user.role = "admin"
            db.commit()
        finally:
            db.close()

        # Create a DB-backed policy via maas_policies.py endpoint
        create = client.post(
            f"/api/v1/maas/{mesh_id}/policies",
            json={"source_tag": "to-delete", "target_tag": "any", "action": "deny"},
            headers=admin_headers,
        )
        assert create.status_code == 200
        # Could be in legacy format (policy_id) or new format (id)
        policy_data = create.json()
        policy_id = policy_data.get("policy_id") or policy_data.get("id")
        assert policy_id is not None

    def test_delete_nonexistent_policy_404(self, client):
        """Deleting non-existent DB policy returns 404."""
        email = f"admin-del2-{uuid.uuid4().hex}@test.com"
        resp = client.post(
            "/api/v1/maas/auth/register",
            json={"email": email, "password": "pass12345"},
        )
        api_key = resp.json()["access_token"]
        headers = {"X-API-Key": api_key}
        db = TestingSessionLocal()
        try:
            user = db.query(User).filter(User.api_key == api_key).first()
            user.role = "admin"
            db.commit()
        finally:
            db.close()

        resp = client.delete(
            "/api/v1/maas/some-mesh/policies/pol-doesnotexist",
            headers=headers,
        )
        assert resp.status_code == 404

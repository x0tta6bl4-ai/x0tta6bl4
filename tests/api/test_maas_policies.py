"""
Integration tests for MaaS ACL Policies.

Endpoints and routing:
  GET    /api/v1/maas/{mesh_id}/policies               — legacy router (mesh_provisioner + _mesh_policies)
  POST   /api/v1/maas/{mesh_id}/policies               — legacy router (mesh_provisioner + _mesh_policies)
  DELETE /api/v1/maas/{mesh_id}/policies/{policy_id}   — maas_policies.py (SQLAlchemy ACLPolicy)

Architecture notes:
  Legacy GET:  requires get_current_user (any auth) + mesh ownership check → {"policies": [...]}
  Legacy POST: requires policy:create permission + mesh ownership check → PolicyResponse dict
               operator has policy:create but CANNOT deploy a mesh (no mesh:create permission)
               → only admin (owner) can successfully create policies via legacy
  maas_policies DELETE: requires admin role, uses SQLAlchemy DB directly, no ownership check

RBAC summary:
  user     — no policy:create → 403 on POST; not owner → 404 on GET; no admin → 403 on DELETE
  operator — has policy:create but not mesh owner → 404 on GET/POST; no admin → 403 on DELETE
  admin    — bypasses all RBAC; is mesh owner (deployed it) → 200 on all
"""

import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.app import app
from src.database import ACLPolicy, Base, User, get_db

_TEST_DB_PATH = f"./test_policies_{uuid.uuid4().hex}.db"
engine = create_engine(
    f"sqlite:///{_TEST_DB_PATH}", connect_args={"check_same_thread": False}
)
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
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=engine)
    if os.path.exists(_TEST_DB_PATH):
        os.remove(_TEST_DB_PATH)


@pytest.fixture(scope="module")
def policy_data(client):
    """
    Set up:
      - admin  (role=admin): deploys mesh → owner_id = admin.id
      - operator (role=operator): has policy:create but NOT mesh owner
      - regular user (role=user): no policy permissions

    Why admin deploys:
      operator lacks mesh:create; user cannot create policies; only admin can own
      AND create policies in the same mesh.
    """
    email_admin = f"pol-adm-{uuid.uuid4().hex[:8]}@test.com"
    email_op = f"pol-op-{uuid.uuid4().hex[:8]}@test.com"
    email_usr = f"pol-usr-{uuid.uuid4().hex[:8]}@test.com"

    r = client.post("/api/v1/maas/auth/register",
                    json={"email": email_admin, "password": "password123"})
    admin_token = r.json()["access_token"]

    r = client.post("/api/v1/maas/auth/register",
                    json={"email": email_op, "password": "password123"})
    op_token = r.json()["access_token"]

    r = client.post("/api/v1/maas/auth/register",
                    json={"email": email_usr, "password": "password123"})
    usr_token = r.json()["access_token"]

    # Elevate admin and operator in DB
    db = TestingSessionLocal()
    admin = db.query(User).filter(User.api_key == admin_token).first()
    admin.role = "admin"
    op = db.query(User).filter(User.api_key == op_token).first()
    op.role = "operator"
    db.commit()
    db.close()

    # Admin deploys mesh → admin.id becomes owner_id in mesh_provisioner
    r = client.post(
        "/api/v1/maas/deploy",
        json={"name": "Policy Test Mesh", "nodes": 1},
        headers={"X-API-Key": admin_token},
    )
    assert r.status_code == 200, f"Deploy failed: {r.text}"
    mesh_id = r.json()["mesh_id"]

    return {
        "admin_token": admin_token,
        "op_token": op_token,
        "usr_token": usr_token,
        "mesh_id": mesh_id,
    }


def _db_policy(mesh_id: str, source: str = "web", target: str = "db",
               action: str = "allow") -> str:
    """Create an ACLPolicy directly in SQLAlchemy DB; return its id."""
    db = TestingSessionLocal()
    policy_id = f"pol-{uuid.uuid4().hex[:8]}"
    db.add(ACLPolicy(
        id=policy_id,
        mesh_id=mesh_id,
        source_tag=source,
        target_tag=target,
        action=action,
    ))
    db.commit()
    db.close()
    return policy_id


# ---------------------------------------------------------------------------
# GET /{mesh_id}/policies  (legacy router — returns {"policies": [...]})
# ---------------------------------------------------------------------------

class TestListPolicies:
    def test_no_auth_401(self, client, policy_data):
        r = client.get(f"/api/v1/maas/{policy_data['mesh_id']}/policies")
        assert r.status_code == 401

    def test_owner_empty_list(self, client, policy_data):
        """Admin (owner) on a fresh mesh gets empty list."""
        r = client.get(
            f"/api/v1/maas/{policy_data['mesh_id']}/policies",
            headers={"X-API-Key": policy_data["admin_token"]},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "policies" in data
        assert isinstance(data["policies"], list)

    def test_operator_nonowner_gets_404(self, client, policy_data):
        """Operator doesn't own the mesh → legacy returns 404."""
        r = client.get(
            f"/api/v1/maas/{policy_data['mesh_id']}/policies",
            headers={"X-API-Key": policy_data["op_token"]},
        )
        assert r.status_code == 404

    def test_user_nonowner_gets_404(self, client, policy_data):
        """Regular user doesn't own the mesh → legacy returns 404."""
        r = client.get(
            f"/api/v1/maas/{policy_data['mesh_id']}/policies",
            headers={"X-API-Key": policy_data["usr_token"]},
        )
        assert r.status_code == 404

    def test_unknown_mesh_404(self, client, policy_data):
        r = client.get(
            "/api/v1/maas/mesh-does-not-exist-xyz/policies",
            headers={"X-API-Key": policy_data["admin_token"]},
        )
        assert r.status_code == 404

    def test_owner_sees_created_policy(self, client, policy_data):
        """After creating a policy via POST, GET shows it."""
        r = client.post(
            f"/api/v1/maas/{policy_data['mesh_id']}/policies",
            json={"source_tag": "frontend", "target_tag": "backend", "action": "allow"},
            headers={"X-API-Key": policy_data["admin_token"]},
        )
        assert r.status_code == 200, r.text

        r = client.get(
            f"/api/v1/maas/{policy_data['mesh_id']}/policies",
            headers={"X-API-Key": policy_data["admin_token"]},
        )
        assert r.status_code == 200, r.text
        policies = r.json()["policies"]
        tags = [(p.get("source_tag") or p.get("source_tag"), p.get("target_tag")) for p in policies]
        assert any(s == "frontend" and t == "backend" for s, t in tags)

    def test_owner_sees_multiple_policies(self, client, policy_data):
        """Two more policies → all appear in list."""
        for src, tgt in [("svc-a", "svc-b"), ("svc-c", "svc-d")]:
            client.post(
                f"/api/v1/maas/{policy_data['mesh_id']}/policies",
                json={"source_tag": src, "target_tag": tgt, "action": "deny"},
                headers={"X-API-Key": policy_data["admin_token"]},
            )
        r = client.get(
            f"/api/v1/maas/{policy_data['mesh_id']}/policies",
            headers={"X-API-Key": policy_data["admin_token"]},
        )
        assert r.status_code == 200, r.text
        assert len(r.json()["policies"]) >= 3


# ---------------------------------------------------------------------------
# POST /{mesh_id}/policies  (legacy router — requires policy:create + ownership)
# ---------------------------------------------------------------------------

class TestCreatePolicy:
    def test_no_auth_401(self, client, policy_data):
        r = client.post(
            f"/api/v1/maas/{policy_data['mesh_id']}/policies",
            json={"source_tag": "web", "target_tag": "db", "action": "allow"},
        )
        assert r.status_code == 401

    def test_user_no_permission_403(self, client, policy_data):
        """User role lacks policy:create → 403 before ownership check."""
        r = client.post(
            f"/api/v1/maas/{policy_data['mesh_id']}/policies",
            json={"source_tag": "web", "target_tag": "db", "action": "allow"},
            headers={"X-API-Key": policy_data["usr_token"]},
        )
        assert r.status_code == 403

    def test_operator_nonowner_404(self, client, policy_data):
        """Operator has policy:create but is NOT the mesh owner → 404."""
        r = client.post(
            f"/api/v1/maas/{policy_data['mesh_id']}/policies",
            json={"source_tag": "web", "target_tag": "db", "action": "allow"},
            headers={"X-API-Key": policy_data["op_token"]},
        )
        assert r.status_code == 404

    def test_admin_owner_success(self, client, policy_data):
        """Admin (owner + RBAC bypass) creates policy successfully."""
        r = client.post(
            f"/api/v1/maas/{policy_data['mesh_id']}/policies",
            json={"source_tag": "api", "target_tag": "cache", "action": "allow"},
            headers={"X-API-Key": policy_data["admin_token"]},
        )
        assert r.status_code == 200, r.text

    def test_create_response_fields(self, client, policy_data):
        r = client.post(
            f"/api/v1/maas/{policy_data['mesh_id']}/policies",
            json={"source_tag": "proxy", "target_tag": "storage", "action": "allow"},
            headers={"X-API-Key": policy_data["admin_token"]},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "source_tag" in data
        assert "target_tag" in data
        assert "action" in data
        assert "created_at" in data
        # Legacy uses policy_id key (not id)
        assert "policy_id" in data or "id" in data

    def test_create_deny_action(self, client, policy_data):
        r = client.post(
            f"/api/v1/maas/{policy_data['mesh_id']}/policies",
            json={"source_tag": "untrusted", "target_tag": "internal", "action": "deny"},
            headers={"X-API-Key": policy_data["admin_token"]},
        )
        assert r.status_code == 200, r.text
        assert r.json()["action"] == "deny"

    def test_create_default_action_is_allow(self, client, policy_data):
        """action field defaults to 'allow' when omitted."""
        r = client.post(
            f"/api/v1/maas/{policy_data['mesh_id']}/policies",
            json={"source_tag": "worker", "target_tag": "queue"},
            headers={"X-API-Key": policy_data["admin_token"]},
        )
        assert r.status_code == 200, r.text
        assert r.json()["action"] == "allow"

    def test_create_unknown_mesh_404(self, client, policy_data):
        r = client.post(
            "/api/v1/maas/mesh-nonexistent-abc/policies",
            json={"source_tag": "a", "target_tag": "b", "action": "allow"},
            headers={"X-API-Key": policy_data["admin_token"]},
        )
        assert r.status_code == 404

    def test_create_invalid_action_422(self, client, policy_data):
        r = client.post(
            f"/api/v1/maas/{policy_data['mesh_id']}/policies",
            json={"source_tag": "a", "target_tag": "b", "action": "maybe"},
            headers={"X-API-Key": policy_data["admin_token"]},
        )
        assert r.status_code == 422

    def test_create_missing_required_field_422(self, client, policy_data):
        """Omitting required source_tag → 422 validation error."""
        r = client.post(
            f"/api/v1/maas/{policy_data['mesh_id']}/policies",
            json={"target_tag": "db", "action": "allow"},  # source_tag missing
            headers={"X-API-Key": policy_data["admin_token"]},
        )
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /{mesh_id}/policies/{policy_id}  (maas_policies.py — SQLAlchemy)
# ---------------------------------------------------------------------------

class TestDeletePolicy:
    def test_no_auth_401(self, client, policy_data):
        r = client.delete(
            f"/api/v1/maas/{policy_data['mesh_id']}/policies/pol-fake001"
        )
        assert r.status_code == 401

    def test_operator_forbidden_403(self, client, policy_data):
        """Operator role cannot delete policies — requires admin."""
        policy_id = _db_policy(policy_data["mesh_id"])
        r = client.delete(
            f"/api/v1/maas/{policy_data['mesh_id']}/policies/{policy_id}",
            headers={"X-API-Key": policy_data["op_token"]},
        )
        assert r.status_code == 403

    def test_user_forbidden_403(self, client, policy_data):
        policy_id = _db_policy(policy_data["mesh_id"])
        r = client.delete(
            f"/api/v1/maas/{policy_data['mesh_id']}/policies/{policy_id}",
            headers={"X-API-Key": policy_data["usr_token"]},
        )
        assert r.status_code == 403

    def test_admin_delete_success(self, client, policy_data):
        policy_id = _db_policy(policy_data["mesh_id"])
        r = client.delete(
            f"/api/v1/maas/{policy_data['mesh_id']}/policies/{policy_id}",
            headers={"X-API-Key": policy_data["admin_token"]},
        )
        assert r.status_code == 200, r.text

    def test_delete_response_format(self, client, policy_data):
        policy_id = _db_policy(policy_data["mesh_id"])
        r = client.delete(
            f"/api/v1/maas/{policy_data['mesh_id']}/policies/{policy_id}",
            headers={"X-API-Key": policy_data["admin_token"]},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "deleted"
        assert data["policy_id"] == policy_id

    def test_delete_not_found_404(self, client, policy_data):
        r = client.delete(
            f"/api/v1/maas/{policy_data['mesh_id']}/policies/pol-nonexistent",
            headers={"X-API-Key": policy_data["admin_token"]},
        )
        assert r.status_code == 404

    def test_delete_wrong_mesh_id_404(self, client, policy_data):
        """Policy exists in DB but mesh_id doesn't match → 404."""
        policy_id = _db_policy(policy_data["mesh_id"])
        r = client.delete(
            f"/api/v1/maas/wrong-mesh-id/policies/{policy_id}",
            headers={"X-API-Key": policy_data["admin_token"]},
        )
        assert r.status_code == 404

    def test_delete_idempotent_second_delete_404(self, client, policy_data):
        """Deleting an already-deleted policy returns 404."""
        policy_id = _db_policy(policy_data["mesh_id"])
        client.delete(
            f"/api/v1/maas/{policy_data['mesh_id']}/policies/{policy_id}",
            headers={"X-API-Key": policy_data["admin_token"]},
        )
        r = client.delete(
            f"/api/v1/maas/{policy_data['mesh_id']}/policies/{policy_id}",
            headers={"X-API-Key": policy_data["admin_token"]},
        )
        assert r.status_code == 404

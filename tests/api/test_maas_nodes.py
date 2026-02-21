"""
Integration tests for MaaS Node Management.

Architecture note:
- maas_legacy router is registered FIRST and shadows most node endpoints.
  Legacy uses mesh_provisioner (in-memory) for mesh lookup, not SQLAlchemy DB.
  Tests for: register, pending, approve, revoke, nodes/all → go through legacy
  and require creating meshes via POST /deploy.

- maas_nodes.py endpoints that are NOT shadowed by legacy:
    POST /{mesh_id}/nodes/{node_id}/heartbeat  — uses SQLAlchemy MeshNode
    POST /{mesh_id}/nodes/check-access          — uses SQLAlchemy MeshNode + ACLPolicy

Tests are split accordingly: legacy-flow tests use the full API, heartbeat and
check-access tests create nodes directly in DB.
"""

import os
import uuid
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.app import app
from src.database import (
    ACLPolicy, Base, MarketplaceEscrow, MarketplaceListing,
    MeshNode, User, get_db,
)

_TEST_DB_PATH = f"./test_nodes_{uuid.uuid4().hex}.db"
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
def node_data(client):
    """
    Set up:
    - admin user (owns the mesh; admin bypasses all RBAC checks)
    - regular user (for RBAC 403 checks — lacks node:revoke / require_role("operator"))
    - mesh deployed via API as admin → goes into mesh_provisioner (in-memory)

    Why admin instead of operator:
      operator role lacks 'mesh:create', so deploy returns 403.
      admin bypasses all require_role/require_permission checks AND owns the mesh.
    """
    email_admin = f"nd-adm-{uuid.uuid4().hex[:8]}@test.com"
    email_usr = f"nd-usr-{uuid.uuid4().hex[:8]}@test.com"

    r = client.post("/api/v1/maas/auth/register",
                    json={"email": email_admin, "password": "password123"})
    admin_token = r.json()["access_token"]

    r = client.post("/api/v1/maas/auth/register",
                    json={"email": email_usr, "password": "password123"})
    usr_token = r.json()["access_token"]

    # Elevate admin directly in DB
    db = TestingSessionLocal()
    admin = db.query(User).filter(User.api_key == admin_token).first()
    admin.role = "admin"
    db.commit()
    db.close()

    # Deploy mesh as admin — adds to mesh_provisioner (in-memory)
    r = client.post(
        "/api/v1/maas/deploy",
        json={"name": "Node Test Mesh", "nodes": 1},
        headers={"X-API-Key": admin_token},
    )
    assert r.status_code == 200, f"Deploy failed: {r.text}"
    deploy_data = r.json()
    mesh_id = deploy_data["mesh_id"]
    join_token = deploy_data["join_config"]["token"]

    return {
        "admin_token": admin_token,
        "usr_token": usr_token,
        "mesh_id": mesh_id,
        "join_token": join_token,
    }


# ---------------------------------------------------------------------------
# Node Registration (legacy flow — uses mesh_provisioner)
# ---------------------------------------------------------------------------

class TestNodeRegistration:
    def test_register_success(self, client, node_data):
        r = client.post(
            f"/api/v1/maas/{node_data['mesh_id']}/nodes/register",
            json={"enrollment_token": node_data["join_token"], "device_class": "gateway"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "pending_approval"
        assert "node_id" in data

    def test_register_generates_auto_node_id(self, client, node_data):
        r = client.post(
            f"/api/v1/maas/{node_data['mesh_id']}/nodes/register",
            json={"enrollment_token": node_data["join_token"]},
        )
        assert r.status_code == 200, r.text
        assert r.json()["node_id"].startswith("node-")

    def test_register_custom_node_id(self, client, node_data):
        custom_id = f"custom-{uuid.uuid4().hex[:8]}"
        r = client.post(
            f"/api/v1/maas/{node_data['mesh_id']}/nodes/register",
            json={"enrollment_token": node_data["join_token"], "node_id": custom_id},
        )
        assert r.status_code == 200, r.text
        assert r.json()["node_id"] == custom_id

    def test_register_invalid_token(self, client, node_data):
        r = client.post(
            f"/api/v1/maas/{node_data['mesh_id']}/nodes/register",
            json={"enrollment_token": "wrong-token-1234567890"},  # ≥16 chars but wrong
        )
        assert r.status_code == 401

    def test_register_unknown_mesh(self, client):
        r = client.post(
            "/api/v1/maas/mesh-nonexistent-xyz/nodes/register",
            json={"enrollment_token": "any-token-1234567890"},  # ≥16 chars
        )
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# List Pending (legacy flow — requires operator role + mesh ownership)
# ---------------------------------------------------------------------------

class TestListPending:
    def test_requires_auth(self, client, node_data):
        r = client.get(f"/api/v1/maas/{node_data['mesh_id']}/nodes/pending")
        assert r.status_code == 401

    def test_user_role_forbidden(self, client, node_data):
        r = client.get(
            f"/api/v1/maas/{node_data['mesh_id']}/nodes/pending",
            headers={"X-API-Key": node_data["usr_token"]},
        )
        assert r.status_code == 403

    def test_operator_sees_pending_nodes(self, client, node_data):
        # Register a node so there's something pending
        r_reg = client.post(
            f"/api/v1/maas/{node_data['mesh_id']}/nodes/register",
            json={"enrollment_token": node_data["join_token"], "device_class": "sensor"},
        )
        registered_id = r_reg.json()["node_id"]

        r = client.get(
            f"/api/v1/maas/{node_data['mesh_id']}/nodes/pending",
            headers={"X-API-Key": node_data["admin_token"]},
        )
        assert r.status_code == 200, r.text
        pending = r.json()["pending"]
        assert registered_id in pending


# ---------------------------------------------------------------------------
# Approve (legacy flow — owner can approve via get_current_user)
# ---------------------------------------------------------------------------

class TestApprove:
    def _register(self, client, node_data):
        r = client.post(
            f"/api/v1/maas/{node_data['mesh_id']}/nodes/register",
            json={"enrollment_token": node_data["join_token"]},
        )
        return r.json()["node_id"]

    def test_approve_success(self, client, node_data):
        nid = self._register(client, node_data)
        r = client.post(
            f"/api/v1/maas/{node_data['mesh_id']}/nodes/{nid}/approve",
            json={},
            headers={"X-API-Key": node_data["admin_token"]},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "approved"
        assert "join_token" in data

    def test_approve_returns_pqc_token(self, client, node_data):
        nid = self._register(client, node_data)
        r = client.post(
            f"/api/v1/maas/{node_data['mesh_id']}/nodes/{nid}/approve",
            json={},
            headers={"X-API-Key": node_data["admin_token"]},
        )
        token = r.json()["join_token"]
        # PQC or HMAC-signed token must have "token" and "signature" keys
        assert "token" in token
        assert "signature" in token

    def test_approve_unknown_node(self, client, node_data):
        r = client.post(
            f"/api/v1/maas/{node_data['mesh_id']}/nodes/ghost-node-xyz/approve",
            json={},
            headers={"X-API-Key": node_data["admin_token"]},
        )
        assert r.status_code == 404

    def test_approved_node_absent_from_pending(self, client, node_data):
        nid = self._register(client, node_data)
        client.post(
            f"/api/v1/maas/{node_data['mesh_id']}/nodes/{nid}/approve",
            json={},
            headers={"X-API-Key": node_data["admin_token"]},
        )
        r = client.get(
            f"/api/v1/maas/{node_data['mesh_id']}/nodes/pending",
            headers={"X-API-Key": node_data["admin_token"]},
        )
        assert nid not in r.json()["pending"]


# ---------------------------------------------------------------------------
# Revoke (legacy flow — requires node:revoke permission + ownership)
# ---------------------------------------------------------------------------

class TestRevoke:
    def _registered_and_approved(self, client, node_data):
        r = client.post(
            f"/api/v1/maas/{node_data['mesh_id']}/nodes/register",
            json={"enrollment_token": node_data["join_token"]},
        )
        nid = r.json()["node_id"]
        client.post(
            f"/api/v1/maas/{node_data['mesh_id']}/nodes/{nid}/approve",
            json={},
            headers={"X-API-Key": node_data["admin_token"]},
        )
        return nid

    def test_revoke_requires_permission(self, client, node_data):
        """user role lacks node:revoke → 403"""
        nid = self._registered_and_approved(client, node_data)
        r = client.post(
            f"/api/v1/maas/{node_data['mesh_id']}/nodes/{nid}/revoke",
            json={},
            headers={"X-API-Key": node_data["usr_token"]},
        )
        assert r.status_code == 403

    def test_revoke_success(self, client, node_data):
        nid = self._registered_and_approved(client, node_data)
        r = client.post(
            f"/api/v1/maas/{node_data['mesh_id']}/nodes/{nid}/revoke",
            json={},
            headers={"X-API-Key": node_data["admin_token"]},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "revoked"
        assert data["node_id"] == nid

    def test_revoke_unknown_node(self, client, node_data):
        r = client.post(
            f"/api/v1/maas/{node_data['mesh_id']}/nodes/nonexistent-nd/revoke",
            json={},
            headers={"X-API-Key": node_data["admin_token"]},
        )
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# List All Nodes (legacy flow — operator + ownership)
# ---------------------------------------------------------------------------

class TestListAllNodes:
    def test_requires_operator(self, client, node_data):
        r = client.get(
            f"/api/v1/maas/{node_data['mesh_id']}/nodes/all",
            headers={"X-API-Key": node_data["usr_token"]},
        )
        assert r.status_code == 403

    def test_requires_auth(self, client, node_data):
        r = client.get(f"/api/v1/maas/{node_data['mesh_id']}/nodes/all")
        assert r.status_code == 401

    def test_operator_gets_list(self, client, node_data):
        r = client.get(
            f"/api/v1/maas/{node_data['mesh_id']}/nodes/all",
            headers={"X-API-Key": node_data["admin_token"]},
        )
        assert r.status_code == 200, r.text
        # Legacy returns a list of node dicts
        data = r.json()
        assert isinstance(data, (list, dict))


# ---------------------------------------------------------------------------
# Heartbeat (maas_nodes.py — unique route, uses SQLAlchemy DB)
# ---------------------------------------------------------------------------

class TestHeartbeat:
    def _db_node(self, mesh_id="mesh-hb-test"):
        db = TestingSessionLocal()
        nid = f"hb-{uuid.uuid4().hex[:8]}"
        db.add(MeshNode(
            id=nid, mesh_id=mesh_id,
            device_class="edge", status="approved",
        ))
        db.commit()
        db.close()
        return nid, mesh_id

    def test_heartbeat_success(self, client):
        nid, mesh_id = self._db_node()
        r = client.post(
            f"/api/v1/maas/{mesh_id}/nodes/{nid}/heartbeat",
            json={"status": "healthy"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["node_id"] == nid
        assert data["mesh_id"] == mesh_id
        assert "last_seen" in data

    def test_heartbeat_updates_last_seen_in_db(self, client):
        nid, mesh_id = self._db_node()
        client.post(
            f"/api/v1/maas/{mesh_id}/nodes/{nid}/heartbeat",
            json={"status": "healthy"},
        )
        db = TestingSessionLocal()
        node = db.query(MeshNode).filter(MeshNode.id == nid).first()
        assert node.last_seen is not None
        db.close()

    def test_heartbeat_healthy_sets_approved(self, client):
        nid, mesh_id = self._db_node()
        r = client.post(
            f"/api/v1/maas/{mesh_id}/nodes/{nid}/heartbeat",
            json={"status": "healthy"},
        )
        assert r.json()["node_status"] == "approved"

    def test_heartbeat_unhealthy_sets_degraded(self, client):
        nid, mesh_id = self._db_node()
        r = client.post(
            f"/api/v1/maas/{mesh_id}/nodes/{nid}/heartbeat",
            json={"status": "unhealthy"},
        )
        assert r.json()["node_status"] == "degraded"

    def test_heartbeat_unknown_node_404(self, client):
        r = client.post(
            "/api/v1/maas/mesh-hb-test/nodes/ghost-node/heartbeat",
            json={"status": "healthy"},
        )
        assert r.status_code == 404

    def test_heartbeat_invalid_status_422(self, client):
        nid, mesh_id = self._db_node()
        r = client.post(
            f"/api/v1/maas/{mesh_id}/nodes/{nid}/heartbeat",
            json={"status": "exploding"},
        )
        assert r.status_code == 422

    def test_heartbeat_auto_releases_escrow(self, client):
        nid, mesh_id = self._db_node()

        db = TestingSessionLocal()
        # Need an owner user in DB for the escrow (use admin — created in node_data fixture)
        op = db.query(User).filter(User.role == "admin").first()
        listing = MarketplaceListing(
            id=f"lst-{uuid.uuid4().hex[:8]}",
            owner_id=op.id,
            node_id=nid,
            price_per_hour=100,
            status="escrow",
        )
        db.add(listing)
        db.flush()
        escrow = MarketplaceEscrow(
            id=f"esc-{uuid.uuid4().hex[:8]}",
            listing_id=listing.id,
            renter_id=op.id,
            amount_cents=100,
            status="held",
        )
        db.add(escrow)
        db.commit()
        escrow_id = escrow.id
        db.close()

        r = client.post(
            f"/api/v1/maas/{mesh_id}/nodes/{nid}/heartbeat",
            json={"status": "healthy"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["escrow_released"] == escrow_id

        db = TestingSessionLocal()
        e = db.query(MarketplaceEscrow).filter(MarketplaceEscrow.id == escrow_id).first()
        assert e.status == "released"
        assert e.released_at is not None
        db.close()


# ---------------------------------------------------------------------------
# Check-Access ACL (maas_nodes.py — unique route, uses SQLAlchemy DB)
# ---------------------------------------------------------------------------

class TestCheckAccess:
    _mesh_id = "mesh-acl-test"

    def _node(self, acl_profile="default"):
        db = TestingSessionLocal()
        nid = f"acl-{uuid.uuid4().hex[:8]}"
        db.add(MeshNode(
            id=nid, mesh_id=self._mesh_id,
            device_class="edge", status="approved",
            acl_profile=acl_profile,
        ))
        db.commit()
        db.close()
        return nid

    def test_default_deny_no_policies(self, client):
        src = self._node("zone-a")
        tgt = self._node("zone-b")
        r = client.post(
            f"/api/v1/maas/{self._mesh_id}/nodes/check-access",
            json={"source_node_id": src, "target_node_id": tgt},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["verdict"] == "deny"
        assert data["policy_id"] is None

    def test_allow_with_matching_policy(self, client):
        src = self._node("frontend")
        tgt = self._node("backend")

        db = TestingSessionLocal()
        db.add(ACLPolicy(
            id=f"pol-{uuid.uuid4().hex[:8]}",
            mesh_id=self._mesh_id,
            source_tag="frontend",
            target_tag="backend",
            action="allow",
        ))
        db.commit()
        db.close()

        r = client.post(
            f"/api/v1/maas/{self._mesh_id}/nodes/check-access",
            json={"source_node_id": src, "target_node_id": tgt},
        )
        assert r.json()["verdict"] == "allow"
        assert r.json()["policy_id"] is not None

    def test_explicit_deny_policy(self, client):
        src = self._node("untrusted")
        tgt = self._node("critical")

        db = TestingSessionLocal()
        db.add(ACLPolicy(
            id=f"pol-{uuid.uuid4().hex[:8]}",
            mesh_id=self._mesh_id,
            source_tag="untrusted",
            target_tag="critical",
            action="deny",
        ))
        db.commit()
        db.close()

        r = client.post(
            f"/api/v1/maas/{self._mesh_id}/nodes/check-access",
            json={"source_node_id": src, "target_node_id": tgt},
        )
        assert r.json()["verdict"] == "deny"

    def test_wildcard_policy(self, client):
        src = self._node("admin")
        tgt = self._node("any-zone")

        db = TestingSessionLocal()
        db.add(ACLPolicy(
            id=f"pol-{uuid.uuid4().hex[:8]}",
            mesh_id=self._mesh_id,
            source_tag="admin",
            target_tag="*",
            action="allow",
        ))
        db.commit()
        db.close()

        r = client.post(
            f"/api/v1/maas/{self._mesh_id}/nodes/check-access",
            json={"source_node_id": src, "target_node_id": tgt},
        )
        assert r.json()["verdict"] == "allow"

    def test_unknown_nodes_404(self, client):
        r = client.post(
            f"/api/v1/maas/{self._mesh_id}/nodes/check-access",
            json={"source_node_id": "ghost-a", "target_node_id": "ghost-b"},
        )
        assert r.status_code == 404

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
    MeshInstance, MeshNode, User, get_db,
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
    def _db_node(self, mesh_id="mesh-hb-test", status="approved"):
        db = TestingSessionLocal()
        nid = f"hb-{uuid.uuid4().hex[:8]}"
        db.add(MeshNode(
            id=nid, mesh_id=mesh_id,
            device_class="edge", status=status,
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

    def test_heartbeat_degraded_sets_degraded(self, client):
        nid, mesh_id = self._db_node()
        r = client.post(
            f"/api/v1/maas/{mesh_id}/nodes/{nid}/heartbeat",
            json={"status": "degraded"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["node_status"] == "degraded"

    def test_heartbeat_unknown_node_404(self, client):
        r = client.post(
            "/api/v1/maas/mesh-hb-test/nodes/ghost-node/heartbeat",
            json={"status": "healthy"},
        )
        assert r.status_code == 404

    def test_heartbeat_rejects_pending_node(self, client):
        nid, mesh_id = self._db_node(status="pending")
        r = client.post(
            f"/api/v1/maas/{mesh_id}/nodes/{nid}/heartbeat",
            json={"status": "healthy"},
        )
        assert r.status_code == 403
        assert r.json()["detail"] == "Node is not approved for heartbeat"

    def test_heartbeat_rejects_revoked_node(self, client):
        nid, mesh_id = self._db_node(status="revoked")
        r = client.post(
            f"/api/v1/maas/{mesh_id}/nodes/{nid}/heartbeat",
            json={"status": "healthy"},
        )
        assert r.status_code == 403
        assert r.json()["detail"] == "Node is not approved for heartbeat"

    def test_heartbeat_exports_telemetry_for_analytics(self, client, monkeypatch):
        nid, mesh_id = self._db_node()
        captured = {}

        def fake_export(node_id, payload):
            captured["node_id"] = node_id
            captured["payload"] = payload

        monkeypatch.setattr("src.api.maas_nodes._set_external_telemetry", fake_export)
        r = client.post(
            f"/api/v1/maas/{mesh_id}/nodes/{nid}/heartbeat",
            json={
                "status": "healthy",
                "cpu_percent": 23.5,
                "mem_percent": 44.1,
                "latency_ms": 12.7,
                "traffic_mbps": 88.9,
                "active_connections": 15,
            },
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["telemetry_exported"] is True
        assert captured["node_id"] == nid
        assert captured["payload"]["mesh_id"] == mesh_id
        assert captured["payload"]["latency_ms"] == 12.7
        assert captured["payload"]["traffic_mbps"] == 88.9
        assert captured["payload"]["active_connections"] == 15

    def test_heartbeat_uses_custom_metrics_fallback_for_export(self, client, monkeypatch):
        nid, mesh_id = self._db_node()
        captured = {}

        def fake_export(node_id, payload):
            captured["node_id"] = node_id
            captured["payload"] = payload

        monkeypatch.setattr("src.api.maas_nodes._set_external_telemetry", fake_export)
        r = client.post(
            f"/api/v1/maas/{mesh_id}/nodes/{nid}/heartbeat",
            json={
                "status": "healthy",
                "custom_metrics": {"latency_ms": "33.3", "traffic_mbps": "120.2"},
            },
        )
        assert r.status_code == 200, r.text
        assert r.json()["telemetry_exported"] is True
        assert captured["payload"]["latency_ms"] == 33.3
        assert captured["payload"]["traffic_mbps"] == 120.2

    def test_heartbeat_export_failure_is_non_blocking(self, client, monkeypatch):
        nid, mesh_id = self._db_node()

        def broken_export(*args, **kwargs):
            raise RuntimeError("redis unavailable")

        monkeypatch.setattr("src.api.maas_nodes._set_external_telemetry", broken_export)
        r = client.post(
            f"/api/v1/maas/{mesh_id}/nodes/{nid}/heartbeat",
            json={"status": "healthy"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["telemetry_exported"] is False

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
# Node Telemetry Readback (maas_nodes.py — unique route, SQLAlchemy + telemetry backend)
# ---------------------------------------------------------------------------

class TestNodeTelemetryReadback:
    def _db_node(self, mesh_id="mesh-telemetry-test"):
        db = TestingSessionLocal()
        nid = f"telem-{uuid.uuid4().hex[:8]}"
        db.add(MeshNode(
            id=nid, mesh_id=mesh_id,
            device_class="edge", status="approved",
        ))
        db.commit()
        db.close()
        return nid, mesh_id

    def _create_operator(self, client):
        email = f"telem-op-{uuid.uuid4().hex[:8]}@test.com"
        r = client.post(
            "/api/v1/maas/auth/register",
            json={"email": email, "password": "password123"},
        )
        assert r.status_code == 200, r.text
        token = r.json()["access_token"]
        db = TestingSessionLocal()
        user = db.query(User).filter(User.api_key == token).first()
        user.role = "operator"
        user_id = user.id
        db.commit()
        db.close()
        return token, user_id

    def _db_node_with_owner(self, owner_id: str):
        mesh_id = f"mesh-telemetry-{uuid.uuid4().hex[:8]}"
        node_id = f"telem-{uuid.uuid4().hex[:8]}"
        db = TestingSessionLocal()
        db.add(MeshInstance(
            id=mesh_id,
            name="Telemetry Access Test Mesh",
            owner_id=owner_id,
            status="active",
        ))
        db.add(MeshNode(
            id=node_id,
            mesh_id=mesh_id,
            device_class="edge",
            status="approved",
        ))
        db.commit()
        db.close()
        return node_id, mesh_id

    def test_requires_auth(self, client):
        nid, mesh_id = self._db_node()
        r = client.get(f"/api/v1/maas/{mesh_id}/nodes/{nid}/telemetry")
        assert r.status_code == 401

    def test_user_role_forbidden(self, client, node_data):
        nid, mesh_id = self._db_node()
        r = client.get(
            f"/api/v1/maas/{mesh_id}/nodes/{nid}/telemetry",
            headers={"X-API-Key": node_data["usr_token"]},
        )
        assert r.status_code == 403

    def test_unknown_node_returns_404(self, client, node_data):
        r = client.get(
            "/api/v1/maas/mesh-telemetry-test/nodes/node-missing/telemetry",
            headers={"X-API-Key": node_data["admin_token"]},
        )
        assert r.status_code == 404

    def test_returns_snapshot_and_history_after_heartbeat(self, client, node_data):
        nid, mesh_id = self._db_node()
        hb = client.post(
            f"/api/v1/maas/{mesh_id}/nodes/{nid}/heartbeat",
            json={
                "status": "healthy",
                "latency_ms": 14.2,
                "traffic_mbps": 77.7,
                "custom_metrics": {"source": "integration-test"},
            },
        )
        assert hb.status_code == 200, hb.text

        r = client.get(
            f"/api/v1/maas/{mesh_id}/nodes/{nid}/telemetry?history_limit=5",
            headers={"X-API-Key": node_data["admin_token"]},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["mesh_id"] == mesh_id
        assert data["node_id"] == nid
        assert isinstance(data["snapshot"], dict)
        assert data["snapshot"].get("latency_ms") == 14.2
        assert data["snapshot"].get("traffic_mbps") == 77.7
        assert isinstance(data["history"], list)
        assert data["history_count"] >= 1
        latest = data["history"][0]
        assert latest.get("latency_ms") == 14.2
        assert latest.get("traffic_mbps") == 77.7

    def test_history_limit_is_enforced(self, client, node_data):
        nid, mesh_id = self._db_node()
        for idx in range(3):
            hb = client.post(
                f"/api/v1/maas/{mesh_id}/nodes/{nid}/heartbeat",
                json={
                    "status": "healthy",
                    "latency_ms": 10.0 + idx,
                    "traffic_mbps": 50.0 + idx,
                },
            )
            assert hb.status_code == 200, hb.text

        r = client.get(
            f"/api/v1/maas/{mesh_id}/nodes/{nid}/telemetry?history_limit=2",
            headers={"X-API-Key": node_data["admin_token"]},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["history_count"] == 2

    def test_operator_owner_can_read_telemetry(self, client):
        op_token, op_user_id = self._create_operator(client)
        nid, mesh_id = self._db_node_with_owner(op_user_id)
        hb = client.post(
            f"/api/v1/maas/{mesh_id}/nodes/{nid}/heartbeat",
            json={"status": "healthy", "latency_ms": 21.0, "traffic_mbps": 101.0},
        )
        assert hb.status_code == 200, hb.text

        r = client.get(
            f"/api/v1/maas/{mesh_id}/nodes/{nid}/telemetry",
            headers={"X-API-Key": op_token},
        )
        assert r.status_code == 200, r.text
        assert r.json()["node_id"] == nid

    def test_operator_cannot_read_foreign_mesh_telemetry(self, client, node_data):
        op_token, _ = self._create_operator(client)
        db = TestingSessionLocal()
        admin = db.query(User).filter(User.api_key == node_data["admin_token"]).first()
        admin_id = admin.id
        db.close()
        nid, mesh_id = self._db_node_with_owner(admin_id)

        r = client.get(
            f"/api/v1/maas/{mesh_id}/nodes/{nid}/telemetry",
            headers={"X-API-Key": op_token},
        )
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Check-Access ACL (maas_nodes.py — unique route, uses SQLAlchemy DB)
# ---------------------------------------------------------------------------

class TestCheckAccess:
    _mesh_id = "mesh-acl-test"

    def _node(self, acl_profile="default", status="approved"):
        db = TestingSessionLocal()
        nid = f"acl-{uuid.uuid4().hex[:8]}"
        db.add(MeshNode(
            id=nid, mesh_id=self._mesh_id,
            device_class="edge", status=status,
            acl_profile=acl_profile,
        ))
        db.commit()
        db.close()
        return nid

    @staticmethod
    def _admin_headers(node_data):
        return {"X-API-Key": node_data["admin_token"]}

    def test_default_deny_no_policies(self, client, node_data):
        src = self._node("zone-a")
        tgt = self._node("zone-b")
        r = client.post(
            f"/api/v1/maas/{self._mesh_id}/nodes/check-access",
            json={"source_node_id": src, "target_node_id": tgt},
            headers=self._admin_headers(node_data),
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["verdict"] == "deny"
        assert data["policy_id"] is None

    def test_allow_with_matching_policy(self, client, node_data):
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
            headers=self._admin_headers(node_data),
        )
        assert r.json()["verdict"] == "allow"
        assert r.json()["policy_id"] is not None

    def test_explicit_deny_policy(self, client, node_data):
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
            headers=self._admin_headers(node_data),
        )
        assert r.json()["verdict"] == "deny"

    def test_wildcard_policy(self, client, node_data):
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
            headers=self._admin_headers(node_data),
        )
        assert r.json()["verdict"] == "allow"

    def test_unknown_nodes_404(self, client, node_data):
        r = client.post(
            f"/api/v1/maas/{self._mesh_id}/nodes/check-access",
            json={"source_node_id": "ghost-a", "target_node_id": "ghost-b"},
            headers=self._admin_headers(node_data),
        )
        assert r.status_code == 404

    def test_denies_if_source_not_approved_even_with_allow_policy(self, client, node_data):
        src = self._node("frontend", status="pending")
        tgt = self._node("backend", status="approved")

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
            headers=self._admin_headers(node_data),
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["verdict"] == "deny"
        assert data["policy_id"] is None
        assert data["reason"] == "source or target node is not approved"

    def test_denies_if_target_not_approved_even_with_allow_policy(self, client, node_data):
        src = self._node("frontend", status="approved")
        tgt = self._node("backend", status="revoked")

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
            headers=self._admin_headers(node_data),
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["verdict"] == "deny"
        assert data["policy_id"] is None
        assert data["reason"] == "source or target node is not approved"


# ---------------------------------------------------------------------------
# Unit-style tests for node utility functions (no TestClient needed)
# ---------------------------------------------------------------------------

class TestNodeUtilityFunctions:
    """Direct tests for _to_optional_float, _export_analytics_telemetry,
    _read_external_telemetry, _read_external_telemetry_history.
    No TestClient is needed — functions are tested directly via import.
    """

    def test_to_optional_float_none_returns_none(self):
        from src.api.maas_nodes import _to_optional_float
        assert _to_optional_float(None) is None

    def test_to_optional_float_valid_converts(self):
        from src.api.maas_nodes import _to_optional_float
        assert _to_optional_float("3.14") == pytest.approx(3.14)
        assert _to_optional_float(42) == pytest.approx(42.0)

    def test_to_optional_float_invalid_returns_none(self):
        from src.api.maas_nodes import _to_optional_float
        assert _to_optional_float("not_a_number") is None
        assert _to_optional_float([1, 2]) is None

    def test_export_analytics_telemetry_none_exporter_returns_false(self):
        from unittest.mock import patch
        import src.api.maas_nodes as nmod
        with patch.object(nmod, "_set_external_telemetry", None):
            from src.api.maas_nodes import _export_analytics_telemetry
            result = nmod._export_analytics_telemetry("n1", {"k": "v"})
        assert result is False

    def test_export_analytics_telemetry_success_returns_true(self):
        from unittest.mock import MagicMock, patch
        import src.api.maas_nodes as nmod
        mock_exporter = MagicMock()
        with patch.object(nmod, "_set_external_telemetry", mock_exporter):
            result = nmod._export_analytics_telemetry("n1", {"k": "v"})
        assert result is True
        mock_exporter.assert_called_once_with("n1", {"k": "v"})

    def test_export_analytics_telemetry_exception_returns_false(self):
        from unittest.mock import MagicMock, patch
        import src.api.maas_nodes as nmod
        mock_exporter = MagicMock(side_effect=RuntimeError("write error"))
        with patch.object(nmod, "_set_external_telemetry", mock_exporter):
            result = nmod._export_analytics_telemetry("n-err", {})
        assert result is False

    def test_read_external_telemetry_none_getter_returns_empty(self):
        from unittest.mock import patch
        import src.api.maas_nodes as nmod
        with patch.object(nmod, "_get_external_telemetry", None):
            result = nmod._read_external_telemetry("n1")
        assert result == {}

    def test_read_external_telemetry_non_dict_returns_empty(self):
        from unittest.mock import MagicMock, patch
        import src.api.maas_nodes as nmod
        with patch.object(nmod, "_get_external_telemetry", MagicMock(return_value=["list"])):
            result = nmod._read_external_telemetry("n1")
        assert result == {}

    def test_read_external_telemetry_exception_returns_empty(self):
        from unittest.mock import MagicMock, patch
        import src.api.maas_nodes as nmod
        with patch.object(nmod, "_get_external_telemetry", MagicMock(side_effect=Exception("err"))):
            result = nmod._read_external_telemetry("n-err")
        assert result == {}

    def test_read_external_telemetry_history_none_getter_returns_empty_list(self):
        from unittest.mock import patch
        import src.api.maas_nodes as nmod
        with patch.object(nmod, "_get_external_telemetry_history", None):
            result = nmod._read_external_telemetry_history("n1", 10)
        assert result == []

    def test_read_external_telemetry_history_non_list_returns_empty_list(self):
        from unittest.mock import MagicMock, patch
        import src.api.maas_nodes as nmod
        with patch.object(nmod, "_get_external_telemetry_history", MagicMock(return_value={"k": "v"})):
            result = nmod._read_external_telemetry_history("n1", 10)
        assert result == []

    def test_read_external_telemetry_history_filters_non_dicts(self):
        from unittest.mock import MagicMock, patch
        import src.api.maas_nodes as nmod
        with patch.object(nmod, "_get_external_telemetry_history",
                          MagicMock(return_value=[{"ok": True}, "bad", 42, {"also": "ok"}])):
            result = nmod._read_external_telemetry_history("n1", 10)
        assert result == [{"ok": True}, {"also": "ok"}]

    def test_read_external_telemetry_history_exception_returns_empty_list(self):
        from unittest.mock import MagicMock, patch
        import src.api.maas_nodes as nmod
        with patch.object(nmod, "_get_external_telemetry_history",
                          MagicMock(side_effect=Exception("err"))):
            result = nmod._read_external_telemetry_history("n-err", 5)
        assert result == []

    # _build_analytics_telemetry_payload branch coverage

    def test_build_analytics_telemetry_payload_latency_from_req(self):
        """latency_ms set on req → included in payload."""
        from src.api.maas_nodes import _build_analytics_telemetry_payload, HeartbeatRequest
        req = HeartbeatRequest(status="healthy", latency_ms=25.0)
        payload = _build_analytics_telemetry_payload("m1", "n1", req, "2026-01-01T00:00:00")
        assert payload["latency_ms"] == 25.0

    def test_build_analytics_telemetry_payload_latency_from_custom_metrics(self):
        """latency_ms not on req but in custom_metrics → used."""
        from src.api.maas_nodes import _build_analytics_telemetry_payload, HeartbeatRequest
        req = HeartbeatRequest(status="healthy", custom_metrics={"latency_ms": 15.5})
        payload = _build_analytics_telemetry_payload("m1", "n1", req, "2026-01-01T00:00:00")
        assert payload["latency_ms"] == 15.5

    def test_build_analytics_telemetry_payload_negative_latency_excluded(self):
        """Negative latency → NOT included in payload."""
        from src.api.maas_nodes import _build_analytics_telemetry_payload, HeartbeatRequest
        req = HeartbeatRequest(status="healthy", latency_ms=-1.0)
        payload = _build_analytics_telemetry_payload("m1", "n1", req, "2026-01-01T00:00:00")
        assert "latency_ms" not in payload

    def test_build_analytics_telemetry_payload_traffic_from_req(self):
        """traffic_mbps set on req → included in payload."""
        from src.api.maas_nodes import _build_analytics_telemetry_payload, HeartbeatRequest
        req = HeartbeatRequest(status="healthy", traffic_mbps=100.0)
        payload = _build_analytics_telemetry_payload("m1", "n1", req, "2026-01-01T00:00:00")
        assert payload["traffic_mbps"] == 100.0

    def test_build_analytics_telemetry_payload_traffic_from_custom_metrics(self):
        """traffic_mbps not on req but in custom_metrics → used."""
        from src.api.maas_nodes import _build_analytics_telemetry_payload, HeartbeatRequest
        req = HeartbeatRequest(status="healthy", custom_metrics={"traffic_mbps": 50.0})
        payload = _build_analytics_telemetry_payload("m1", "n1", req, "2026-01-01T00:00:00")
        assert payload["traffic_mbps"] == 50.0

    def test_build_analytics_telemetry_payload_negative_traffic_excluded(self):
        """Negative traffic → NOT included in payload."""
        from src.api.maas_nodes import _build_analytics_telemetry_payload, HeartbeatRequest
        req = HeartbeatRequest(status="healthy", traffic_mbps=-5.0)
        payload = _build_analytics_telemetry_payload("m1", "n1", req, "2026-01-01T00:00:00")
        assert "traffic_mbps" not in payload

    def test_build_analytics_telemetry_payload_core_fields_always_present(self):
        """Core fields always present regardless of optional values."""
        from src.api.maas_nodes import _build_analytics_telemetry_payload, HeartbeatRequest
        req = HeartbeatRequest(status="degraded", cpu_percent=55.0)
        payload = _build_analytics_telemetry_payload("mesh-x", "node-y", req, "2026-02-22T12:00:00")
        assert payload["mesh_id"] == "mesh-x"
        assert payload["node_id"] == "node-y"
        assert payload["status"] == "degraded"
        assert payload["cpu_percent"] == 55.0
        assert payload["timestamp"] == "2026-02-22T12:00:00"


# ---------------------------------------------------------------------------
# Unit-style tests for _to_optional_float
# ---------------------------------------------------------------------------

class TestToOptionalFloat:
    """Direct tests for _to_optional_float conversion helper."""

    def test_none_returns_none(self):
        from src.api.maas_nodes import _to_optional_float
        assert _to_optional_float(None) is None

    def test_valid_int_returns_float(self):
        from src.api.maas_nodes import _to_optional_float
        result = _to_optional_float(42)
        assert result == 42.0
        assert isinstance(result, float)

    def test_valid_string_returns_float(self):
        from src.api.maas_nodes import _to_optional_float
        result = _to_optional_float("3.14")
        assert abs(result - 3.14) < 1e-9

    def test_invalid_string_returns_none(self):
        from src.api.maas_nodes import _to_optional_float
        assert _to_optional_float("not-a-number") is None

    def test_invalid_type_returns_none(self):
        from src.api.maas_nodes import _to_optional_float
        assert _to_optional_float({"key": "value"}) is None


# ---------------------------------------------------------------------------
# Unit-style tests for _export_analytics_telemetry,
# _read_external_telemetry, _read_external_telemetry_history
# ---------------------------------------------------------------------------

class TestExternalTelemetryHelpers:
    """Tests for telemetry import/export helper functions."""

    def test_export_returns_false_when_setter_is_none(self):
        from unittest.mock import patch
        from src.api import maas_nodes as mod
        from src.api.maas_nodes import _export_analytics_telemetry
        with patch.object(mod, "_set_external_telemetry", None):
            result = _export_analytics_telemetry("node-x", {"cpu": 10.0})
        assert result is False

    def test_export_returns_true_when_setter_succeeds(self):
        from unittest.mock import patch, MagicMock
        from src.api import maas_nodes as mod
        from src.api.maas_nodes import _export_analytics_telemetry
        mock_setter = MagicMock()
        with patch.object(mod, "_set_external_telemetry", mock_setter):
            result = _export_analytics_telemetry("node-x", {"cpu": 10.0})
        assert result is True
        mock_setter.assert_called_once_with("node-x", {"cpu": 10.0})

    def test_export_returns_false_when_setter_raises(self):
        from unittest.mock import patch, MagicMock
        from src.api import maas_nodes as mod
        from src.api.maas_nodes import _export_analytics_telemetry
        mock_setter = MagicMock(side_effect=Exception("redis down"))
        with patch.object(mod, "_set_external_telemetry", mock_setter):
            result = _export_analytics_telemetry("node-x", {"cpu": 10.0})
        assert result is False

    def test_read_external_returns_empty_when_getter_is_none(self):
        from unittest.mock import patch
        from src.api import maas_nodes as mod
        from src.api.maas_nodes import _read_external_telemetry
        with patch.object(mod, "_get_external_telemetry", None):
            result = _read_external_telemetry("node-x")
        assert result == {}

    def test_read_external_returns_empty_when_getter_raises(self):
        from unittest.mock import patch, MagicMock
        from src.api import maas_nodes as mod
        from src.api.maas_nodes import _read_external_telemetry
        mock_getter = MagicMock(side_effect=Exception("timeout"))
        with patch.object(mod, "_get_external_telemetry", mock_getter):
            result = _read_external_telemetry("node-x")
        assert result == {}

    def test_read_external_returns_empty_when_result_not_dict(self):
        from unittest.mock import patch, MagicMock
        from src.api import maas_nodes as mod
        from src.api.maas_nodes import _read_external_telemetry
        mock_getter = MagicMock(return_value=["not", "a", "dict"])
        with patch.object(mod, "_get_external_telemetry", mock_getter):
            result = _read_external_telemetry("node-x")
        assert result == {}

    def test_read_external_returns_dict_when_getter_succeeds(self):
        from unittest.mock import patch, MagicMock
        from src.api import maas_nodes as mod
        from src.api.maas_nodes import _read_external_telemetry
        mock_getter = MagicMock(return_value={"cpu": 42.0})
        with patch.object(mod, "_get_external_telemetry", mock_getter):
            result = _read_external_telemetry("node-x")
        assert result == {"cpu": 42.0}

    def test_read_history_returns_empty_when_getter_is_none(self):
        from unittest.mock import patch
        from src.api import maas_nodes as mod
        from src.api.maas_nodes import _read_external_telemetry_history
        with patch.object(mod, "_get_external_telemetry_history", None):
            result = _read_external_telemetry_history("node-x", limit=5)
        assert result == []

    def test_read_history_returns_empty_when_getter_raises(self):
        from unittest.mock import patch, MagicMock
        from src.api import maas_nodes as mod
        from src.api.maas_nodes import _read_external_telemetry_history
        mock_getter = MagicMock(side_effect=Exception("oops"))
        with patch.object(mod, "_get_external_telemetry_history", mock_getter):
            result = _read_external_telemetry_history("node-x", limit=5)
        assert result == []

    def test_read_history_returns_empty_when_result_not_list(self):
        from unittest.mock import patch, MagicMock
        from src.api import maas_nodes as mod
        from src.api.maas_nodes import _read_external_telemetry_history
        mock_getter = MagicMock(return_value={"not": "a list"})
        with patch.object(mod, "_get_external_telemetry_history", mock_getter):
            result = _read_external_telemetry_history("node-x", limit=5)
        assert result == []

    def test_read_history_filters_non_dicts(self):
        from unittest.mock import patch, MagicMock
        from src.api import maas_nodes as mod
        from src.api.maas_nodes import _read_external_telemetry_history
        mock_getter = MagicMock(return_value=[{"cpu": 1}, "bad", 42, {"mem": 2}])
        with patch.object(mod, "_get_external_telemetry_history", mock_getter):
            result = _read_external_telemetry_history("node-x", limit=10)
        assert result == [{"cpu": 1}, {"mem": 2}]

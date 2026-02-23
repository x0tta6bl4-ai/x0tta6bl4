"""
Integration tests for MaaS Dashboard:
- Summary endpoint (meshes, node stats, security attestation, audit, invoices)
- /nodes/{mesh_id} per-mesh node detail
- HARDWARE_ROOTED vs SOFTWARE_ONLY attestation classification
- Node health based on last_seen timestamp
"""

import os
import uuid
from datetime import datetime, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.app import app
from src.database import Base, get_db, User, MeshInstance, MeshNode

_TEST_DB_PATH = f"./test_dashboard_{uuid.uuid4().hex}.db"
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
def user_data(client):
    """Register user and return (token, user_id, mesh_id)."""
    email = f"dash-{uuid.uuid4().hex[:8]}@test.com"
    r = client.post(
        "/api/v1/maas/auth/register",
        json={"email": email, "password": "password123"},
    )
    token = r.json()["access_token"]

    db = TestingSessionLocal()
    user = db.query(User).filter(User.api_key == token).first()
    user_id = user.id

    # Create a DB-backed mesh + nodes
    mesh_id = f"mesh-dash-{uuid.uuid4().hex[:6]}"
    mesh = MeshInstance(
        id=mesh_id,
        name="Dashboard Test Mesh",
        owner_id=user_id,
        status="active",
        pqc_enabled=True,
    )
    db.add(mesh)

    # Node 1: hardware-rooted, recently seen (healthy)
    db.add(MeshNode(
        id=f"nd-hw-{uuid.uuid4().hex[:6]}",
        mesh_id=mesh_id,
        status="approved",
        device_class="gateway",
        hardware_id="tpm-abc123",
        enclave_enabled=True,
        last_seen=datetime.utcnow() - timedelta(minutes=1),
    ))
    # Node 2: software-only, stale
    db.add(MeshNode(
        id=f"nd-sw-{uuid.uuid4().hex[:6]}",
        mesh_id=mesh_id,
        status="approved",
        device_class="edge",
        hardware_id=None,
        enclave_enabled=False,
        last_seen=datetime.utcnow() - timedelta(minutes=15),
    ))
    # Node 3: no last_seen (unknown health)
    db.add(MeshNode(
        id=f"nd-un-{uuid.uuid4().hex[:6]}",
        mesh_id=mesh_id,
        status="approved",
        device_class="sensor",
        hardware_id=None,
        enclave_enabled=False,
        last_seen=None,
    ))
    db.commit()
    db.close()

    return {"token": token, "user_id": user_id, "mesh_id": mesh_id}


class TestDashboardSummary:
    def test_summary_requires_auth(self, client):
        r = client.get("/api/v1/maas/dashboard/summary")
        assert r.status_code == 401

    def test_summary_returns_user_info(self, client, user_data):
        r = client.get(
            "/api/v1/maas/dashboard/summary",
            headers={"X-API-Key": user_data["token"]},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "user" in data
        assert data["user"]["plan"] == "starter"

    def test_summary_mesh_count(self, client, user_data):
        r = client.get(
            "/api/v1/maas/dashboard/summary",
            headers={"X-API-Key": user_data["token"]},
        )
        data = r.json()
        assert data["stats"]["total_meshes"] >= 1
        mesh_ids = [m["id"] for m in data["meshes"]]
        assert user_data["mesh_id"] in mesh_ids

    def test_summary_node_attestation_stats(self, client, user_data):
        r = client.get(
            "/api/v1/maas/dashboard/summary",
            headers={"X-API-Key": user_data["token"]},
        )
        data = r.json()
        security = data["stats"]["security"]
        assert "HARDWARE_ROOTED" in security
        assert "SOFTWARE_ONLY" in security
        # We created 1 hardware-rooted node
        assert security["HARDWARE_ROOTED"] >= 1
        # We created 2 software-only nodes
        assert security["SOFTWARE_ONLY"] >= 2

    def test_summary_node_health_stats(self, client, user_data):
        r = client.get(
            "/api/v1/maas/dashboard/summary",
            headers={"X-API-Key": user_data["token"]},
        )
        data = r.json()
        health = data["stats"]["node_health"]
        assert health.get("healthy", 0) >= 1   # 1 min old = healthy
        assert health.get("stale", 0) >= 1     # 15 min old = stale
        assert health.get("unknown", 0) >= 1   # no last_seen

    def test_summary_total_nodes(self, client, user_data):
        r = client.get(
            "/api/v1/maas/dashboard/summary",
            headers={"X-API-Key": user_data["token"]},
        )
        data = r.json()
        assert data["stats"]["total_nodes"] >= 3

    def test_summary_has_audit_and_invoices(self, client, user_data):
        r = client.get(
            "/api/v1/maas/dashboard/summary",
            headers={"X-API-Key": user_data["token"]},
        )
        data = r.json()
        assert "recent_audit" in data
        assert "pending_invoices" in data
        assert isinstance(data["recent_audit"], list)
        assert isinstance(data["pending_invoices"], list)


class TestDashboardNodeDetail:
    def test_nodes_detail_returns_list(self, client, user_data):
        mesh_id = user_data["mesh_id"]
        r = client.get(
            f"/api/v1/maas/dashboard/nodes/{mesh_id}",
            headers={"X-API-Key": user_data["token"]},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["mesh_id"] == mesh_id
        assert data["count"] >= 3

    def test_nodes_hardware_rooted_classification(self, client, user_data):
        mesh_id = user_data["mesh_id"]
        r = client.get(
            f"/api/v1/maas/dashboard/nodes/{mesh_id}",
            headers={"X-API-Key": user_data["token"]},
        )
        nodes = r.json()["nodes"]
        att_types = {n["attestation"] for n in nodes}
        assert "HARDWARE_ROOTED" in att_types
        assert "SOFTWARE_ONLY" in att_types

    def test_nodes_health_classification(self, client, user_data):
        mesh_id = user_data["mesh_id"]
        r = client.get(
            f"/api/v1/maas/dashboard/nodes/{mesh_id}",
            headers={"X-API-Key": user_data["token"]},
        )
        nodes = r.json()["nodes"]
        health_values = {n["health"] for n in nodes}
        assert "healthy" in health_values
        assert "stale" in health_values
        assert "unknown" in health_values

    def test_nodes_unknown_mesh_404(self, client, user_data):
        r = client.get(
            "/api/v1/maas/dashboard/nodes/mesh-nonexistent",
            headers={"X-API-Key": user_data["token"]},
        )
        assert r.status_code == 404

    def test_nodes_requires_auth(self, client, user_data):
        r = client.get(f"/api/v1/maas/dashboard/nodes/{user_data['mesh_id']}")
        assert r.status_code == 401

    def test_nodes_other_user_mesh_404(self, client, user_data):
        # Register another user and try to access first user's mesh
        r2 = client.post(
            "/api/v1/maas/auth/register",
            json={"email": f"other-{uuid.uuid4().hex[:8]}@test.com", "password": "pw123456"},
        )
        other_token = r2.json()["access_token"]
        r = client.get(
            f"/api/v1/maas/dashboard/nodes/{user_data['mesh_id']}",
            headers={"X-API-Key": other_token},
        )
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Offline node health + admin audit path
# ---------------------------------------------------------------------------

class TestDashboardEdgeCases:
    @pytest.fixture(scope="class")
    def offline_data(self, client):
        """Create a mesh with an offline node (last_seen > 30 min ago)."""
        email = f"offline-{uuid.uuid4().hex[:8]}@test.com"
        r = client.post(
            "/api/v1/maas/auth/register",
            json={"email": email, "password": "password123"},
        )
        token = r.json()["access_token"]

        db = TestingSessionLocal()
        user = db.query(User).filter(User.api_key == token).first()
        user_id = user.id

        mesh_id = f"mesh-off-{uuid.uuid4().hex[:6]}"
        db.add(MeshInstance(
            id=mesh_id,
            name="Offline Test Mesh",
            owner_id=user_id,
            status="active",
            pqc_enabled=False,
        ))
        # Node that was last seen > 30 min ago → "offline"
        db.add(MeshNode(
            id=f"nd-off-{uuid.uuid4().hex[:6]}",
            mesh_id=mesh_id,
            status="approved",
            device_class="edge",
            hardware_id=None,
            enclave_enabled=False,
            last_seen=datetime.utcnow() - timedelta(minutes=45),
        ))
        db.commit()
        db.close()

        return {"token": token, "mesh_id": mesh_id}

    def test_offline_node_health_in_summary(self, client, offline_data):
        """Node last_seen 45 min ago → health 'offline' counted in summary."""
        r = client.get(
            "/api/v1/maas/dashboard/summary",
            headers={"X-API-Key": offline_data["token"]},
        )
        assert r.status_code == 200, r.text
        health = r.json()["stats"]["node_health"]
        assert health.get("offline", 0) >= 1

    def test_offline_node_health_in_node_detail(self, client, offline_data):
        """Node detail endpoint also shows 'offline' for the stale node."""
        r = client.get(
            f"/api/v1/maas/dashboard/nodes/{offline_data['mesh_id']}",
            headers={"X-API-Key": offline_data["token"]},
        )
        assert r.status_code == 200, r.text
        health_values = {n["health"] for n in r.json()["nodes"]}
        assert "offline" in health_values

    def test_admin_sees_all_audit_logs(self, client):
        """Admin role bypasses user_id filter for audit logs (line 98-99)."""
        # Create and promote an admin
        email = f"adm-dash-{uuid.uuid4().hex[:8]}@test.com"
        r = client.post(
            "/api/v1/maas/auth/register",
            json={"email": email, "password": "password123"},
        )
        admin_token = r.json()["access_token"]

        db = TestingSessionLocal()
        u = db.query(User).filter(User.api_key == admin_token).first()
        u.role = "admin"
        db.commit()
        db.close()

        r = client.get(
            "/api/v1/maas/dashboard/summary",
            headers={"X-API-Key": admin_token},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        # Admin gets recent_audit without user_id filter — list present
        assert "recent_audit" in data
        assert isinstance(data["recent_audit"], list)

# ---------------------------------------------------------------------------
# Unit-style tests for _node_attestation_type and _node_health
# ---------------------------------------------------------------------------

class TestDashboardUtilityFunctions:
    """Direct tests for _node_attestation_type and _node_health helpers."""

    def test_attestation_hardware_rooted_when_hardware_id_and_enclave(self):
        """hardware_id set AND enclave_enabled=True → HARDWARE_ROOTED."""
        from src.api.maas_dashboard import _node_attestation_type
        from src.database import MeshNode
        node = MeshNode(hardware_id="tpm-abc123", enclave_enabled=True)
        assert _node_attestation_type(node) == "HARDWARE_ROOTED"

    def test_attestation_software_only_when_no_hardware_id(self):
        """hardware_id is None → SOFTWARE_ONLY."""
        from src.api.maas_dashboard import _node_attestation_type
        from src.database import MeshNode
        node = MeshNode(hardware_id=None, enclave_enabled=True)
        assert _node_attestation_type(node) == "SOFTWARE_ONLY"

    def test_attestation_software_only_when_enclave_disabled(self):
        """hardware_id set but enclave_enabled=False → SOFTWARE_ONLY."""
        from src.api.maas_dashboard import _node_attestation_type
        from src.database import MeshNode
        node = MeshNode(hardware_id="tpm-xyz", enclave_enabled=False)
        assert _node_attestation_type(node) == "SOFTWARE_ONLY"

    def test_attestation_software_only_when_neither_set(self):
        """Both hardware_id=None and enclave_enabled=None → SOFTWARE_ONLY."""
        from src.api.maas_dashboard import _node_attestation_type
        from src.database import MeshNode
        node = MeshNode(hardware_id=None, enclave_enabled=None)
        assert _node_attestation_type(node) == "SOFTWARE_ONLY"

    def test_node_health_returns_unknown_when_no_last_seen(self):
        """Node with no last_seen → 'unknown'."""
        from src.api.maas_dashboard import _node_health
        from src.database import MeshNode
        node = MeshNode(last_seen=None)
        assert _node_health(node) == "unknown"

    def test_node_health_healthy_when_recently_seen(self):
        """Node seen within 5 min → 'healthy'."""
        from datetime import datetime, timedelta
        from src.api.maas_dashboard import _node_health
        from src.database import MeshNode
        node = MeshNode(last_seen=datetime.utcnow() - timedelta(minutes=1))
        assert _node_health(node) == "healthy"

    def test_node_health_stale_when_seen_10_minutes_ago(self):
        """Node seen 10 min ago (> 5 min stale threshold, ≤ 30 min) → 'stale'."""
        from datetime import datetime, timedelta
        from src.api.maas_dashboard import _node_health
        from src.database import MeshNode
        node = MeshNode(last_seen=datetime.utcnow() - timedelta(minutes=10))
        assert _node_health(node) == "stale"

    def test_node_health_offline_when_seen_over_30_minutes_ago(self):
        """Node seen > 30 min ago → 'offline'."""
        from datetime import datetime, timedelta
        from src.api.maas_dashboard import _node_health
        from src.database import MeshNode
        node = MeshNode(last_seen=datetime.utcnow() - timedelta(minutes=60))
        assert _node_health(node) == "offline"

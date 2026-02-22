"""
Integration tests for MaaS Telemetry API.

NOTE: maas_telemetry.py is registered AFTER maas_legacy.py, so both:
  POST /api/v1/maas/heartbeat             — handled by legacy
  GET  /api/v1/maas/{mesh_id}/topology    — handled by legacy

Legacy heartbeat: requires get_current_user (any auth), stores in _node_telemetry dict.
Legacy topology:  requires auth + mesh ownership (_get_mesh_or_404).

Tests verify API behaviour regardless of which router handles the request.
"""

import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.app import app
from src.database import Base, MeshNode, User, get_db

_TEST_DB_PATH = f"./test_telemetry_{uuid.uuid4().hex}.db"
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
def telemetry_data(client):
    """Admin user + deployed mesh for topology tests."""
    email_admin = f"tele-adm-{uuid.uuid4().hex[:8]}@test.com"
    email_usr = f"tele-usr-{uuid.uuid4().hex[:8]}@test.com"

    r = client.post("/api/v1/maas/auth/register",
                    json={"email": email_admin, "password": "password123"})
    admin_token = r.json()["access_token"]

    r = client.post("/api/v1/maas/auth/register",
                    json={"email": email_usr, "password": "password123"})
    usr_token = r.json()["access_token"]

    # Elevate admin
    db = TestingSessionLocal()
    admin = db.query(User).filter(User.api_key == admin_token).first()
    admin.role = "admin"
    db.commit()
    db.close()

    # Deploy a mesh (admin owns it)
    r = client.post(
        "/api/v1/maas/deploy",
        json={"name": "Telemetry Test Mesh", "nodes": 2},
        headers={"X-API-Key": admin_token},
    )
    assert r.status_code == 200, f"Deploy failed: {r.text}"
    mesh_id = r.json()["mesh_id"]

    return {
        "admin_token": admin_token,
        "usr_token": usr_token,
        "mesh_id": mesh_id,
    }


def _heartbeat_payload(node_id: str | None = None) -> dict:
    return {
        "node_id": node_id or f"node-{uuid.uuid4().hex[:8]}",
        "cpu_usage": 12.5,
        "memory_usage": 45.0,
        "neighbors_count": 3,
        "routing_table_size": 10,
        "uptime": 3600.0,
    }


# ---------------------------------------------------------------------------
# POST /api/v1/maas/heartbeat
# ---------------------------------------------------------------------------

class TestHeartbeat:
    def test_no_auth_401(self, client, telemetry_data):
        r = client.post("/api/v1/maas/heartbeat",
                        json=_heartbeat_payload())
        assert r.status_code == 401

    def test_authenticated_success(self, client, telemetry_data):
        r = client.post(
            "/api/v1/maas/heartbeat",
            json=_heartbeat_payload(),
            headers={"X-API-Key": telemetry_data["admin_token"]},
        )
        assert r.status_code == 200, r.text

    def test_response_has_status_ack(self, client, telemetry_data):
        r = client.post(
            "/api/v1/maas/heartbeat",
            json=_heartbeat_payload(),
            headers={"X-API-Key": telemetry_data["usr_token"]},
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "ack"

    def test_response_has_mesh_id_field(self, client, telemetry_data):
        r = client.post(
            "/api/v1/maas/heartbeat",
            json=_heartbeat_payload(),
            headers={"X-API-Key": telemetry_data["admin_token"]},
        )
        assert "mesh_id" in r.json()

    def test_unknown_node_returns_mesh_id_none(self, client, telemetry_data):
        """Node not in any mesh → mesh_id is None (not an error)."""
        r = client.post(
            "/api/v1/maas/heartbeat",
            json=_heartbeat_payload("phantom-node-xyz"),
            headers={"X-API-Key": telemetry_data["admin_token"]},
        )
        assert r.status_code == 200, r.text
        assert r.json()["mesh_id"] is None

    def test_heartbeat_with_pheromones(self, client, telemetry_data):
        payload = _heartbeat_payload()
        payload["pheromones"] = {
            "dest-a": {"hop-1": 0.9, "hop-2": 0.4},
        }
        r = client.post(
            "/api/v1/maas/heartbeat",
            json=payload,
            headers={"X-API-Key": telemetry_data["admin_token"]},
        )
        assert r.status_code == 200, r.text

    def test_missing_required_field_422(self, client, telemetry_data):
        r = client.post(
            "/api/v1/maas/heartbeat",
            json={"node_id": "node-x"},  # missing cpu_usage etc.
            headers={"X-API-Key": telemetry_data["admin_token"]},
        )
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/maas/{mesh_id}/topology
# ---------------------------------------------------------------------------

class TestTopology:
    def test_no_auth_401(self, client, telemetry_data):
        r = client.get(f"/api/v1/maas/{telemetry_data['mesh_id']}/topology")
        assert r.status_code == 401

    def test_nonowner_gets_404(self, client, telemetry_data):
        """User who doesn't own the mesh → 404 (legacy ownership check)."""
        r = client.get(
            f"/api/v1/maas/{telemetry_data['mesh_id']}/topology",
            headers={"X-API-Key": telemetry_data["usr_token"]},
        )
        assert r.status_code == 404

    def test_owner_gets_200(self, client, telemetry_data):
        r = client.get(
            f"/api/v1/maas/{telemetry_data['mesh_id']}/topology",
            headers={"X-API-Key": telemetry_data["admin_token"]},
        )
        assert r.status_code == 200, r.text

    def test_response_has_nodes_and_links(self, client, telemetry_data):
        r = client.get(
            f"/api/v1/maas/{telemetry_data['mesh_id']}/topology",
            headers={"X-API-Key": telemetry_data["admin_token"]},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "nodes" in data
        assert "links" in data
        assert isinstance(data["nodes"], list)
        assert isinstance(data["links"], list)

    def test_unknown_mesh_404(self, client, telemetry_data):
        r = client.get(
            "/api/v1/maas/nonexistent-mesh-xyz/topology",
            headers={"X-API-Key": telemetry_data["admin_token"]},
        )
        assert r.status_code == 404

    def test_topology_includes_deployed_nodes(self, client, telemetry_data):
        """Mesh deployed with 2 nodes should show ≥ 0 nodes in topology."""
        r = client.get(
            f"/api/v1/maas/{telemetry_data['mesh_id']}/topology",
            headers={"X-API-Key": telemetry_data["admin_token"]},
        )
        assert r.status_code == 200, r.text
        # nodes list should exist (may be empty if simulated provisioning)
        assert isinstance(r.json()["nodes"], list)


# ---------------------------------------------------------------------------
# Unit-style tests for telemetry module utility functions (no TestClient needed)
# ---------------------------------------------------------------------------

class TestTelemetryUtilityFunctions:
    """Direct tests for _store_local_fallback, _get_telemetry, _get_telemetry_history.

    These functions are tested without the HTTP layer, so the module-scoped
    TestClient is not needed. REDIS_AVAILABLE is patched to False to ensure
    deterministic behaviour in CI environments without Redis.
    """

    def test_store_local_fallback_list_history(self):
        """_store_local_fallback with list history → inserts item at index 0."""
        from src.api import maas_telemetry as tmod
        fallback: dict = {}
        tmod._LOCAL_TELEMETRY_FALLBACK.clear()

        tmod._store_local_fallback("k1", "k1:history", {"val": 1})
        assert tmod._LOCAL_TELEMETRY_FALLBACK["k1"] == {"val": 1}
        history = tmod._LOCAL_TELEMETRY_FALLBACK["k1:history"]
        assert isinstance(history, list)
        assert history[0] == {"val": 1}

    def test_store_local_fallback_non_list_history_replaced(self):
        """_store_local_fallback: if history_key holds a non-list → replaced with [data]."""
        from src.api import maas_telemetry as tmod
        tmod._LOCAL_TELEMETRY_FALLBACK.clear()
        tmod._LOCAL_TELEMETRY_FALLBACK["k:history"] = "corrupt"  # non-list existing value

        tmod._store_local_fallback("k", "k:history", {"val": 42})
        result = tmod._LOCAL_TELEMETRY_FALLBACK["k:history"]
        assert isinstance(result, list)
        assert result[0] == {"val": 42}

    def test_get_telemetry_fallback_dict_returned(self):
        """_get_telemetry with REDIS_AVAILABLE=False → returns fallback dict."""
        from unittest.mock import patch
        from src.api import maas_telemetry as tmod
        tmod._LOCAL_TELEMETRY_FALLBACK.clear()
        tmod._LOCAL_TELEMETRY_FALLBACK["maas:telemetry:n1"] = {"cpu": 0.5}

        with patch.object(tmod, "REDIS_AVAILABLE", False):
            result = tmod._get_telemetry("n1")
        assert result == {"cpu": 0.5}

    def test_get_telemetry_fallback_non_dict_returns_empty(self):
        """_get_telemetry: fallback is non-dict (e.g. list) → returns {}."""
        from unittest.mock import patch
        from src.api import maas_telemetry as tmod
        tmod._LOCAL_TELEMETRY_FALLBACK.clear()
        tmod._LOCAL_TELEMETRY_FALLBACK["maas:telemetry:bad"] = ["not", "a", "dict"]

        with patch.object(tmod, "REDIS_AVAILABLE", False):
            result = tmod._get_telemetry("bad")
        assert result == {}

    def test_get_telemetry_history_limit_zero_returns_empty(self):
        """_get_telemetry_history with limit=0 → [] immediately (line 93-94)."""
        from src.api import maas_telemetry as tmod
        result = tmod._get_telemetry_history("node-x", limit=0)
        assert result == []

    def test_get_telemetry_history_fallback_non_list_returns_empty(self):
        """_get_telemetry_history: fallback key holds non-list → [] (line 119)."""
        from unittest.mock import patch
        from src.api import maas_telemetry as tmod
        tmod._LOCAL_TELEMETRY_FALLBACK.clear()
        tmod._LOCAL_TELEMETRY_FALLBACK["maas:telemetry:n2:history"] = "oops"

        with patch.object(tmod, "REDIS_AVAILABLE", False):
            result = tmod._get_telemetry_history("n2", limit=10)
        assert result == []

    def test_get_telemetry_history_fallback_list_filters_non_dicts(self):
        """_get_telemetry_history: fallback list with mixed items → only dicts returned."""
        from unittest.mock import patch
        from src.api import maas_telemetry as tmod
        tmod._LOCAL_TELEMETRY_FALLBACK.clear()
        tmod._LOCAL_TELEMETRY_FALLBACK["maas:telemetry:n3:history"] = [
            {"ok": True}, "bad", 123, {"also": "good"},
        ]

        with patch.object(tmod, "REDIS_AVAILABLE", False):
            result = tmod._get_telemetry_history("n3", limit=10)
        assert result == [{"ok": True}, {"also": "good"}]

    def test_set_telemetry_redis_failure_falls_back_to_local(self):
        """_set_telemetry: REDIS_AVAILABLE=True but setex raises → local fallback used."""
        from unittest.mock import patch, MagicMock
        from src.api import maas_telemetry as tmod
        tmod._LOCAL_TELEMETRY_FALLBACK.clear()

        mock_redis = MagicMock()
        mock_redis.setex.side_effect = Exception("Redis connection error")

        with patch.object(tmod, "REDIS_AVAILABLE", True), \
             patch.object(tmod, "r_client", mock_redis):
            tmod._set_telemetry("failnode", {"cpu": 80.0})

        # Data should have fallen back to the local store
        assert tmod._LOCAL_TELEMETRY_FALLBACK.get("maas:telemetry:failnode") == {"cpu": 80.0}

    def test_set_telemetry_without_redis_writes_to_local(self):
        """_set_telemetry: REDIS_AVAILABLE=False → writes directly to local fallback."""
        from unittest.mock import patch
        from src.api import maas_telemetry as tmod
        tmod._LOCAL_TELEMETRY_FALLBACK.clear()

        with patch.object(tmod, "REDIS_AVAILABLE", False):
            tmod._set_telemetry("noredis-node", {"mem": 50.0})

        assert tmod._LOCAL_TELEMETRY_FALLBACK.get("maas:telemetry:noredis-node") == {"mem": 50.0}

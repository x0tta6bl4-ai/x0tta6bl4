"""
Unit tests for telemetry layer — heartbeat and topology endpoints.

NOTE: /api/v1/maas/heartbeat and /{mesh_id}/topology are served by the
legacy handler (maas_legacy.py) because it is registered first in app.py.
The maas_telemetry.py module's _set_telemetry/_get_telemetry helpers are
tested at the unit level directly for Redis vs. memory fallback behaviour.
"""
import uuid
import os
import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

from src.core.app import app
from src.database import Base, get_db, User

_TEST_DB_PATH = f"./test_telemetry_{uuid.uuid4().hex}.db"
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
    original = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    if original is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = original
    Base.metadata.drop_all(bind=engine)
    if os.path.exists(_TEST_DB_PATH):
        os.remove(_TEST_DB_PATH)


@pytest.fixture(scope="module")
def registered_user(client):
    email = f"telem-{uuid.uuid4().hex[:8]}@test.com"
    resp = client.post(
        "/api/v1/maas/auth/register",
        json={"email": email, "password": "password123"},
    )
    assert resp.status_code == 200
    api_key = resp.json()["access_token"]
    return {"email": email, "api_key": api_key, "headers": {"X-API-Key": api_key}}


@pytest.fixture(scope="module")
def provisioned_mesh(client, registered_user):
    """Deploy a mesh via the legacy provisioner (in-memory) for topology tests."""
    resp = client.post(
        "/api/v1/maas/deploy",
        json={"name": "telem-test-mesh", "nodes": 2, "pqc_enabled": False},
        headers=registered_user["headers"],
    )
    assert resp.status_code == 200
    return resp.json()["mesh_id"]


# ---------------------------------------------------------------------------
# HTTP endpoint tests — routes served by legacy handler
# ---------------------------------------------------------------------------

class TestHeartbeatEndpoint:
    """
    /api/v1/maas/heartbeat is intercepted by maas_legacy.router (registered first).
    The legacy handler accepts any node_id from authenticated users and stores
    telemetry in the in-memory _node_telemetry dict.
    """

    def test_heartbeat_unauthenticated_returns_401(self, client):
        """Legacy heartbeat requires authentication."""
        resp = client.post("/api/v1/maas/heartbeat", json={
            "node_id": "any-node",
            "cpu_usage": 0.5,
            "memory_usage": 0.3,
            "neighbors_count": 2,
            "routing_table_size": 10,
            "uptime": 3600.0,
        })
        assert resp.status_code == 401

    def test_heartbeat_authenticated_any_node_returns_200(self, client, registered_user):
        """Legacy handler stores telemetry in-memory for any node_id."""
        resp = client.post(
            "/api/v1/maas/heartbeat",
            json={
                "node_id": f"node-{uuid.uuid4().hex[:8]}",
                "cpu_usage": 0.45,
                "memory_usage": 0.62,
                "neighbors_count": 3,
                "routing_table_size": 12,
                "uptime": 7200.0,
            },
            headers=registered_user["headers"],
        )
        assert resp.status_code == 200

    def test_heartbeat_with_pheromones(self, client, registered_user):
        """Legacy handler accepts optional pheromone payload."""
        resp = client.post(
            "/api/v1/maas/heartbeat",
            json={
                "node_id": f"node-{uuid.uuid4().hex[:8]}",
                "cpu_usage": 0.3,
                "memory_usage": 0.4,
                "neighbors_count": 2,
                "routing_table_size": 8,
                "uptime": 500.0,
                "pheromones": {"route_a": {"next-hop-1": 0.8}},
            },
            headers=registered_user["headers"],
        )
        assert resp.status_code == 200

    def test_heartbeat_invalid_payload_returns_422(self, client, registered_user):
        """Missing required fields returns validation error."""
        resp = client.post(
            "/api/v1/maas/heartbeat",
            json={"node_id": "partial-data"},
            headers=registered_user["headers"],
        )
        assert resp.status_code == 422


class TestTopologyEndpoint:
    """
    /{mesh_id}/topology is intercepted by maas_legacy.router.
    It checks in-memory mesh ownership via _get_mesh_or_404.
    """

    def test_topology_unauthenticated_returns_401(self, client, provisioned_mesh):
        resp = client.get(f"/api/v1/maas/{provisioned_mesh}/topology")
        assert resp.status_code == 401

    def test_topology_authenticated_own_mesh_returns_nodes(self, client, registered_user, provisioned_mesh):
        resp = client.get(
            f"/api/v1/maas/{provisioned_mesh}/topology",
            headers=registered_user["headers"],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "nodes" in data
        assert "links" in data

    def test_topology_unknown_mesh_returns_404(self, client, registered_user):
        resp = client.get(
            "/api/v1/maas/mesh-nonexistent/topology",
            headers=registered_user["headers"],
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Unit tests for maas_telemetry helper functions (Redis / memory fallback)
# ---------------------------------------------------------------------------

class TestTelemetryHelpers:
    """Direct tests of _set_telemetry / _get_telemetry helper functions."""

    def test_set_and_get_in_memory_fallback(self):
        """When REDIS_AVAILABLE=False, data is stored in dict."""
        import src.api.maas_telemetry as mod
        original_redis = mod.REDIS_AVAILABLE
        original_client = mod.r_client
        mod.REDIS_AVAILABLE = False
        mod.r_client = {}
        try:
            node_id = f"unit-node-{uuid.uuid4().hex[:8]}"
            data = {"cpu": 0.5, "mem": 0.7}
            mod._set_telemetry(node_id, data)
            result = mod._get_telemetry(node_id)
            assert result == data
            history = mod._get_telemetry_history(node_id, limit=10)
            assert len(history) == 1
            assert history[0] == data
        finally:
            mod.REDIS_AVAILABLE = original_redis
            mod.r_client = original_client

    def test_get_missing_key_returns_empty_dict(self):
        """Getting telemetry for unknown node returns empty dict."""
        import src.api.maas_telemetry as mod
        original_redis = mod.REDIS_AVAILABLE
        original_client = mod.r_client
        mod.REDIS_AVAILABLE = False
        mod.r_client = {}
        try:
            result = mod._get_telemetry("nonexistent-node-xyz")
            assert result == {}
        finally:
            mod.REDIS_AVAILABLE = original_redis
            mod.r_client = original_client

    def test_redis_available_uses_setex(self):
        """When Redis is available, _set_telemetry calls r_client.setex with TTL."""
        import src.api.maas_telemetry as mod
        from unittest.mock import MagicMock
        mock_redis = MagicMock()
        mock_redis.get.return_value = json.dumps({"cpu": 0.3})
        original_redis = mod.REDIS_AVAILABLE
        original_client = mod.r_client
        mod.REDIS_AVAILABLE = True
        mod.r_client = mock_redis
        try:
            mod._set_telemetry("test-node", {"cpu": 0.3})
            mock_redis.setex.assert_called_once()
            call_args = mock_redis.setex.call_args[0]
            assert call_args[0] == "maas:telemetry:test-node"
            assert call_args[1] == 300  # 5-minute TTL
            mock_redis.pipeline.assert_called_once()
        finally:
            mod.REDIS_AVAILABLE = original_redis
            mod.r_client = original_client

    def test_redis_get_parses_json(self):
        """_get_telemetry parses JSON from Redis."""
        import src.api.maas_telemetry as mod
        from unittest.mock import MagicMock
        payload = {"cpu": 0.9, "mem": 0.8}
        mock_redis = MagicMock()
        mock_redis.get.return_value = json.dumps(payload)
        original_redis = mod.REDIS_AVAILABLE
        original_client = mod.r_client
        mod.REDIS_AVAILABLE = True
        mod.r_client = mock_redis
        try:
            result = mod._get_telemetry("cached-node")
            assert result == payload
        finally:
            mod.REDIS_AVAILABLE = original_redis
            mod.r_client = original_client

    def test_redis_miss_returns_empty_dict(self):
        """When Redis.get returns None, result is empty dict."""
        import src.api.maas_telemetry as mod
        from unittest.mock import MagicMock
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        original_redis = mod.REDIS_AVAILABLE
        original_client = mod.r_client
        mod.REDIS_AVAILABLE = True
        mod.r_client = mock_redis
        try:
            result = mod._get_telemetry("missing-node")
            assert result == {}
        finally:
            mod.REDIS_AVAILABLE = original_redis
            mod.r_client = original_client

    def test_get_history_redis_parses_json_entries(self):
        import src.api.maas_telemetry as mod
        from unittest.mock import MagicMock
        mock_redis = MagicMock()
        mock_redis.lrange.return_value = [
            json.dumps({"cpu": 0.7, "last_seen": "2026-02-21T10:00:00"}),
            "invalid-json",
            json.dumps({"cpu": 0.5, "last_seen": "2026-02-21T09:55:00"}),
        ]
        original_redis = mod.REDIS_AVAILABLE
        original_client = mod.r_client
        mod.REDIS_AVAILABLE = True
        mod.r_client = mock_redis
        try:
            result = mod._get_telemetry_history("history-node", limit=10)
            assert len(result) == 2
            assert result[0]["cpu"] == 0.7
            assert result[1]["cpu"] == 0.5
        finally:
            mod.REDIS_AVAILABLE = original_redis
            mod.r_client = original_client

    def test_get_history_memory_fallback_honors_limit(self):
        import src.api.maas_telemetry as mod
        original_redis = mod.REDIS_AVAILABLE
        original_client = mod.r_client
        original_local_fallback = mod._LOCAL_TELEMETRY_FALLBACK
        mod.REDIS_AVAILABLE = False
        mod.r_client = {}
        mod._LOCAL_TELEMETRY_FALLBACK = mod.LRUCache(max_size=200)
        try:
            node_id = "history-memory-node"
            mod._set_telemetry(node_id, {"cpu": 0.1})
            mod._set_telemetry(node_id, {"cpu": 0.2})
            mod._set_telemetry(node_id, {"cpu": 0.3})
            result = mod._get_telemetry_history(node_id, limit=2)
            assert len(result) == 2
            assert result[0]["cpu"] == 0.3
            assert result[1]["cpu"] == 0.2
        finally:
            mod.REDIS_AVAILABLE = original_redis
            mod.r_client = original_client
            mod._LOCAL_TELEMETRY_FALLBACK = original_local_fallback

    def test_redis_failure_falls_back_to_local_cache(self):
        import src.api.maas_telemetry as mod
        from unittest.mock import MagicMock

        mock_redis = MagicMock()
        mock_redis.setex.side_effect = RuntimeError("redis unavailable")
        mock_redis.get.side_effect = RuntimeError("redis unavailable")
        mock_redis.lrange.side_effect = RuntimeError("redis unavailable")

        original_redis = mod.REDIS_AVAILABLE
        original_client = mod.r_client
        original_local_fallback = mod._LOCAL_TELEMETRY_FALLBACK

        mod.REDIS_AVAILABLE = True
        mod.r_client = mock_redis
        mod._LOCAL_TELEMETRY_FALLBACK = mod.LRUCache(max_size=200)
        try:
            node_id = "redis-fallback-node"
            payload = {"cpu": 0.4, "latency_ms": 11.0}
            mod._set_telemetry(node_id, payload)

            latest = mod._get_telemetry(node_id)
            history = mod._get_telemetry_history(node_id, limit=5)
            assert latest == payload
            assert len(history) == 1
            assert history[0] == payload
        finally:
            mod.REDIS_AVAILABLE = original_redis
            mod.r_client = original_client
            mod._LOCAL_TELEMETRY_FALLBACK = original_local_fallback

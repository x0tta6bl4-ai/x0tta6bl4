"""
Unit tests for telemetry layer — heartbeat and topology endpoints.

NOTE: /api/v1/maas/heartbeat is served by the legacy handler because it is
registered first in app.py. /{mesh_id}/topology is served by maas_telemetry
and verifies mesh ownership before reading telemetry snapshots. The helper
paths are tested directly for Redis vs. memory fallback behaviour.
"""
import uuid
import os
import json
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

from src.coordination.events import EventBus, EventType
from src.core.app import app
from src.database import Base, MeshInstance as DBMeshInstance, MeshNode, get_db

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
    assert resp.status_code in {200, 201}
    return resp.json()["mesh_id"]


# ---------------------------------------------------------------------------
# HTTP endpoint tests — routes served by legacy handler
# ---------------------------------------------------------------------------

class TestHeartbeatEndpoint:
    """
    /api/v1/maas/heartbeat is intercepted by maas_legacy.router (registered first).
    The legacy handler only accepts nodes already present in the mesh registry.
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

    def test_heartbeat_authenticated_registered_node_returns_200(
        self,
        client,
        registered_user,
        provisioned_mesh,
    ):
        """Legacy handler stores telemetry only for known mesh nodes."""
        resp = client.post(
            "/api/v1/maas/heartbeat",
            json={
                "node_id": f"{provisioned_mesh}-node-0",
                "cpu_usage": 0.45,
                "memory_usage": 0.62,
                "neighbors_count": 3,
                "routing_table_size": 12,
                "uptime": 7200.0,
            },
            headers=registered_user["headers"],
        )
        assert resp.status_code == 200

    def test_heartbeat_with_pheromones(self, client, registered_user, provisioned_mesh):
        """Legacy handler accepts optional pheromone payload."""
        resp = client.post(
            "/api/v1/maas/heartbeat",
            json={
                "node_id": f"{provisioned_mesh}-node-1",
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
    /{mesh_id}/topology is served by maas_telemetry and checks mesh ownership
    before reading telemetry snapshots.
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


class TestLRUCache:
    """Unit tests for the LRUCache class used as telemetry fallback."""

    def _make(self, max_size=5):
        import src.api.maas_telemetry as mod
        return mod.LRUCache(max_size=max_size)

    def test_set_and_get_basic(self):
        c = self._make()
        c.set("k1", {"v": 1})
        assert c.get("k1") == {"v": 1}

    def test_get_missing_returns_none(self):
        c = self._make()
        assert c.get("nonexistent") is None

    def test_update_existing_key(self):
        c = self._make()
        c.set("k", "first")
        c.set("k", "second")
        assert c.get("k") == "second"
        assert len(c) == 1

    def test_lru_eviction_removes_oldest(self):
        c = self._make(max_size=3)
        c.set("a", 1)
        c.set("b", 2)
        c.set("c", 3)
        c.get("a")  # access "a" — now b is LRU
        c.set("d", 4)  # evicts "b"
        assert c.get("b") is None
        assert c.get("a") == 1
        assert c.get("c") == 3
        assert c.get("d") == 4

    def test_delete_existing_key(self):
        c = self._make()
        c.set("x", 99)
        assert c.delete("x") is True
        assert c.get("x") is None

    def test_delete_missing_key_returns_false(self):
        c = self._make()
        assert c.delete("no_such_key") is False

    def test_keys_returns_all_keys(self):
        c = self._make()
        c.set("k1", 1)
        c.set("k2", 2)
        keys = c.keys()
        assert set(keys) == {"k1", "k2"}

    def test_len_empty(self):
        c = self._make()
        assert len(c) == 0

    def test_len_after_sets(self):
        c = self._make()
        c.set("a", 1)
        c.set("b", 2)
        assert len(c) == 2

    def test_get_stats_initial(self):
        c = self._make()
        stats = c.get_stats()
        assert stats["size"] == 0
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["hit_rate"] == 0.0
        assert stats["evictions"] == 0

    def test_get_stats_tracks_hits_misses_evictions(self):
        c = self._make(max_size=2)
        c.set("a", 1)
        c.set("b", 2)
        c.get("a")    # hit
        c.get("z")    # miss
        c.set("c", 3) # evicts "b"
        stats = c.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["evictions"] == 1
        assert stats["hit_rate"] == pytest.approx(0.5)

    def test_get_fallback_cache_stats_function(self):
        import src.api.maas_telemetry as mod
        stats = mod.get_fallback_cache_stats()
        assert "size" in stats
        assert "max_size" in stats
        assert "hit_rate" in stats

    def test_store_local_fallback_corrupted_history_reset(self):
        """When history entry is not a list it is reset to a fresh list."""
        import src.api.maas_telemetry as mod
        original = mod._LOCAL_TELEMETRY_FALLBACK
        cache = mod.LRUCache(max_size=200)
        history_key = "maas:telemetry:corrupt-node:history"
        cache.set(history_key, {"bad": "data"})  # non-list — corrupted
        mod._LOCAL_TELEMETRY_FALLBACK = cache
        try:
            mod._store_local_fallback(
                "maas:telemetry:corrupt-node",
                history_key,
                {"cpu": 0.9},
            )
            history = cache.get(history_key)
            assert isinstance(history, list)
            assert len(history) == 1
            assert history[0]["cpu"] == 0.9
        finally:
            mod._LOCAL_TELEMETRY_FALLBACK = original


class TestTelemetryDegradedDependencyMarkers:
    def test_set_telemetry_marks_redis_degraded_when_redis_disabled(self):
        import src.api.maas_telemetry as mod

        original_redis = mod.REDIS_AVAILABLE
        try:
            mod.REDIS_AVAILABLE = False
            degraded = set()
            mod._set_telemetry("node-degraded-1", {"cpu": 0.2}, degraded_dependencies=degraded)
            assert "redis" in degraded
        finally:
            mod.REDIS_AVAILABLE = original_redis

    def test_get_telemetry_marks_redis_degraded_when_redis_read_fails(self):
        import src.api.maas_telemetry as mod
        from unittest.mock import MagicMock

        original_redis = mod.REDIS_AVAILABLE
        original_client = mod.r_client
        original_fallback = mod._LOCAL_TELEMETRY_FALLBACK
        mod._LOCAL_TELEMETRY_FALLBACK = mod.LRUCache(max_size=32)
        mod._LOCAL_TELEMETRY_FALLBACK.set("maas:telemetry:node-degraded-2", {"cpu": 0.3})
        try:
            mod.REDIS_AVAILABLE = True
            mock_redis = MagicMock()
            mock_redis.get.side_effect = RuntimeError("redis read failed")
            mod.r_client = mock_redis

            degraded = set()
            result = mod._get_telemetry("node-degraded-2", degraded_dependencies=degraded)

            assert result == {"cpu": 0.3}
            assert "redis" in degraded
        finally:
            mod.REDIS_AVAILABLE = original_redis
            mod.r_client = original_client
            mod._LOCAL_TELEMETRY_FALLBACK = original_fallback


class TestTelemetryPheromoneContract:
    def test_extract_pheromone_score_supports_numeric_and_structured_payloads(self):
        import src.api.maas_telemetry as mod

        assert mod._extract_pheromone_score(0.9) == pytest.approx(0.9)
        assert mod._extract_pheromone_score({"score": 0.7}) == pytest.approx(0.7)
        assert mod._extract_pheromone_score({"weight": 0.4}) == pytest.approx(0.4)
        assert mod._extract_pheromone_score({"unknown": "shape"}) == 0.0

    def test_derive_topology_status_preserves_degraded_and_offline_semantics(self):
        import src.api.maas_telemetry as mod

        assert mod._derive_topology_status({"status": "degraded"}, "approved") == "degraded"
        assert mod._derive_topology_status({"status": "unhealthy"}, "approved") == "degraded"
        assert mod._derive_topology_status({"cpu": 0.2}, "approved") == "healthy"
        assert mod._derive_topology_status({}, "approved") == "offline"
        assert mod._derive_topology_status(None, "approved") == "offline"

    @pytest.mark.asyncio
    async def test_heartbeat_persists_pheromones_and_topology_uses_numeric_weights(
        self,
        monkeypatch,
        tmp_path,
    ):
        import src.api.maas_telemetry as mod

        local_db_path = f"./test_telemetry_direct_{uuid.uuid4().hex}.db"
        local_engine = create_engine(f"sqlite:///{local_db_path}", connect_args={"check_same_thread": False})
        LocalSession = sessionmaker(autocommit=False, autoflush=False, bind=local_engine)

        original_redis = mod.REDIS_AVAILABLE
        original_client = mod.r_client
        original_fallback = mod._LOCAL_TELEMETRY_FALLBACK

        class _ReputationStub:
            async def record_proxy_result(self, **_kwargs):
                return None

            def get_proxy_trust(self, _node_id):
                return None

        mod.REDIS_AVAILABLE = False
        mod.r_client = None
        mod._LOCAL_TELEMETRY_FALLBACK = mod.LRUCache(max_size=64)
        monkeypatch.setattr(mod, "reputation_system", _ReputationStub())
        monkeypatch.setattr(mod, "_record_heartbeat_metric", lambda _node_id: None)
        monkeypatch.setattr(mod.uptime_tracker, "record_heartbeat", lambda _node_id: None)

        Base.metadata.create_all(bind=local_engine)
        db = LocalSession()
        try:
            db.add_all([
                DBMeshInstance(id="mesh-direct", name="mesh-direct", owner_id="owner-1"),
                MeshNode(id="node-a", mesh_id="mesh-direct", device_class="edge", status="healthy"),
                MeshNode(id="node-b", mesh_id="mesh-direct", device_class="edge", status="healthy"),
            ])
            db.commit()

            bus = EventBus(project_root=str(tmp_path))
            heartbeat_request = SimpleNamespace(
                state=SimpleNamespace(
                    event_bus=bus,
                    event_project_root=str(tmp_path),
                ),
                client=SimpleNamespace(host="198.51.100.10"),
            )
            await mod.heartbeat(
                mod.NodeHeartbeatRequest(
                    node_id="node-a",
                    cpu_usage=0.5,
                    memory_usage=0.3,
                    neighbors_count=1,
                    routing_table_size=8,
                    uptime=120.0,
                    latency_ms=12.0,
                    pheromones={"dest-b": {"node-b": 0.91}},
                ),
                request=heartbeat_request,
                db=db,
                current_user=SimpleNamespace(id="owner-1"),
            )

            telemetry = mod._get_telemetry("node-a")
            assert telemetry["status"] == "healthy"
            assert telemetry["pheromones"] == {"dest-b": {"node-b": 0.91}}
            assert telemetry["latency"] == 12.0
            assert "redis" in heartbeat_request.state.degraded_dependencies
            events = bus.get_event_history(
                event_type=EventType.PIPELINE_STAGE_END,
                source_agent="maas-telemetry",
            )
            heartbeat_events = [
                event.data for event in events if event.data["operation"] == "heartbeat"
            ]
            assert len(heartbeat_events) == 1
            heartbeat_payload = heartbeat_events[0]
            assert heartbeat_payload["stage"] == "heartbeat_processed"
            assert heartbeat_payload["status"] == "accepted"
            assert heartbeat_payload["read_only"] is False
            assert heartbeat_payload["heartbeat_summary"]["db_node_found"] is True
            assert heartbeat_payload["heartbeat_summary"]["db_committed"] is True
            assert heartbeat_payload["heartbeat_summary"]["client_ip_hash"] == (
                mod._redacted_sha256_prefix("198.51.100.10")
            )
            assert heartbeat_payload["heartbeat_summary"]["has_pheromones"] is True
            assert (
                heartbeat_payload["heartbeat_summary"]["pheromone_destination_count"]
                == 1
            )
            assert (
                heartbeat_payload["heartbeat_summary"]["heartbeat_metric_recorded"]
                is True
            )
            assert heartbeat_payload["trust_summary"] == {
                "reputation_update_attempted": True,
                "reputation_update_success": True,
                "trust_score_after": 0.5,
                "trust_source": "default",
            }
            assert (
                heartbeat_payload["settlement_summary"]["uptime_sample_attempted"]
                is True
            )
            assert (
                heartbeat_payload["settlement_summary"]["settlement_decision_made"]
                is False
            )
            assert heartbeat_payload["upstream_events_total"] == 1
            evidence_text = json.dumps([event.data for event in events], sort_keys=True)
            raw_log = (
                tmp_path / ".agent_coordination" / "events.log"
            ).read_text(encoding="utf-8")
            for raw_value in (
                "node-a",
                "node-b",
                "mesh-direct",
                "198.51.100.10",
                "dest-b",
            ):
                assert raw_value not in evidence_text
                assert raw_value not in raw_log

            topology_request = SimpleNamespace(state=SimpleNamespace())
            topology = await mod.get_topology(
                "mesh-direct",
                request=topology_request,
                db=db,
                current_user=SimpleNamespace(id="owner-1"),
            )

            assert any(
                link["source"] == "node-a"
                and link["target"] == "node-b"
                and link["quality"] == pytest.approx(0.91)
                for link in topology["links"]
            )
            assert "redis" in topology_request.state.degraded_dependencies
        finally:
            db.close()
            Base.metadata.drop_all(bind=local_engine)
            if os.path.exists(local_db_path):
                os.remove(local_db_path)
            mod.REDIS_AVAILABLE = original_redis
            mod.r_client = original_client
            mod._LOCAL_TELEMETRY_FALLBACK = original_fallback

    @pytest.mark.asyncio
    async def test_topology_uses_degraded_status_from_existing_snapshot(self):
        import src.api.maas_telemetry as mod

        local_db_path = f"./test_telemetry_topology_{uuid.uuid4().hex}.db"
        local_engine = create_engine(f"sqlite:///{local_db_path}", connect_args={"check_same_thread": False})
        LocalSession = sessionmaker(autocommit=False, autoflush=False, bind=local_engine)

        original_redis = mod.REDIS_AVAILABLE
        original_client = mod.r_client
        original_fallback = mod._LOCAL_TELEMETRY_FALLBACK

        mod.REDIS_AVAILABLE = False
        mod.r_client = None
        mod._LOCAL_TELEMETRY_FALLBACK = mod.LRUCache(max_size=64)

        Base.metadata.create_all(bind=local_engine)
        db = LocalSession()
        try:
            db.add(DBMeshInstance(id="mesh-topology", name="mesh-topology", owner_id="owner-1"))
            db.add(MeshNode(id="node-degraded", mesh_id="mesh-topology", device_class="edge", status="degraded"))
            db.commit()

            mod._set_telemetry("node-degraded", {"status": "degraded", "latency_ms": 88.1})

            topology_request = SimpleNamespace(state=SimpleNamespace())
            topology = await mod.get_topology(
                "mesh-topology",
                request=topology_request,
                db=db,
                current_user=SimpleNamespace(id="owner-1"),
            )

            assert topology["nodes"][0]["id"] == "node-degraded"
            assert topology["nodes"][0]["status"] == "degraded"
            assert topology["nodes"][0]["telemetry"]["latency_ms"] == 88.1
            assert "redis" in topology_request.state.degraded_dependencies
        finally:
            db.close()
            Base.metadata.drop_all(bind=local_engine)
            if os.path.exists(local_db_path):
                os.remove(local_db_path)
            mod.REDIS_AVAILABLE = original_redis
            mod.r_client = original_client
            mod._LOCAL_TELEMETRY_FALLBACK = original_fallback

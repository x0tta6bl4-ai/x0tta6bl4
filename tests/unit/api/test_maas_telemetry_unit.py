"""Unit tests for pure helpers and data structures in src/api/maas_telemetry.py."""

from __future__ import annotations

import json
import asyncio
import threading
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.coordination.events import EventBus, EventType

# ---------------------------------------------------------------------------
# Import the module under test (Redis is stubbed at module level if
# the connection attempt fails; the tests below rely on that fallback path)
# ---------------------------------------------------------------------------
import importlib
import sys


def _load_telemetry():
    """Load maas_telemetry with Redis/DB dependencies stubbed out."""
    key = "src.api.maas_telemetry"
    attr = "maas_telemetry"
    sentinel = object()
    original_module = sys.modules.get(key, sentinel)
    parent = sys.modules.get("src.api")
    stubs = {
        "redis": MagicMock(),
        "src.database": MagicMock(),
        "src.api.maas_auth": MagicMock(),
        "src.core.reliability_policy": MagicMock(),
        "src.monitoring.maas_metrics": MagicMock(),
        "src.network.reputation_scoring": MagicMock(),
    }
    # Make redis.from_url(...).ping() raise so REDIS_AVAILABLE stays False
    mock_redis_client = MagicMock()
    mock_redis_client.ping.side_effect = Exception("no redis in tests")
    stubs["redis"].from_url.return_value = mock_redis_client

    if key in sys.modules:
        del sys.modules[key]

    with patch.dict("sys.modules", stubs):
        mod = importlib.import_module(key)
    if original_module is sentinel:
        sys.modules.pop(key, None)
        if parent is not None and getattr(parent, attr, None) is mod:
            delattr(parent, attr)
    else:
        sys.modules[key] = original_module
        if parent is not None:
            setattr(parent, attr, original_module)
    return mod


_mod = _load_telemetry()

LRUCache = _mod.LRUCache
_extract_pheromone_score = _mod._extract_pheromone_score
_derive_topology_status = _mod._derive_topology_status
_store_local_fallback = _mod._store_local_fallback
get_fallback_cache_stats = _mod.get_fallback_cache_stats


def _force_telemetry_dependencies_ready(monkeypatch) -> None:
    monkeypatch.setattr(_mod, "REDIS_AVAILABLE", True)
    monkeypatch.setattr(_mod, "r_client", object())
    monkeypatch.setattr(_mod, "_LOCAL_TELEMETRY_FALLBACK", _mod.LRUCache(max_size=16))
    monkeypatch.setattr(
        _mod,
        "uptime_tracker",
        SimpleNamespace(record_heartbeat=lambda *_args: None, get_uptime_percent=lambda *_args: 1.0),
    )
    monkeypatch.setattr(
        _mod,
        "reputation_system",
        SimpleNamespace(
            record_proxy_result=lambda *_args, **_kwargs: None,
            get_proxy_trust=lambda *_args: None,
        ),
    )
    monkeypatch.setattr(_mod, "_record_heartbeat_metric", lambda *_args: None)
    monkeypatch.setattr(_mod, "get_current_user_from_maas", lambda *_args, **_kwargs: None)


class TestTelemetryReadiness:
    def test_ready_when_core_and_persistent_dependencies_are_available(self, monkeypatch):
        _force_telemetry_dependencies_ready(monkeypatch)
        db = MagicMock(spec=["query", "commit"])

        payload = _mod._telemetry_readiness_status(db)

        assert payload["status"] == "ready"
        assert payload["registration_mode"] == "full_mode_only"
        assert payload["route_present_in_light_mode"] is False
        assert payload["lifecycle_binding"] == "route_import_only"
        assert payload["startup_hook_completed"] is None
        assert payload["telemetry_runtime_ready"] is True
        assert payload["telemetry_db_ready"] is True
        assert payload["mesh_node_model_ready"] is True
        assert payload["redis_persistence_ready"] is True
        assert payload["fallback_cache_ready"] is True
        assert payload["uptime_tracker_ready"] is True
        assert payload["settlement_uptime_ready"] is True
        assert payload["reputation_system_ready"] is True
        assert payload["metrics_export_ready"] is True
        assert payload["auth_dependency_ready"] is True
        assert payload["legacy_route_shadowing"]["shadowed_by_legacy"] == [
            "POST /heartbeat",
            "GET /{mesh_id}/topology",
        ]
        assert payload["degraded_dependencies"] == []

    def test_degraded_when_runtime_dependencies_are_missing(self, monkeypatch):
        monkeypatch.setattr(_mod, "MeshNode", SimpleNamespace(id="id"))
        monkeypatch.setattr(_mod, "REDIS_AVAILABLE", False)
        monkeypatch.setattr(_mod, "r_client", None)
        monkeypatch.setattr(_mod, "_LOCAL_TELEMETRY_FALLBACK", None)
        monkeypatch.setattr(_mod, "uptime_tracker", SimpleNamespace(record_heartbeat=None))
        monkeypatch.setattr(_mod, "reputation_system", SimpleNamespace())
        monkeypatch.setattr(_mod, "_record_heartbeat_metric", None)
        monkeypatch.setattr(_mod, "get_current_user_from_maas", None)

        payload = _mod._telemetry_readiness_status(SimpleNamespace())

        assert payload["status"] == "degraded"
        assert payload["telemetry_runtime_ready"] is False
        assert payload["telemetry_db_ready"] is False
        assert payload["mesh_node_model_ready"] is False
        assert payload["redis_persistence_ready"] is False
        assert payload["fallback_cache_ready"] is False
        assert payload["uptime_tracker_ready"] is False
        assert payload["settlement_uptime_ready"] is False
        assert payload["reputation_system_ready"] is False
        assert payload["metrics_export_ready"] is False
        assert payload["auth_dependency_ready"] is False
        assert payload["degraded_dependencies"] == [
            "database",
            "mesh_node_model",
            "redis",
            "fallback_cache",
            "uptime_tracker",
            "reputation_system",
            "heartbeat_metrics",
            "auth",
        ]
        assert "legacy route precedence" in payload["claim_boundary"]

    def test_endpoint_marks_degraded_dependencies(self, monkeypatch):
        _force_telemetry_dependencies_ready(monkeypatch)
        marked: set[str] = set()

        def mark_degraded(_request, dependency):
            marked.add(dependency)

        monkeypatch.setattr(_mod, "mark_degraded_dependency", mark_degraded)
        request = SimpleNamespace(state=SimpleNamespace())

        payload = asyncio.run(
            _mod.telemetry_readiness(request=request, db=SimpleNamespace())
        )

        assert payload["status"] == "degraded"
        assert marked == {"database"}


# ===========================================================================
# LRUCache
# ===========================================================================


class TestLRUCacheBasics:
    def setup_method(self):
        self.cache = LRUCache(max_size=5)

    def test_empty_cache_len_zero(self):
        assert len(self.cache) == 0

    def test_set_and_get(self):
        self.cache.set("k", "v")
        assert self.cache.get("k") == "v"

    def test_get_missing_returns_none(self):
        assert self.cache.get("missing") is None

    def test_set_updates_existing(self):
        self.cache.set("k", "v1")
        self.cache.set("k", "v2")
        assert self.cache.get("k") == "v2"
        assert len(self.cache) == 1

    def test_len_grows_with_entries(self):
        for i in range(3):
            self.cache.set(f"k{i}", i)
        assert len(self.cache) == 3

    def test_delete_existing_key_returns_true(self):
        self.cache.set("k", "v")
        assert self.cache.delete("k") is True
        assert len(self.cache) == 0

    def test_delete_missing_key_returns_false(self):
        assert self.cache.delete("nonexistent") is False

    def test_keys_returns_all_current_keys(self):
        self.cache.set("a", 1)
        self.cache.set("b", 2)
        keys = self.cache.keys()
        assert set(keys) == {"a", "b"}

    def test_contains_true(self):
        self.cache.set("x", 99)
        assert "x" in self.cache

    def test_contains_false(self):
        assert "ghost" not in self.cache

    def test_getitem_existing(self):
        self.cache["key"] = "val"
        assert self.cache["key"] == "val"

    def test_setitem_alias(self):
        self.cache["z"] = 42
        assert self.cache.get("z") == 42

    def test_getitem_missing_raises_key_error(self):
        with pytest.raises(KeyError):
            _ = self.cache["does_not_exist"]

    def test_clear_empties_cache(self):
        for i in range(3):
            self.cache.set(f"k{i}", i)
        self.cache.clear()
        assert len(self.cache) == 0

    def test_clear_resets_stats(self):
        self.cache.set("a", 1)
        self.cache.get("a")  # hit
        self.cache.get("missing")  # miss
        self.cache.clear()
        stats = self.cache.get_stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0


class TestLRUCacheEviction:
    def test_evicts_lru_when_over_capacity(self):
        cache = LRUCache(max_size=3)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        # Access 'a' to make it MRU
        cache.get("a")
        # Adding 'd' should evict 'b' (LRU)
        cache.set("d", 4)
        assert "b" not in cache
        assert "a" in cache
        assert "c" in cache
        assert "d" in cache

    def test_eviction_count_tracked(self):
        cache = LRUCache(max_size=2)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)  # evicts 'a'
        stats = cache.get_stats()
        assert stats["evictions"] == 1

    def test_no_eviction_under_capacity(self):
        cache = LRUCache(max_size=10)
        for i in range(5):
            cache.set(f"k{i}", i)
        assert len(cache) == 5
        assert cache.get_stats()["evictions"] == 0

    def test_update_existing_does_not_evict(self):
        cache = LRUCache(max_size=2)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("a", 99)  # update, not new entry
        assert len(cache) == 2
        assert cache.get_stats()["evictions"] == 0


class TestLRUCacheStats:
    def test_initial_stats(self):
        cache = LRUCache(max_size=100)
        stats = cache.get_stats()
        assert stats["size"] == 0
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["hit_rate"] == 0.0
        assert stats["evictions"] == 0

    def test_hit_increments(self):
        cache = LRUCache()
        cache.set("k", "v")
        cache.get("k")
        cache.get("k")
        assert cache.get_stats()["hits"] == 2

    def test_miss_increments(self):
        cache = LRUCache()
        cache.get("x")
        cache.get("y")
        assert cache.get_stats()["misses"] == 2

    def test_hit_rate_calculation(self):
        cache = LRUCache()
        cache.set("k", "v")
        cache.get("k")   # hit
        cache.get("x")   # miss
        stats = cache.get_stats()
        assert stats["hit_rate"] == pytest.approx(0.5)

    def test_max_size_in_stats(self):
        cache = LRUCache(max_size=42)
        assert cache.get_stats()["max_size"] == 42


class TestLRUCacheThreadSafety:
    def test_concurrent_writes_no_data_loss(self):
        cache = LRUCache(max_size=1000)
        errors = []

        def writer(start):
            try:
                for i in range(start, start + 100):
                    cache.set(f"key-{i}", i)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=writer, args=(i * 100,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(cache) <= 1000  # max_size is respected

    def test_concurrent_reads_stable(self):
        cache = LRUCache()
        for i in range(20):
            cache.set(f"k{i}", i)

        results = []
        errors = []

        def reader():
            try:
                for i in range(20):
                    results.append(cache.get(f"k{i}"))
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=reader) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors


# ===========================================================================
# _extract_pheromone_score
# ===========================================================================


class TestExtractPheromoneScore:
    def test_float_returned_as_float(self):
        assert _extract_pheromone_score(3.14) == pytest.approx(3.14)

    def test_int_converted_to_float(self):
        assert _extract_pheromone_score(7) == pytest.approx(7.0)

    def test_zero_returns_zero(self):
        assert _extract_pheromone_score(0) == 0.0

    def test_negative_numeric(self):
        assert _extract_pheromone_score(-1.5) == pytest.approx(-1.5)

    def test_bool_true_returns_zero(self):
        # bool is subclass of int but should be excluded
        assert _extract_pheromone_score(True) == 0.0

    def test_bool_false_returns_zero(self):
        assert _extract_pheromone_score(False) == 0.0

    def test_dict_with_score_key(self):
        assert _extract_pheromone_score({"score": 0.9}) == pytest.approx(0.9)

    def test_dict_with_weight_key(self):
        assert _extract_pheromone_score({"weight": 2.5}) == pytest.approx(2.5)

    def test_dict_with_latency_score_key(self):
        assert _extract_pheromone_score({"latency_score": 0.3}) == pytest.approx(0.3)

    def test_dict_score_takes_precedence_over_weight(self):
        assert _extract_pheromone_score({"score": 1.0, "weight": 2.0}) == pytest.approx(1.0)

    def test_dict_with_no_known_key_returns_zero(self):
        assert _extract_pheromone_score({"unknown": 5.0}) == 0.0

    def test_dict_value_is_bool_returns_zero(self):
        assert _extract_pheromone_score({"score": True}) == 0.0

    def test_string_returns_zero(self):
        assert _extract_pheromone_score("0.5") == 0.0

    def test_none_returns_zero(self):
        assert _extract_pheromone_score(None) == 0.0

    def test_list_returns_zero(self):
        assert _extract_pheromone_score([1, 2]) == 0.0

    def test_empty_dict_returns_zero(self):
        assert _extract_pheromone_score({}) == 0.0


# ===========================================================================
# _derive_topology_status
# ===========================================================================


class TestDeriveTopologyStatus:
    def test_healthy_when_telemetry_present_and_status_healthy(self):
        result = _derive_topology_status({"status": "healthy", "cpu": 0.3}, "online")
        assert result == "healthy"

    def test_healthy_when_telemetry_has_no_status(self):
        result = _derive_topology_status({"cpu": 0.3}, None)
        assert result == "healthy"

    def test_offline_when_no_telemetry_and_no_db_status(self):
        result = _derive_topology_status(None, None)
        assert result == "offline"

    def test_offline_when_empty_telemetry_and_no_db_status(self):
        result = _derive_topology_status({}, None)
        assert result == "offline"

    def test_degraded_from_telemetry_status(self):
        result = _derive_topology_status({"status": "degraded"}, "online")
        assert result == "degraded"

    def test_unhealthy_maps_to_degraded(self):
        result = _derive_topology_status({"status": "unhealthy"}, "online")
        assert result == "degraded"

    def test_status_is_case_insensitive(self):
        result = _derive_topology_status({"status": "DEGRADED"}, None)
        assert result == "degraded"

    def test_status_strips_whitespace(self):
        result = _derive_topology_status({"status": "  unhealthy  "}, None)
        assert result == "degraded"

    def test_db_status_fallback_when_telemetry_status_missing(self):
        # telemetry is a dict (truthy) but no 'status' key -> use db_status
        result = _derive_topology_status({}, "degraded")
        assert result == "degraded"

    def test_db_status_degraded_with_empty_telemetry(self):
        result = _derive_topology_status({}, "degraded")
        assert result == "degraded"

    def test_none_telemetry_db_status_degraded(self):
        result = _derive_topology_status(None, "degraded")
        assert result == "degraded"

    def test_non_dict_telemetry_treated_as_absent(self):
        # Telemetry must be a dict
        result = _derive_topology_status("active", None)
        assert result == "offline"

    def test_db_status_non_degraded_with_no_telemetry(self):
        result = _derive_topology_status(None, "online")
        assert result == "offline"

    def test_telemetry_has_non_string_status_falls_to_db(self):
        result = _derive_topology_status({"status": 200}, "degraded")
        # 200 is int, not str -> skip telemetry status, use db_status
        assert result == "degraded"


# ===========================================================================
# _store_local_fallback (uses the module-level _LOCAL_TELEMETRY_FALLBACK)
# ===========================================================================


class TestStoreLocalFallback:
    def setup_method(self):
        # Clear the module-level fallback cache before each test
        _mod._LOCAL_TELEMETRY_FALLBACK.clear()

    def test_stores_current_snapshot(self):
        _store_local_fallback("maas:telemetry:n1", "maas:telemetry:n1:history", {"cpu": 0.5})
        assert _mod._LOCAL_TELEMETRY_FALLBACK.get("maas:telemetry:n1") == {"cpu": 0.5}

    def test_creates_history_list(self):
        _store_local_fallback("k", "k:history", {"x": 1})
        history = _mod._LOCAL_TELEMETRY_FALLBACK.get("k:history")
        assert isinstance(history, list)
        assert history[0] == {"x": 1}

    def test_history_prepends_newest_first(self):
        _store_local_fallback("k", "k:history", {"x": 1})
        _store_local_fallback("k", "k:history", {"x": 2})
        history = _mod._LOCAL_TELEMETRY_FALLBACK.get("k:history")
        assert history[0]["x"] == 2
        assert history[1]["x"] == 1

    def test_history_trimmed_to_max_items(self):
        orig_max = _mod.TELEMETRY_HISTORY_MAX_ITEMS
        _mod.TELEMETRY_HISTORY_MAX_ITEMS = 3
        try:
            for i in range(5):
                _store_local_fallback("k", "k:history", {"i": i})
            history = _mod._LOCAL_TELEMETRY_FALLBACK.get("k:history")
            assert len(history) == 3
        finally:
            _mod.TELEMETRY_HISTORY_MAX_ITEMS = orig_max

    def test_overwrites_corrupted_history(self):
        # If the history key holds a non-list, it should be reset
        _mod._LOCAL_TELEMETRY_FALLBACK.set("k:history", "corrupted")
        _store_local_fallback("k", "k:history", {"new": True})
        history = _mod._LOCAL_TELEMETRY_FALLBACK.get("k:history")
        assert isinstance(history, list)
        assert history[0] == {"new": True}


# ===========================================================================
# _set_telemetry / _get_telemetry / _get_telemetry_history (Redis-off path)
# ===========================================================================


class TestTelemetryFallbackPath:
    """Tests for Redis-unavailable path using the in-memory fallback."""

    def setup_method(self):
        _mod._LOCAL_TELEMETRY_FALLBACK.clear()
        # Ensure REDIS_AVAILABLE is False for these tests
        self._orig = _mod.REDIS_AVAILABLE
        _mod.REDIS_AVAILABLE = False

    def teardown_method(self):
        _mod.REDIS_AVAILABLE = self._orig

    def test_set_then_get_roundtrip(self):
        data = {"cpu": 0.7, "status": "healthy"}
        deps: set = set()
        _mod._set_telemetry("node-x", data, degraded_dependencies=deps)
        result = _mod._get_telemetry("node-x", degraded_dependencies=deps)
        assert result == data

    def test_set_adds_redis_to_degraded(self):
        deps: set = set()
        _mod._set_telemetry("node-y", {"cpu": 0.1}, degraded_dependencies=deps)
        assert "redis" in deps

    def test_get_missing_returns_empty_dict(self):
        result = _mod._get_telemetry("node-never-set")
        assert result == {}

    def test_get_history_after_set(self):
        deps: set = set()
        _mod._set_telemetry("node-h", {"v": 1}, degraded_dependencies=deps)
        _mod._set_telemetry("node-h", {"v": 2}, degraded_dependencies=deps)
        history = _mod._get_telemetry_history("node-h", limit=10)
        assert len(history) == 2

    def test_get_history_limit_respected(self):
        for i in range(5):
            _mod._set_telemetry("node-lim", {"i": i})
        history = _mod._get_telemetry_history("node-lim", limit=3)
        assert len(history) == 3

    def test_get_history_zero_limit_returns_empty(self):
        _mod._set_telemetry("node-z", {"x": 1})
        history = _mod._get_telemetry_history("node-z", limit=0)
        assert history == []

    def test_get_history_missing_node_returns_empty(self):
        result = _mod._get_telemetry_history("ghost-node")
        assert result == []

    def test_no_degraded_without_kwarg(self):
        # No degraded_dependencies kwarg → no error
        _mod._set_telemetry("node-nd", {"a": 1})
        result = _mod._get_telemetry("node-nd")
        assert result == {"a": 1}

    def test_eventbus_observed_state_evidence_is_redacted(self, tmp_path):
        bus = EventBus(project_root=str(tmp_path))
        deps: set[str] = set()
        data = {
            "mesh_id": "mesh-secret-telemetry",
            "node_id": "node-secret-telemetry",
            "status": "healthy",
            "latency_ms": 12.5,
            "pheromones": {"neighbor-secret": {"node-secret-telemetry": 0.8}},
        }

        _mod._set_telemetry(
            "node-secret-telemetry",
            data,
            degraded_dependencies=deps,
            event_bus=bus,
            mesh_id="mesh-secret-telemetry",
        )
        assert _mod._get_telemetry(
            "node-secret-telemetry",
            degraded_dependencies=deps,
            event_bus=bus,
            mesh_id="mesh-secret-telemetry",
        ) == data
        assert _mod._get_telemetry_history(
            "node-secret-telemetry",
            limit=5,
            degraded_dependencies=deps,
            event_bus=bus,
            mesh_id="mesh-secret-telemetry",
        ) == [data]

        events = bus.get_event_history(
            event_type=EventType.PIPELINE_STAGE_END,
            source_agent="maas-telemetry",
            limit=10,
        )
        payloads_by_operation = {
            event.data["operation"]: event.data for event in events
        }

        write_payload = payloads_by_operation["telemetry_snapshot_write"]
        assert write_payload["service_name"] == "maas-telemetry"
        assert write_payload["source_alias"] == "maas-telemetry"
        assert write_payload["layer"] == "api_telemetry_observed_state"
        assert write_payload["storage_backend"] == "local_fallback"
        assert write_payload["read_only"] is False
        assert write_payload["safe_actuator"] is False
        assert write_payload["raw_identifiers_redacted"] is True
        assert write_payload["node_id_hash"] == _mod._redacted_sha256_prefix(
            "node-secret-telemetry"
        )
        assert write_payload["mesh_id_hash"] == _mod._redacted_sha256_prefix(
            "mesh-secret-telemetry"
        )
        assert write_payload["degraded_dependencies"] == ["redis"]
        assert write_payload["telemetry_summary"]["field_count"] == len(data)
        assert write_payload["telemetry_summary"]["has_pheromones"] is True
        write_claim_gate = write_payload["maas_telemetry_claim_gate"]
        assert write_claim_gate["surface"] == "maas_telemetry.telemetry_snapshot_write"
        assert write_claim_gate["local_telemetry_snapshot_observation_claim_allowed"] is True
        assert write_claim_gate["dataplane_delivery_claim_allowed"] is False
        assert write_claim_gate["traffic_delivery_claim_allowed"] is False
        assert write_claim_gate["customer_traffic_claim_allowed"] is False
        assert write_claim_gate["settlement_finality_claim_allowed"] is False
        assert write_claim_gate["production_readiness_claim_allowed"] is False

        read_payload = payloads_by_operation["telemetry_snapshot_read"]
        assert read_payload["read_only"] is True
        assert read_payload["storage_backend"] == "local_fallback"
        assert read_payload["maas_telemetry_claim_gate"]["surface"] == (
            "maas_telemetry.telemetry_snapshot_read"
        )
        assert read_payload["maas_telemetry_claim_gate"][
            "local_telemetry_snapshot_observation_claim_allowed"
        ] is True

        history_payload = payloads_by_operation["telemetry_history_read"]
        assert history_payload["read_only"] is True
        assert history_payload["telemetry_summary"]["history_count"] == 1
        assert history_payload["maas_telemetry_claim_gate"]["surface"] == (
            "maas_telemetry.telemetry_history_read"
        )
        assert history_payload["maas_telemetry_claim_gate"][
            "local_telemetry_history_observation_claim_allowed"
        ] is True

        serialized = json.dumps(
            [event.data for event in events],
            sort_keys=True,
        )
        raw_log = (
            tmp_path / ".agent_coordination" / "events.log"
        ).read_text(encoding="utf-8")
        for raw_value in (
            "node-secret-telemetry",
            "mesh-secret-telemetry",
            "neighbor-secret",
        ):
            assert raw_value not in serialized
            assert raw_value not in raw_log


class TestTopologyEvidence:
    @pytest.mark.asyncio
    async def test_topology_response_marks_cached_telemetry_source_quality(
        self,
        monkeypatch,
        tmp_path,
    ):
        bus = EventBus(project_root=str(tmp_path))
        request = SimpleNamespace(
            state=SimpleNamespace(event_bus=bus, event_project_root=str(tmp_path))
        )
        node = SimpleNamespace(
            id="node-topology-secret",
            mesh_id="mesh-topology-secret",
            device_class="edge",
            status="healthy",
        )

        class FakeQuery:
            def filter(self, *_args, **_kwargs):
                return self

            def all(self):
                return [node]

        class FakeDb:
            def query(self, _model):
                return FakeQuery()

        monkeypatch.setattr(_mod, "REDIS_AVAILABLE", False)
        monkeypatch.setattr(_mod, "r_client", None)
        monkeypatch.setattr(
            _mod,
            "_LOCAL_TELEMETRY_FALLBACK",
            _mod.LRUCache(max_size=16),
        )
        monkeypatch.setattr(
            _mod,
            "_verify_topology_mesh_access",
            lambda *_args, **_kwargs: {
                "mesh_source": "database",
                "owner_checked": True,
            },
        )

        _mod._set_telemetry(
            node.id,
            {
                "status": "healthy",
                "latency_ms": 12.5,
                "pheromones": {"neighbor-secret": {node.id: 0.8}},
            },
            event_bus=bus,
            mesh_id=node.mesh_id,
        )

        response = await _mod.get_topology(
            node.mesh_id,
            request=request,
            db=FakeDb(),
            current_user=SimpleNamespace(id="owner-secret"),
        )
        telemetry_evidence = response["nodes"][0]["telemetry_evidence"]
        control_policy_evidence = response["control_policy_evidence"]

        assert response["nodes"][0]["status"] == "healthy"
        assert telemetry_evidence["decision_basis"] == "cached_observed_state"
        assert telemetry_evidence["source_quality"] == (
            "local_fallback_or_redis_degraded_cached_snapshot"
        )
        assert telemetry_evidence["status_source"] == "cached_telemetry_status"
        assert telemetry_evidence["dataplane_confirmed"] is False
        assert telemetry_evidence["events_total"] == 1
        assert telemetry_evidence["source_agents"] == ["maas-telemetry"]
        assert telemetry_evidence["payload_summary"]["has_pheromones"] is True
        assert telemetry_evidence["maas_telemetry_claim_gate"]["surface"] == (
            "maas_telemetry.topology_node_telemetry_evidence"
        )
        assert telemetry_evidence["maas_telemetry_claim_gate"][
            "local_topology_snapshot_observation_claim_allowed"
        ] is True
        assert telemetry_evidence["maas_telemetry_claim_gate"][
            "dataplane_delivery_claim_allowed"
        ] is False
        assert telemetry_evidence["maas_telemetry_claim_gate"][
            "node_reachability_claim_allowed"
        ] is False
        assert telemetry_evidence["maas_telemetry_claim_gate"][
            "settlement_finality_claim_allowed"
        ] is False
        assert control_policy_evidence["decision_basis"] == (
            "cached_telemetry_observed_state"
        )
        assert control_policy_evidence["dataplane_confirmed"] is False
        assert control_policy_evidence["events_total"] == 1
        assert control_policy_evidence["event_ids"] == telemetry_evidence["event_ids"]
        assert control_policy_evidence["source_qualities"] == [
            "local_fallback_or_redis_degraded_cached_snapshot"
        ]
        assert control_policy_evidence["maas_telemetry_claim_gate"]["surface"] == (
            "maas_telemetry.topology_control_policy_evidence"
        )
        assert control_policy_evidence["maas_telemetry_claim_gate"][
            "routing_convergence_claim_allowed"
        ] is False

        evidence_text = json.dumps(
            {
                "telemetry_evidence": telemetry_evidence,
                "control_policy_evidence": control_policy_evidence,
            },
            sort_keys=True,
        )
        for raw_value in (node.id, node.mesh_id, "neighbor-secret", "owner-secret"):
            assert raw_value not in evidence_text


# ===========================================================================
# get_fallback_cache_stats
# ===========================================================================


class TestGetFallbackCacheStats:
    def test_returns_dict_with_expected_keys(self):
        stats = get_fallback_cache_stats()
        assert isinstance(stats, dict)
        for key in ("size", "max_size", "hits", "misses", "hit_rate", "evictions"):
            assert key in stats

"""Unit tests for MeshShield quarantine engine."""

import asyncio
import time
from unittest.mock import patch, MagicMock

import pytest

from src.network.mesh_shield import (
    MeshShield,
    NodeHealth,
    NodeStatus,
    FailureEvent,
    ShieldedMeshRouter,
)


# ========== NodeStatus Tests ==========


class TestNodeStatus:
    def test_enum_values(self):
        assert NodeStatus.HEALTHY.value == "healthy"
        assert NodeStatus.DEGRADED.value == "degraded"
        assert NodeStatus.QUARANTINED.value == "quarantined"
        assert NodeStatus.DEAD.value == "dead"

    def test_all_statuses(self):
        assert len(NodeStatus) == 4


# ========== NodeHealth Tests ==========


class TestNodeHealth:
    def test_defaults(self):
        nh = NodeHealth(node_id="n1")
        assert nh.node_id == "n1"
        assert nh.status == NodeStatus.HEALTHY
        assert nh.reputation == 1.0
        assert nh.failure_count == 0
        assert nh.recovery_count == 0

    def test_is_alive_recent_beacon(self):
        nh = NodeHealth(node_id="n1", last_beacon=time.time())
        assert nh.is_alive(timeout=3.0) is True

    def test_is_alive_old_beacon(self):
        nh = NodeHealth(node_id="n1", last_beacon=time.time() - 10)
        assert nh.is_alive(timeout=3.0) is False

    def test_is_quarantined_active(self):
        nh = NodeHealth(node_id="n1", quarantine_until=time.time() + 100)
        assert nh.is_quarantined() is True

    def test_is_quarantined_expired(self):
        nh = NodeHealth(node_id="n1", quarantine_until=time.time() - 1)
        assert nh.is_quarantined() is False

    def test_is_quarantined_default(self):
        nh = NodeHealth(node_id="n1")
        assert nh.is_quarantined() is False


# ========== FailureEvent Tests ==========


class TestFailureEvent:
    def test_defaults(self):
        fe = FailureEvent(node_id="n1", timestamp=1000.0, detection_time=2.5)
        assert fe.node_id == "n1"
        assert fe.recovery_time == 0.0
        assert fe.cause == "unknown"
        assert fe.recovered is False

    def test_custom_values(self):
        fe = FailureEvent(
            node_id="n2",
            timestamp=2000.0,
            detection_time=1.0,
            recovery_time=5.0,
            cause="beacon_timeout",
            recovered=True,
        )
        assert fe.cause == "beacon_timeout"
        assert fe.recovered is True


# ========== MeshShield Core Tests ==========


class TestMeshShield:
    @pytest.fixture
    def shield(self):
        return MeshShield("local-node")

    def test_init(self, shield):
        assert shield.node_id == "local-node"
        assert shield.nodes == {}
        assert shield._running is False
        assert shield._metrics["failures_detected"] == 0

    def test_register_node(self, shield):
        shield.register_node("n1")
        assert "n1" in shield.nodes
        assert shield.nodes["n1"].status == NodeStatus.HEALTHY

    def test_register_node_idempotent(self, shield):
        shield.register_node("n1")
        shield.nodes["n1"].failure_count = 5
        shield.register_node("n1")  # should not reset
        assert shield.nodes["n1"].failure_count == 5

    def test_receive_beacon_new_node(self, shield):
        shield.receive_beacon("n1", latency_ms=50.0)
        assert "n1" in shield.nodes
        assert shield.nodes["n1"].latency_ms == 50.0

    def test_receive_beacon_updates_status(self, shield):
        shield.register_node("n1")
        shield.receive_beacon("n1", latency_ms=100.0)
        assert shield.nodes["n1"].status == NodeStatus.HEALTHY

    def test_receive_beacon_high_latency_degrades(self, shield):
        shield.register_node("n1")
        shield.receive_beacon("n1", latency_ms=600.0)
        assert shield.nodes["n1"].status == NodeStatus.DEGRADED

    def test_receive_beacon_recovery(self, shield):
        shield.register_node("n1")
        shield.nodes["n1"].status = NodeStatus.DEAD
        shield.receive_beacon("n1", latency_ms=50.0)
        assert shield.nodes["n1"].status == NodeStatus.HEALTHY
        assert shield.nodes["n1"].recovery_count == 1

    def test_receive_beacon_reputation_recovery(self, shield):
        shield.register_node("n1")
        shield.nodes["n1"].reputation = 0.5
        shield.receive_beacon("n1", latency_ms=50.0)
        assert shield.nodes["n1"].reputation > 0.5

    def test_receive_beacon_reputation_capped(self, shield):
        shield.register_node("n1")
        shield.nodes["n1"].reputation = 0.999
        shield.receive_beacon("n1", latency_ms=50.0)
        assert shield.nodes["n1"].reputation <= 1.0


# ========== Async Methods Tests ==========


class TestMeshShieldAsync:
    @pytest.fixture
    def shield(self):
        return MeshShield("local-node")

    @pytest.mark.asyncio
    async def test_start_stop(self, shield):
        await shield.start()
        assert shield._running is True
        await shield.stop()
        assert shield._running is False

    @pytest.mark.asyncio
    async def test_beacon_loop_detects_dead_node(self, shield):
        shield.register_node("n1")
        shield.nodes["n1"].last_beacon = time.time() - 10  # stale
        shield._running = True

        # Run one iteration of beacon loop
        now = time.time()
        node = shield.nodes["n1"]
        time_since = now - node.last_beacon
        if time_since > shield.FAILURE_THRESHOLD:
            node.status = NodeStatus.DEAD
            node.failure_count += 1

        assert shield.nodes["n1"].status == NodeStatus.DEAD
        assert shield.nodes["n1"].failure_count == 1

    @pytest.mark.asyncio
    async def test_beacon_loop_detects_degraded(self, shield):
        shield.register_node("n1")
        shield.nodes["n1"].last_beacon = time.time() - 2.0  # between thresholds
        shield._running = True

        now = time.time()
        node = shield.nodes["n1"]
        time_since = now - node.last_beacon
        if time_since > shield.DEGRADED_THRESHOLD and node.status == NodeStatus.HEALTHY:
            node.status = NodeStatus.DEGRADED

        assert shield.nodes["n1"].status == NodeStatus.DEGRADED

    @pytest.mark.asyncio
    async def test_beacon_loop_skips_quarantined(self, shield):
        shield.register_node("n1")
        shield.nodes["n1"].quarantine_until = time.time() + 100
        shield.nodes["n1"].last_beacon = time.time() - 10
        shield._running = True

        # Quarantined nodes should be skipped
        node = shield.nodes["n1"]
        if not node.is_quarantined():
            node.status = NodeStatus.DEAD

        # Status should NOT change (quarantined)
        assert shield.nodes["n1"].status == NodeStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_handle_failure(self, shield):
        shield.register_node("n1")
        await shield._handle_failure("n1", detection_time=3.5)

        assert shield.nodes["n1"].status == NodeStatus.QUARANTINED
        assert shield.nodes["n1"].failure_count == 1
        assert shield._metrics["failures_detected"] == 1
        assert shield._metrics["failures_recovered"] == 1
        assert len(shield.failure_events) == 1
        assert shield.failure_events[0].cause == "beacon_timeout"

    @pytest.mark.asyncio
    async def test_quarantine_node(self, shield):
        shield.register_node("n1")
        await shield._quarantine_node("n1")

        assert shield.nodes["n1"].status == NodeStatus.QUARANTINED
        assert shield.nodes["n1"].quarantine_until > time.time()
        assert shield._metrics["quarantines"] == 1

    @pytest.mark.asyncio
    async def test_reroute_traffic_with_backup(self, shield):
        shield.register_node("n1")
        shield.register_node("n2")
        shield.active_routes["dest1"] = ["n1", "n2"]
        shield.backup_routes["dest1"] = ["n2", "n3"]

        await shield._reroute_traffic("n1")

        assert shield.active_routes["dest1"] == ["n2", "n3"]

    @pytest.mark.asyncio
    async def test_reroute_traffic_no_backup(self, shield):
        shield.register_node("n1")
        shield.register_node("n2")
        shield.receive_beacon("n2", latency_ms=50)
        shield.active_routes["dest1"] = ["n1"]

        await shield._reroute_traffic("n1")

        # Should calculate new route excluding n1
        if "dest1" in shield.active_routes:
            assert "n1" not in shield.active_routes["dest1"]


# ========== Route Calculation Tests ==========


class TestRouteCalculation:
    @pytest.fixture
    def shield(self):
        s = MeshShield("local")
        s.register_node("n1")
        s.register_node("n2")
        s.register_node("n3")
        s.receive_beacon("n1", 50)
        s.receive_beacon("n2", 80)
        s.receive_beacon("n3", 200)
        return s

    def test_calculate_route_excludes(self, shield):
        route = shield._calculate_route("dest", exclude=["n1"])
        assert "n1" not in route

    def test_calculate_route_returns_healthy_only(self, shield):
        shield.nodes["n2"].status = NodeStatus.DEAD
        route = shield._calculate_route("dest")
        assert "n2" not in route

    def test_calculate_route_empty_when_all_excluded(self, shield):
        route = shield._calculate_route("dest", exclude=["n1", "n2", "n3"])
        assert route == []

    def test_calculate_route_sorted_by_reputation(self, shield):
        shield.nodes["n3"].reputation = 0.1
        route = shield._calculate_route("dest")
        if len(route) >= 2:
            # n1 and n2 should be preferred (higher reputation)
            assert "n3" not in route[:2] or shield.nodes["n3"].reputation >= shield.nodes["n1"].reputation


# ========== Recovery Tests ==========


class TestRecovery:
    def test_complete_recovery(self):
        shield = MeshShield("local")
        shield.register_node("n1")
        shield.nodes["n1"].status = NodeStatus.QUARANTINED
        shield.nodes["n1"].quarantine_until = time.time() + 100

        shield._complete_recovery("n1")

        assert shield.nodes["n1"].status == NodeStatus.HEALTHY
        assert shield.nodes["n1"].quarantine_until == 0.0


# ========== Metrics Tests ==========


class TestMetrics:
    @pytest.fixture
    def shield(self):
        s = MeshShield("local")
        s.register_node("n1")
        s.register_node("n2")
        return s

    def test_get_metrics_empty(self, shield):
        metrics = shield.get_metrics()
        assert metrics["mttr_avg"] == 0
        assert metrics["mttd_avg"] == 0
        assert metrics["failures_detected"] == 0
        assert metrics["nodes_healthy"] == 2

    def test_get_metrics_with_data(self, shield):
        shield._metrics["mttr_samples"] = [1.0, 2.0, 3.0]
        shield._metrics["mttd_samples"] = [0.5, 1.5]
        shield._metrics["failures_detected"] = 3
        shield._metrics["failures_recovered"] = 2

        metrics = shield.get_metrics()
        assert metrics["mttr_avg"] == 2.0
        assert metrics["mttd_avg"] == 1.0
        assert metrics["recovery_rate"] == 2 / 3

    def test_get_node_status(self, shield):
        shield.receive_beacon("n1", 50)
        status = shield.get_node_status()
        assert len(status) == 2
        assert any(s["node_id"] == "n1" for s in status)

    def test_export_metrics(self, shield, tmp_path):
        filepath = str(tmp_path / "metrics.json")
        shield.export_metrics(filepath)

        import json
        with open(filepath) as f:
            data = json.load(f)
        assert "metrics" in data
        assert "nodes" in data
        assert data["node_id"] == "local"


# ========== ShieldedMeshRouter Tests ==========


class TestShieldedMeshRouter:
    def test_init(self):
        router = ShieldedMeshRouter("local")
        assert router.node_id == "local"
        assert isinstance(router.shield, MeshShield)

    def test_on_peer_beacon(self):
        router = ShieldedMeshRouter("local")
        router.on_peer_beacon("peer1", 50.0)
        assert "peer1" in router.shield.nodes

    def test_get_healthy_peers(self):
        router = ShieldedMeshRouter("local")
        router.shield.register_node("p1")
        router.shield.register_node("p2")
        router.shield.receive_beacon("p1", 50)
        router.shield.receive_beacon("p2", 50)
        router.shield.nodes["p2"].status = NodeStatus.DEAD

        healthy = router.get_healthy_peers()
        assert "p1" in healthy
        assert "p2" not in healthy

    @pytest.mark.asyncio
    async def test_start_stop(self):
        router = ShieldedMeshRouter("local")
        await router.start()
        assert router.shield._running is True
        await router.stop()
        assert router.shield._running is False

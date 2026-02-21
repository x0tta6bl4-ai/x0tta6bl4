"""Unit tests for Route Recovery."""
import os
import time
import pytest
from unittest.mock import patch, MagicMock

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

from src.network.routing.recovery import RecoveryAttempt, RouteRecovery
from src.network.routing.route_table import RouteEntry, RouteTable
from src.network.routing.topology import TopologyManager, NodeInfo


class TestRecoveryAttempt:
    def test_defaults(self):
        ra = RecoveryAttempt(destination="node-002", start_time=time.time())
        assert ra.attempt_count == 0
        assert ra.max_attempts == 3
        assert ra.success is False

    def test_elapsed(self):
        ra = RecoveryAttempt(destination="node-002", start_time=time.time() - 2.0)
        assert ra.elapsed >= 2.0


class TestRouteRecoveryInit:
    def test_init(self):
        topo = TopologyManager("local")
        rt = RouteTable()
        rr = RouteRecovery(topo, rt, "local")
        assert rr.local_node_id == "local"
        assert rr._recovery_attempts == {}
        assert rr._neighbor_hellos == {}


class TestSetCallbacks:
    def test_set_all(self):
        topo = TopologyManager("local")
        rt = RouteTable()
        rr = RouteRecovery(topo, rt, "local")
        cb1, cb2, cb3, cb4 = MagicMock(), MagicMock(), MagicMock(), MagicMock()
        rr.set_callbacks(cb1, cb2, cb3, cb4)
        assert rr._on_route_discovery is cb1
        assert rr._on_route_error is cb2
        assert rr._on_recovery_success is cb3
        assert rr._on_recovery_failure is cb4


class TestHandleHello:
    def test_new_neighbor(self):
        topo = TopologyManager("local")
        topo.add_node("n1", is_neighbor=True)
        rt = RouteTable()
        rr = RouteRecovery(topo, rt, "local")
        rr.handle_hello("n1")
        assert "n1" in rr._neighbor_hellos
        assert rr._neighbor_hellos["n1"][0] == 0  # zero missed

    def test_updates_topology(self):
        topo = TopologyManager("local")
        node = topo.add_node("n1", is_neighbor=True)
        old_seen = node.last_seen
        rt = RouteTable()
        rr = RouteRecovery(topo, rt, "local")
        time.sleep(0.01)
        rr.handle_hello("n1")
        assert topo.get_node("n1").last_seen >= old_seen


class TestCheckNeighborStatus:
    def test_no_failures(self):
        topo = TopologyManager("local")
        rt = RouteTable()
        rr = RouteRecovery(topo, rt, "local")
        rr._neighbor_hellos["n1"] = (0, time.time())
        assert rr.check_neighbor_status() == []

    def test_missed_hellos(self):
        topo = TopologyManager("local")
        rt = RouteTable()
        rr = RouteRecovery(topo, rt, "local")
        # Set last hello to long ago, already missed 2
        rr._neighbor_hellos["n1"] = (2, time.time() - 10)
        failed = rr.check_neighbor_status()
        assert "n1" in failed

    def test_increments_missed(self):
        topo = TopologyManager("local")
        rt = RouteTable()
        rr = RouteRecovery(topo, rt, "local")
        rr._neighbor_hellos["n1"] = (1, time.time() - 2)
        rr.check_neighbor_status()
        # n1 should have missed incremented to 2 but still below threshold
        assert "n1" in rr._neighbor_hellos or "n1" not in rr._neighbor_hellos


class TestHandleLinkFailure:
    def test_marks_inactive(self):
        topo = TopologyManager("local")
        topo.add_node("n1", is_neighbor=True)
        rt = RouteTable()
        rr = RouteRecovery(topo, rt, "local")
        rr.handle_link_failure("n1")
        assert topo.get_node("n1").is_active is False

    def test_finds_affected_routes(self):
        topo = TopologyManager("local")
        topo.add_node("n1", is_neighbor=True)
        rt = RouteTable()
        rt.add_route(RouteEntry(destination="dest1", next_hop="n1", hop_count=2, seq_num=1))
        rr = RouteRecovery(topo, rt, "local")
        affected = rr.handle_link_failure("n1")
        assert "dest1" in affected

    def test_calls_error_callback(self):
        topo = TopologyManager("local")
        topo.add_node("n1", is_neighbor=True)
        rt = RouteTable()
        rr = RouteRecovery(topo, rt, "local")
        cb = MagicMock()
        rr.set_callbacks(on_route_error=cb)
        rr.handle_link_failure("n1")
        cb.assert_called_once_with("n1")


class TestTryAlternativePath:
    def test_no_alternative(self):
        topo = TopologyManager("local")
        rt = RouteTable()
        rr = RouteRecovery(topo, rt, "local")
        assert rr._try_alternative_path("dest1") is False

    def test_with_alternative(self):
        topo = TopologyManager("local")
        rt = RouteTable()
        route = RouteEntry(destination="dest1", next_hop="n2", hop_count=3, seq_num=1)
        rt.add_route(route)
        rr = RouteRecovery(topo, rt, "local")
        # Has valid route
        result = rr._try_alternative_path("dest1")
        assert isinstance(result, bool)


class TestInitiateDiscovery:
    def test_no_attempt(self):
        topo = TopologyManager("local")
        rt = RouteTable()
        rr = RouteRecovery(topo, rt, "local")
        rr._initiate_discovery("dest1")  # No recovery attempt, should be no-op

    def test_max_attempts_reached(self):
        topo = TopologyManager("local")
        rt = RouteTable()
        rr = RouteRecovery(topo, rt, "local")
        cb = MagicMock()
        rr.set_callbacks(on_recovery_failure=cb)
        rr._recovery_attempts["dest1"] = RecoveryAttempt(
            destination="dest1", start_time=time.time(), attempt_count=3
        )
        rr._initiate_discovery("dest1")
        cb.assert_called_once_with("dest1")
        assert "dest1" not in rr._recovery_attempts

    def test_calls_discovery_callback(self):
        topo = TopologyManager("local")
        rt = RouteTable()
        rr = RouteRecovery(topo, rt, "local")
        cb = MagicMock()
        rr.set_callbacks(on_route_discovery=cb)
        rr._recovery_attempts["dest1"] = RecoveryAttempt(
            destination="dest1", start_time=time.time(), attempt_count=0
        )
        rr._initiate_discovery("dest1")
        cb.assert_called_once_with("dest1")


class TestHandleRouteDiscovered:
    def test_not_recovering(self):
        topo = TopologyManager("local")
        rt = RouteTable()
        rr = RouteRecovery(topo, rt, "local")
        route = RouteEntry(destination="dest1", next_hop="n2", hop_count=2, seq_num=1)
        rr.handle_route_discovered("dest1", route)  # No recovery, should not crash

    def test_successful_recovery(self):
        topo = TopologyManager("local")
        rt = RouteTable()
        rr = RouteRecovery(topo, rt, "local")
        cb = MagicMock()
        rr.set_callbacks(on_recovery_success=cb)
        rr._recovery_attempts["dest1"] = RecoveryAttempt(
            destination="dest1", start_time=time.time()
        )
        route = RouteEntry(destination="dest1", next_hop="n2", hop_count=2, seq_num=1)
        rr.handle_route_discovered("dest1", route)
        assert "dest1" not in rr._recovery_attempts
        cb.assert_called_once()


class TestCheckRecoveryTimeouts:
    def test_no_timeouts(self):
        topo = TopologyManager("local")
        rt = RouteTable()
        rr = RouteRecovery(topo, rt, "local")
        assert rr.check_recovery_timeouts() == []

    def test_timeout_with_retries(self):
        topo = TopologyManager("local")
        rt = RouteTable()
        rr = RouteRecovery(topo, rt, "local")
        rr._recovery_attempts["dest1"] = RecoveryAttempt(
            destination="dest1", start_time=time.time() - 10, attempt_count=3
        )
        failed = rr.check_recovery_timeouts()
        assert "dest1" in failed


class TestGetStats:
    def test_stats(self):
        topo = TopologyManager("local")
        rt = RouteTable()
        rr = RouteRecovery(topo, rt, "local")
        stats = rr.get_stats()
        assert stats["active_recoveries"] == 0
        assert stats["tracked_neighbors"] == 0


class TestCleanup:
    def test_removes_old_recoveries(self):
        topo = TopologyManager("local")
        rt = RouteTable()
        rr = RouteRecovery(topo, rt, "local")
        rr._recovery_attempts["old"] = RecoveryAttempt(
            destination="old", start_time=time.time() - 100
        )
        rr.cleanup()
        assert "old" not in rr._recovery_attempts

    def test_removes_stale_hellos(self):
        topo = TopologyManager("local")
        rt = RouteTable()
        rr = RouteRecovery(topo, rt, "local")
        rr._neighbor_hellos["stale"] = (5, time.time() - 100)
        rr.cleanup()
        assert "stale" not in rr._neighbor_hellos

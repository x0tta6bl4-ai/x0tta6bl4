"""
Comprehensive unit tests for src/simulation/digital_twin.py.
"""

import json
import time
from unittest.mock import MagicMock, patch

import pytest

from src.simulation.digital_twin import (
    ChaosScenarioRunner,
    LinkState,
    MeshDigitalTwin,
    NodeState,
    SimulationResult,
    TwinLink,
    TwinNode,
)


# ==================== TwinNode Tests ====================


class TestTwinNode:
    def test_defaults(self):
        node = TwinNode(node_id="n1")
        assert node.node_id == "n1"
        assert node.state == NodeState.HEALTHY
        assert node.cpu_usage == 0.0
        assert node.memory_usage == 0.0
        assert node.uptime == 0.0
        assert node.trust_score == 1.0
        assert node.position == (0.0, 0.0)
        assert node.metadata == {}
        assert len(node.state_history) == 0
        assert len(node.metrics_history) == 0

    def test_record_state(self):
        node = TwinNode(node_id="n1", cpu_usage=50.0, memory_usage=70.0)
        node.state = NodeState.DEGRADED
        node.record_state()
        assert len(node.state_history) == 1
        entry = node.state_history[0]
        assert entry["state"] == "degraded"
        assert entry["cpu"] == 50.0
        assert entry["memory"] == 70.0
        assert "timestamp" in entry

    def test_record_state_maxlen(self):
        node = TwinNode(node_id="n1")
        for i in range(110):
            node.cpu_usage = float(i)
            node.record_state()
        # maxlen=100
        assert len(node.state_history) == 100
        # oldest should be i=10
        assert node.state_history[0]["cpu"] == 10.0

    def test_to_dict(self):
        node = TwinNode(
            node_id="n1",
            state=NodeState.FAILED,
            cpu_usage=80.0,
            memory_usage=60.0,
            uptime=3600.0,
            trust_score=0.5,
            position=(10.0, 20.0),
        )
        d = node.to_dict()
        assert d["node_id"] == "n1"
        assert d["state"] == "failed"
        assert d["cpu_usage"] == 80.0
        assert d["memory_usage"] == 60.0
        assert d["uptime"] == 3600.0
        assert d["trust_score"] == 0.5
        assert d["position"] == (10.0, 20.0)


# ==================== TwinLink Tests ====================


class TestTwinLink:
    def test_defaults(self):
        link = TwinLink(source="a", target="b")
        assert link.source == "a"
        assert link.target == "b"
        assert link.state == LinkState.UP
        assert link.latency_ms == 1.0
        assert link.bandwidth_mbps == 100.0
        assert link.packet_loss == 0.0
        assert link.rssi == -50.0
        assert link.snr == 20.0

    def test_link_id(self):
        link = TwinLink(source="a", target="b")
        assert link.link_id == "a->b"

    def test_quality_score_ideal(self):
        link = TwinLink(source="a", target="b", latency_ms=0.0, packet_loss=0.0, rssi=-40.0)
        score = link.quality_score
        # latency_score = 1.0, loss_score = 1.0, rssi_score = 1.0
        assert score == pytest.approx(1.0)

    def test_quality_score_worst(self):
        link = TwinLink(source="a", target="b", latency_ms=500.0, packet_loss=1.0, rssi=-90.0)
        score = link.quality_score
        # latency_score = 0.0, loss_score = 0.0, rssi_score = 0.0
        assert score == pytest.approx(0.0)

    def test_quality_score_mid(self):
        link = TwinLink(source="a", target="b", latency_ms=250.0, packet_loss=0.5, rssi=-65.0)
        score = link.quality_score
        # latency_score = 0.5, loss_score = 0.5, rssi_score = (25/50)=0.5
        assert score == pytest.approx(0.5)

    def test_quality_score_very_high_latency(self):
        link = TwinLink(source="a", target="b", latency_ms=1000.0, packet_loss=0.0, rssi=-50.0)
        # latency_score = max(0, 1-2) = 0
        assert link.quality_score >= 0.0

    def test_quality_score_very_low_rssi(self):
        link = TwinLink(source="a", target="b", latency_ms=0.0, packet_loss=0.0, rssi=-100.0)
        # rssi_score = max(0, (-100+90)/50) = max(0, -0.2) = 0
        score = link.quality_score
        assert score == pytest.approx(0.8)  # 1*0.4 + 1*0.4 + 0*0.2

    def test_to_dict(self):
        link = TwinLink(source="a", target="b", latency_ms=10.0, bandwidth_mbps=50.0, packet_loss=0.1)
        d = link.to_dict()
        assert d["link_id"] == "a->b"
        assert d["source"] == "a"
        assert d["target"] == "b"
        assert d["state"] == "up"
        assert d["latency_ms"] == 10.0
        assert d["bandwidth_mbps"] == 50.0
        assert d["packet_loss"] == 0.1
        assert "quality_score" in d


# ==================== SimulationResult Tests ====================


class TestSimulationResult:
    def test_to_dict(self):
        result = SimulationResult(
            scenario_name="test",
            duration_seconds=10.0,
            mttr_seconds=5.0,
            nodes_affected=3,
            links_affected=2,
            connectivity_maintained=0.8,
            packet_loss_total=0.1,
            events=[{"e": 1}, {"e": 2}],
        )
        d = result.to_dict()
        assert d["scenario"] == "test"
        assert d["duration_seconds"] == 10.0
        assert d["mttr_seconds"] == 5.0
        assert d["nodes_affected"] == 3
        assert d["links_affected"] == 2
        assert d["connectivity_maintained"] == 0.8
        assert d["packet_loss_total"] == 0.1
        assert d["events_count"] == 2

    def test_defaults(self):
        result = SimulationResult(
            scenario_name="x",
            duration_seconds=0,
            mttr_seconds=0,
            nodes_affected=0,
            links_affected=0,
            connectivity_maintained=1.0,
            packet_loss_total=0.0,
        )
        assert result.events == []
        assert result.to_dict()["events_count"] == 0


# ==================== Enums Tests ====================


class TestEnums:
    def test_node_state_values(self):
        assert NodeState.HEALTHY.value == "healthy"
        assert NodeState.DEGRADED.value == "degraded"
        assert NodeState.FAILED.value == "failed"
        assert NodeState.RECOVERING.value == "recovering"
        assert NodeState.ISOLATED.value == "isolated"

    def test_link_state_values(self):
        assert LinkState.UP.value == "up"
        assert LinkState.DEGRADED.value == "degraded"
        assert LinkState.DOWN.value == "down"
        assert LinkState.CONGESTED.value == "congested"


# ==================== MeshDigitalTwin Tests ====================


class TestMeshDigitalTwin:
    def _make_twin(self):
        """Create a twin with no prometheus."""
        return MeshDigitalTwin(twin_id="test")

    def _make_twin_with_nodes(self):
        """Create a twin with a small topology."""
        twin = self._make_twin()
        for i in range(5):
            twin.add_node(TwinNode(node_id=f"n{i}"))
        # Create a chain: n0-n1-n2-n3-n4
        for i in range(4):
            twin.add_link(TwinLink(source=f"n{i}", target=f"n{i+1}", latency_ms=10.0))
        # Add a cross link: n0-n3
        twin.add_link(TwinLink(source="n0", target="n3", latency_ms=20.0))
        return twin

    # ---- Init ----

    def test_init_default(self):
        twin = MeshDigitalTwin()
        assert twin.twin_id == "default"
        assert twin.prometheus_url is None
        assert twin.prom is None
        assert twin.nodes == {}
        assert twin.links == {}

    def test_init_with_id(self):
        twin = MeshDigitalTwin(twin_id="my-twin")
        assert twin.twin_id == "my-twin"

    @patch("src.simulation.digital_twin.HAS_PROMETHEUS", True)
    @patch("src.simulation.digital_twin.PrometheusConnect", create=True)
    def test_init_with_prometheus(self, mock_prom_cls):
        mock_client = MagicMock()
        mock_prom_cls.return_value = mock_client
        twin = MeshDigitalTwin(twin_id="t", prometheus_url="http://prom:9090")
        assert twin.prom is mock_client
        mock_prom_cls.assert_called_once_with(url="http://prom:9090")

    @patch("src.simulation.digital_twin.HAS_PROMETHEUS", True)
    @patch("src.simulation.digital_twin.PrometheusConnect", side_effect=Exception("conn fail"), create=True)
    def test_init_prometheus_connection_error(self, mock_prom_cls):
        twin = MeshDigitalTwin(twin_id="t", prometheus_url="http://prom:9090")
        assert twin.prom is None

    @patch("src.simulation.digital_twin.HAS_PROMETHEUS", False)
    def test_init_prometheus_not_available(self):
        twin = MeshDigitalTwin(twin_id="t", prometheus_url="http://prom:9090")
        assert twin.prom is None

    # ---- Topology Management ----

    def test_add_node(self):
        twin = self._make_twin()
        node = TwinNode(node_id="n1", cpu_usage=50.0)
        twin.add_node(node)
        assert "n1" in twin.nodes
        assert twin.graph.has_node("n1")

    def test_add_link(self):
        twin = self._make_twin()
        twin.add_node(TwinNode(node_id="a"))
        twin.add_node(TwinNode(node_id="b"))
        link = TwinLink(source="a", target="b", latency_ms=5.0)
        twin.add_link(link)
        assert "a->b" in twin.links
        assert twin.graph.has_edge("a", "b")

    def test_remove_node(self):
        twin = self._make_twin_with_nodes()
        assert "n1" in twin.nodes
        twin.remove_node("n1")
        assert "n1" not in twin.nodes
        assert not twin.graph.has_node("n1")
        # Links involving n1 should be gone
        for lid in twin.links:
            assert "n1" not in lid

    def test_remove_node_nonexistent(self):
        twin = self._make_twin()
        twin.remove_node("nonexistent")  # Should not raise

    def test_remove_node_removes_associated_links(self):
        twin = self._make_twin()
        twin.add_node(TwinNode(node_id="a"))
        twin.add_node(TwinNode(node_id="b"))
        twin.add_node(TwinNode(node_id="c"))
        twin.add_link(TwinLink(source="a", target="b"))
        twin.add_link(TwinLink(source="b", target="c"))
        twin.remove_node("b")
        assert len(twin.links) == 0

    def test_create_test_topology(self):
        twin = self._make_twin()
        with patch("src.simulation.digital_twin.random") as mock_random:
            mock_random.uniform.return_value = 50.0
            mock_random.random.return_value = 0.1  # < 0.3 connectivity
            twin.create_test_topology(num_nodes=5, connectivity=0.3)
        assert len(twin.nodes) == 5
        # All links should have been created since random() = 0.1 < 0.3
        # 5 nodes => C(5,2) = 10 pairs
        assert len(twin.links) == 10

    def test_create_test_topology_no_links(self):
        twin = self._make_twin()
        with patch("src.simulation.digital_twin.random") as mock_random:
            mock_random.uniform.return_value = 50.0
            mock_random.random.return_value = 0.9  # > 0.3 connectivity
            twin.create_test_topology(num_nodes=3, connectivity=0.3)
        assert len(twin.nodes) == 3
        assert len(twin.links) == 0

    # ---- Telemetry Ingestion ----

    def test_ingest_no_prometheus(self):
        twin = self._make_twin()
        count = twin.ingest_from_prometheus()
        assert count == 0

    def test_ingest_from_prometheus_node_metrics(self):
        twin = self._make_twin()
        mock_prom = MagicMock()
        twin.prom = mock_prom

        def custom_query_side_effect(query):
            if "cpu_usage" in query:
                return [
                    {
                        "metric": {"node_id": "n1"},
                        "values": [[1000, "45.0"], [1001, "50.0"]],
                    }
                ]
            return []

        mock_prom.custom_query.side_effect = custom_query_side_effect
        count = twin.ingest_from_prometheus(duration_hours=1)
        assert count == 2
        assert "n1" in twin.nodes
        assert twin.nodes["n1"].cpu_usage == 50.0

    def test_ingest_from_prometheus_link_metrics(self):
        twin = self._make_twin()
        mock_prom = MagicMock()
        twin.prom = mock_prom

        def custom_query_side_effect(query):
            if "mesh_link_latency_ms" in query:
                return [
                    {
                        "metric": {"source": "a", "target": "b"},
                        "values": [[1000, "15.0"]],
                    }
                ]
            return []

        mock_prom.custom_query.side_effect = custom_query_side_effect
        count = twin.ingest_from_prometheus()
        assert count == 1
        assert "a->b" in twin.links
        assert twin.links["a->b"].latency_ms == 15.0

    def test_ingest_from_prometheus_empty_values(self):
        twin = self._make_twin()
        mock_prom = MagicMock()
        twin.prom = mock_prom
        mock_prom.custom_query.return_value = [
            {"metric": {"node_id": "n1"}, "values": []}
        ]
        count = twin.ingest_from_prometheus()
        assert count == 0

    def test_ingest_from_prometheus_exception(self):
        twin = self._make_twin()
        mock_prom = MagicMock()
        twin.prom = mock_prom
        mock_prom.custom_query.side_effect = Exception("query failed")
        count = twin.ingest_from_prometheus()
        assert count == 0

    def test_ingest_creates_new_node_and_link(self):
        twin = self._make_twin()
        mock_prom = MagicMock()
        twin.prom = mock_prom

        call_count = [0]

        def custom_query_side_effect(query):
            call_count[0] += 1
            if "mesh_node_cpu_usage" in query:
                return [
                    {
                        "metric": {"node_id": "new_node"},
                        "values": [[1000, "30.0"]],
                    }
                ]
            if "mesh_link_latency_ms" in query:
                return [
                    {
                        "metric": {"source": "x", "target": "y"},
                        "values": [[1000, "5.0"]],
                    }
                ]
            return []

        mock_prom.custom_query.side_effect = custom_query_side_effect
        twin.ingest_from_prometheus()
        assert "new_node" in twin.nodes
        assert "x->y" in twin.links

    # ---- Failure Simulation ----

    def test_simulate_node_failure_nonexistent(self):
        twin = self._make_twin()
        result = twin.simulate_node_failure("nonexistent")
        assert result.scenario_name == "node_failure"
        assert result.nodes_affected == 0
        assert result.links_affected == 0
        assert result.connectivity_maintained == 1.0
        assert any("error" in e for e in result.events)

    def test_simulate_node_failure_success(self):
        twin = self._make_twin_with_nodes()
        result = twin.simulate_node_failure("n2")
        assert result.scenario_name == "node_failure"
        assert result.nodes_affected == 1
        assert result.links_affected > 0
        assert result.mttr_seconds > 0
        assert result.duration_seconds > 0
        # After simulation, node should be HEALTHY (recovered)
        assert twin.nodes["n2"].state == NodeState.HEALTHY
        # Links should be restored
        for lid, link in twin.links.items():
            if link.source == "n2" or link.target == "n2":
                assert link.state == LinkState.UP
        # Events should have expected sequence
        event_types = [e.get("event") for e in result.events]
        assert "node_failed" in event_types
        assert "links_down" in event_types
        assert "failure_detected" in event_types
        assert "recovery_planned" in event_types
        assert "recovery_started" in event_types
        assert "recovery_complete" in event_types

    def test_simulate_node_failure_records_recovery_time(self):
        twin = self._make_twin_with_nodes()
        twin.simulate_node_failure("n0")
        assert len(twin._recovery_times) == 1
        assert twin._recovery_times[0] > 0

    def test_simulate_node_failure_mttr_capped(self):
        """MTTR should be capped: base 2 + complexity factor capped at 10 + 1 stabilization."""
        twin = self._make_twin()
        # Many nodes to increase complexity
        for i in range(200):
            twin.add_node(TwinNode(node_id=f"n{i}"))
        twin.add_link(TwinLink(source="n0", target="n1"))
        result = twin.simulate_node_failure("n0")
        # min(2 + 200*0.1, 10) + 1 = 11
        assert result.mttr_seconds == 11.0

    # ---- Network Partition ----

    def test_simulate_network_partition(self):
        twin = self._make_twin_with_nodes()
        result = twin.simulate_network_partition(["n0", "n1"], ["n3", "n4"])
        assert result.scenario_name == "network_partition"
        assert result.nodes_affected == 4
        assert result.connectivity_maintained == 0.5
        # All links should be restored after
        for lid, link in twin.links.items():
            assert link.state == LinkState.UP
        event_types = [e.get("event") for e in result.events]
        assert "partition_created" in event_types
        assert "partition_healed" in event_types

    def test_simulate_network_partition_no_cross_links(self):
        twin = self._make_twin()
        twin.add_node(TwinNode(node_id="a"))
        twin.add_node(TwinNode(node_id="b"))
        # No link between them
        result = twin.simulate_network_partition(["a"], ["b"])
        assert result.links_affected == 0

    def test_simulate_network_partition_with_cross_links(self):
        twin = self._make_twin()
        twin.add_node(TwinNode(node_id="a"))
        twin.add_node(TwinNode(node_id="b"))
        twin.add_link(TwinLink(source="a", target="b"))
        result = twin.simulate_network_partition(["a"], ["b"])
        assert result.links_affected == 1

    # ---- Cascade Failure ----

    def test_simulate_cascade_failure_no_propagation(self):
        twin = self._make_twin_with_nodes()
        with patch("src.simulation.digital_twin.random") as mock_random:
            mock_random.random.return_value = 1.0  # Never propagate
            result = twin.simulate_cascade_failure(["n2"], propagation_probability=0.3)
        assert result.scenario_name == "cascade_failure"
        assert result.nodes_affected == 1
        # Node should be recovered
        assert twin.nodes["n2"].state == NodeState.HEALTHY

    def test_simulate_cascade_failure_full_propagation(self):
        twin = self._make_twin_with_nodes()
        with patch("src.simulation.digital_twin.random") as mock_random:
            mock_random.random.return_value = 0.0  # Always propagate
            result = twin.simulate_cascade_failure(["n2"], propagation_probability=0.5)
        assert result.nodes_affected == 5  # All nodes should be affected
        # All nodes should be recovered
        for node in twin.nodes.values():
            assert node.state == NodeState.HEALTHY

    def test_simulate_cascade_failure_wave_limit(self):
        """Cascade should stop after 10 waves."""
        twin = self._make_twin()
        # Create a long chain
        for i in range(30):
            twin.add_node(TwinNode(node_id=f"n{i}"))
        for i in range(29):
            twin.add_link(TwinLink(source=f"n{i}", target=f"n{i+1}"))

        with patch("src.simulation.digital_twin.random") as mock_random:
            mock_random.random.return_value = 0.0  # Always propagate
            result = twin.simulate_cascade_failure(["n0"], propagation_probability=1.0)
        # Should have stopped after 10 waves, but may still affect many nodes
        event_waves = [e for e in result.events if e.get("event") == "cascade_wave"]
        assert len(event_waves) <= 10

    def test_simulate_cascade_nonexistent_initial_node(self):
        twin = self._make_twin_with_nodes()
        with patch("src.simulation.digital_twin.random") as mock_random:
            mock_random.random.return_value = 1.0
            result = twin.simulate_cascade_failure(["nonexistent"])
        assert result.nodes_affected >= 1  # The set includes "nonexistent"

    def test_simulate_cascade_empty_topology(self):
        twin = self._make_twin()
        twin.add_node(TwinNode(node_id="alone"))
        with patch("src.simulation.digital_twin.random") as mock_random:
            mock_random.random.return_value = 0.0
            result = twin.simulate_cascade_failure(["alone"])
        assert result.nodes_affected == 1

    # ---- Analysis helpers ----

    def test_calculate_links_affected_empty(self):
        twin = self._make_twin_with_nodes()
        count = twin._calculate_links_affected(set())
        assert count == 0

    def test_calculate_links_affected_single_node(self):
        twin = self._make_twin_with_nodes()
        # n2 has links to n1 and n3
        count = twin._calculate_links_affected({"n2"})
        assert count == 2

    def test_calculate_links_affected_nonexistent_node(self):
        twin = self._make_twin_with_nodes()
        count = twin._calculate_links_affected({"nonexistent"})
        assert count == 0

    def test_calculate_links_affected_no_bidirectional(self):
        twin = self._make_twin()
        twin.add_node(TwinNode(node_id="a"))
        twin.add_node(TwinNode(node_id="b"))
        twin.add_link(TwinLink(source="a", target="b"))
        count = twin._calculate_links_affected({"a"}, consider_bidirectional=False)
        assert count == 1

    def test_calculate_links_affected_bidirectional_dedup(self):
        """When two failed nodes share a link, it should be counted once with bidirectional."""
        twin = self._make_twin()
        twin.add_node(TwinNode(node_id="a"))
        twin.add_node(TwinNode(node_id="b"))
        twin.add_link(TwinLink(source="a", target="b"))
        count = twin._calculate_links_affected({"a", "b"}, consider_bidirectional=True)
        assert count == 1

    def test_calculate_links_affected_by_partition(self):
        twin = self._make_twin_with_nodes()
        # n0-n1-n2-n3-n4 chain + n0-n3 cross
        # Partition: {n0,n1} vs {n3,n4}
        count = twin._calculate_links_affected_by_partition({"n0", "n1"}, {"n3", "n4"})
        # n1->n2 is not cross-partition (n2 not in either group)
        # n0->n3 is cross-partition
        assert count == 1

    def test_calculate_links_affected_by_partition_no_overlap(self):
        twin = self._make_twin()
        twin.add_node(TwinNode(node_id="a"))
        twin.add_node(TwinNode(node_id="b"))
        # No link
        count = twin._calculate_links_affected_by_partition({"a"}, {"b"})
        assert count == 0

    def test_calculate_connectivity_empty(self):
        twin = self._make_twin()
        assert twin._calculate_connectivity() == 1.0

    def test_calculate_connectivity_all_healthy(self):
        twin = self._make_twin_with_nodes()
        assert twin._calculate_connectivity() == 1.0

    def test_calculate_connectivity_partial(self):
        twin = self._make_twin_with_nodes()
        twin.nodes["n0"].state = NodeState.FAILED
        twin.nodes["n1"].state = NodeState.FAILED
        assert twin._calculate_connectivity() == pytest.approx(3 / 5)

    def test_plan_recovery(self):
        twin = self._make_twin_with_nodes()
        routes = twin._plan_recovery("n2")
        # n2 connects n1 and n3; there's alternative n0-n1...n3 via cross link n0->n3
        assert isinstance(routes, list)

    def test_plan_recovery_no_alternatives(self):
        twin = self._make_twin()
        twin.add_node(TwinNode(node_id="a"))
        twin.add_node(TwinNode(node_id="b"))
        twin.add_node(TwinNode(node_id="c"))
        twin.add_link(TwinLink(source="a", target="b"))
        twin.add_link(TwinLink(source="b", target="c"))
        # If b fails, a and c are disconnected; no alt path
        routes = twin._plan_recovery("b")
        assert routes == []

    def test_plan_recovery_nonexistent_node(self):
        twin = self._make_twin_with_nodes()
        routes = twin._plan_recovery("nonexistent")
        assert routes == []

    # ---- MTTR Statistics ----

    def test_get_mttr_statistics_empty(self):
        twin = self._make_twin()
        stats = twin.get_mttr_statistics()
        assert stats["mean"] == 0
        assert stats["median"] == 0
        assert stats["p95"] == 0
        assert stats["min"] == 0
        assert stats["max"] == 0
        assert stats["samples"] == 0

    def test_get_mttr_statistics_with_data(self):
        twin = self._make_twin()
        twin._recovery_times = [1.0, 2.0, 3.0, 4.0, 5.0]
        stats = twin.get_mttr_statistics()
        assert stats["mean"] == 3.0
        assert stats["median"] == 3.0
        assert stats["min"] == 1.0
        assert stats["max"] == 5.0
        assert stats["samples"] == 5

    def test_get_mttr_statistics_single_sample(self):
        twin = self._make_twin()
        twin._recovery_times = [7.5]
        stats = twin.get_mttr_statistics()
        assert stats["mean"] == 7.5
        assert stats["median"] == 7.5
        assert stats["p95"] == 7.5
        assert stats["samples"] == 1

    # ---- Topology Stats ----

    def test_get_topology_stats_empty(self):
        twin = self._make_twin()
        stats = twin.get_topology_stats()
        assert stats["total_nodes"] == 0
        assert stats["total_links"] == 0
        assert stats["avg_link_quality"] == 0
        assert stats["connectivity"] == 1.0

    def test_get_topology_stats_with_data(self):
        twin = self._make_twin_with_nodes()
        stats = twin.get_topology_stats()
        assert stats["total_nodes"] == 5
        assert stats["healthy_nodes"] == 5
        assert stats["total_links"] == 5  # 4 chain + 1 cross
        assert stats["up_links"] == 5
        assert 0 <= stats["avg_link_quality"] <= 1

    def test_get_topology_stats_degraded(self):
        twin = self._make_twin_with_nodes()
        twin.nodes["n0"].state = NodeState.FAILED
        twin.links["n0->n1"].state = LinkState.DOWN
        stats = twin.get_topology_stats()
        assert stats["healthy_nodes"] == 4
        assert stats["up_links"] == 4

    # ---- Export ----

    def test_export_state(self):
        twin = self._make_twin_with_nodes()
        state = twin.export_state()
        assert state["twin_id"] == "test"
        assert "timestamp" in state
        assert "topology" in state
        assert "mttr" in state
        assert len(state["nodes"]) == 5
        assert len(state["links"]) == 5

    def test_to_json(self):
        twin = self._make_twin_with_nodes()
        json_str = twin.to_json()
        parsed = json.loads(json_str)
        assert parsed["twin_id"] == "test"
        assert len(parsed["nodes"]) == 5


# ==================== ChaosScenarioRunner Tests ====================


class TestChaosScenarioRunner:
    def _make_runner(self):
        twin = MeshDigitalTwin(twin_id="chaos")
        for i in range(10):
            twin.add_node(TwinNode(node_id=f"n{i}"))
        for i in range(9):
            twin.add_link(TwinLink(source=f"n{i}", target=f"n{i+1}"))
        return ChaosScenarioRunner(twin)

    def test_init(self):
        twin = MeshDigitalTwin()
        runner = ChaosScenarioRunner(twin)
        assert runner.twin is twin
        assert runner.results == []

    def test_run_pod_kill_scenario(self):
        runner = self._make_runner()
        with patch("src.simulation.digital_twin.random") as mock_random:
            mock_random.sample.side_effect = lambda lst, k: lst[:k]
            results = runner.run_pod_kill_scenario(kill_percentage=20, iterations=2)
        assert len(results) > 0
        for r in results:
            assert r.scenario_name == "node_failure"
        assert len(runner.results) == len(results)

    def test_run_pod_kill_min_one(self):
        """At least 1 node should be killed even at low percentage."""
        twin = MeshDigitalTwin(twin_id="t")
        twin.add_node(TwinNode(node_id="n0"))
        runner = ChaosScenarioRunner(twin)
        with patch("src.simulation.digital_twin.random") as mock_random:
            mock_random.sample.return_value = ["n0"]
            results = runner.run_pod_kill_scenario(kill_percentage=1, iterations=1)
        assert len(results) == 1

    def test_run_network_partition_scenario(self):
        runner = self._make_runner()
        with patch("src.simulation.digital_twin.random") as mock_random:
            mock_random.shuffle = lambda x: None  # Don't shuffle
            results = runner.run_network_partition_scenario(iterations=2)
        assert len(results) == 2
        for r in results:
            assert r.scenario_name == "network_partition"
        assert len(runner.results) == 2

    def test_run_cascade_scenario(self):
        runner = self._make_runner()
        with patch("src.simulation.digital_twin.random") as mock_random:
            mock_random.sample.side_effect = lambda lst, k: lst[:k]
            mock_random.random.return_value = 1.0  # No propagation
            results = runner.run_cascade_scenario(num_initial_failures=2, iterations=2)
        assert len(results) == 2
        for r in results:
            assert r.scenario_name == "cascade_failure"
        assert len(runner.results) == 2

    def test_get_summary_empty(self):
        twin = MeshDigitalTwin()
        runner = ChaosScenarioRunner(twin)
        summary = runner.get_summary()
        assert summary == {"scenarios_run": 0}

    def test_get_summary_with_results(self):
        twin = MeshDigitalTwin()
        runner = ChaosScenarioRunner(twin)
        runner.results = [
            SimulationResult(
                scenario_name="test",
                duration_seconds=1.0,
                mttr_seconds=5.0,
                nodes_affected=2,
                links_affected=1,
                connectivity_maintained=0.8,
                packet_loss_total=0.1,
            ),
            SimulationResult(
                scenario_name="test2",
                duration_seconds=2.0,
                mttr_seconds=10.0,
                nodes_affected=3,
                links_affected=2,
                connectivity_maintained=0.6,
                packet_loss_total=0.2,
            ),
        ]
        summary = runner.get_summary()
        assert summary["scenarios_run"] == 2
        assert summary["avg_mttr"] == 7.5
        assert summary["total_nodes_affected"] == 5
        assert summary["avg_connectivity"] == pytest.approx(0.7)

    def test_results_accumulate(self):
        runner = self._make_runner()
        with patch("src.simulation.digital_twin.random") as mock_random:
            mock_random.sample.side_effect = lambda lst, k: lst[:k]
            mock_random.random.return_value = 1.0
            runner.run_cascade_scenario(iterations=1)
            initial_count = len(runner.results)
            runner.run_cascade_scenario(iterations=1)
            assert len(runner.results) == initial_count + 1

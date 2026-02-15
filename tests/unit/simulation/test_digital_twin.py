"""
Tests for Digital Twin simulation.
"""

import sys

import pytest

sys.path.insert(0, "/mnt/AC74CC2974CBF3DC")

from src.simulation.digital_twin import (ChaosScenarioRunner, LinkState,
                                         MeshDigitalTwin, NodeState, TwinLink,
                                         TwinNode)


class TestTwinNode:
    """Tests for TwinNode."""

    def test_node_creation(self):
        node = TwinNode(node_id="test-1")
        assert node.node_id == "test-1"
        assert node.state == NodeState.HEALTHY

    def test_node_state_history(self):
        node = TwinNode(node_id="test-1")
        node.cpu_usage = 50.0
        node.record_state()

        assert len(node.state_history) == 1
        assert node.state_history[0]["cpu"] == 50.0

    def test_node_to_dict(self):
        node = TwinNode(node_id="test-1", cpu_usage=30.0, memory_usage=40.0)
        d = node.to_dict()

        assert d["node_id"] == "test-1"
        assert d["cpu_usage"] == 30.0
        assert d["state"] == "healthy"


class TestTwinLink:
    """Tests for TwinLink."""

    def test_link_creation(self):
        link = TwinLink(source="a", target="b")
        assert link.link_id == "a->b"
        assert link.state == LinkState.UP

    def test_link_quality_score(self):
        # Good link
        good_link = TwinLink(
            source="a", target="b", latency_ms=10, packet_loss=0.01, rssi=-50
        )
        assert good_link.quality_score > 0.8

        # Bad link
        bad_link = TwinLink(
            source="a", target="b", latency_ms=400, packet_loss=0.3, rssi=-85
        )
        assert bad_link.quality_score < 0.5

    def test_link_to_dict(self):
        link = TwinLink(source="a", target="b", latency_ms=25)
        d = link.to_dict()

        assert d["source"] == "a"
        assert d["target"] == "b"
        assert d["latency_ms"] == 25


class TestMeshDigitalTwin:
    """Tests for MeshDigitalTwin."""

    def test_twin_creation(self):
        twin = MeshDigitalTwin(twin_id="test-twin")
        assert twin.twin_id == "test-twin"
        assert len(twin.nodes) == 0

    def test_add_node(self):
        twin = MeshDigitalTwin()
        node = TwinNode(node_id="node-1")
        twin.add_node(node)

        assert "node-1" in twin.nodes
        assert twin.graph.has_node("node-1")

    def test_add_link(self):
        twin = MeshDigitalTwin()
        twin.add_node(TwinNode(node_id="a"))
        twin.add_node(TwinNode(node_id="b"))

        link = TwinLink(source="a", target="b")
        twin.add_link(link)

        assert "a->b" in twin.links
        assert twin.graph.has_edge("a", "b")

    def test_remove_node(self):
        twin = MeshDigitalTwin()
        twin.add_node(TwinNode(node_id="a"))
        twin.add_node(TwinNode(node_id="b"))
        twin.add_link(TwinLink(source="a", target="b"))

        twin.remove_node("a")

        assert "a" not in twin.nodes
        assert not twin.graph.has_node("a")

    def test_create_test_topology(self):
        twin = MeshDigitalTwin()
        twin.create_test_topology(num_nodes=10, connectivity=0.5)

        assert len(twin.nodes) == 10
        assert len(twin.links) > 0  # Should have some links

    def test_topology_stats(self):
        twin = MeshDigitalTwin()
        twin.create_test_topology(num_nodes=5, connectivity=0.8)

        stats = twin.get_topology_stats()

        assert stats["total_nodes"] == 5
        assert stats["healthy_nodes"] == 5
        assert stats["connectivity"] == 1.0

    def test_export_state(self):
        twin = MeshDigitalTwin(twin_id="export-test")
        twin.create_test_topology(num_nodes=3, connectivity=1.0)

        state = twin.export_state()

        assert state["twin_id"] == "export-test"
        assert len(state["nodes"]) == 3
        assert "topology" in state
        assert "mttr" in state


class TestLinksAffectedCalculation:
    """Tests for links_affected calculation."""

    def test_calculate_links_affected_single_node(self):
        """Test calculation for single node failure."""
        twin = MeshDigitalTwin()
        # Create a simple topology: A-B-C (linear)
        twin.add_node(TwinNode(node_id="A"))
        twin.add_node(TwinNode(node_id="B"))
        twin.add_node(TwinNode(node_id="C"))
        twin.add_link(TwinLink(source="A", target="B"))
        twin.add_link(TwinLink(source="B", target="C"))

        # Fail node B (should affect 2 links: A-B and B-C)
        links_affected = twin._calculate_links_affected(
            {"B"}, consider_bidirectional=True
        )
        assert links_affected == 2

    def test_calculate_links_affected_multiple_nodes(self):
        """Test calculation for multiple node failures."""
        twin = MeshDigitalTwin()
        # Create topology: A-B-C-D (linear)
        twin.add_node(TwinNode(node_id="A"))
        twin.add_node(TwinNode(node_id="B"))
        twin.add_node(TwinNode(node_id="C"))
        twin.add_node(TwinNode(node_id="D"))
        twin.add_link(TwinLink(source="A", target="B"))
        twin.add_link(TwinLink(source="B", target="C"))
        twin.add_link(TwinLink(source="C", target="D"))

        # Fail nodes B and C (should affect 3 links: A-B, B-C, C-D)
        links_affected = twin._calculate_links_affected(
            {"B", "C"}, consider_bidirectional=True
        )
        assert links_affected == 3

    def test_calculate_links_affected_bidirectional(self):
        """Test bidirectional link handling."""
        twin = MeshDigitalTwin()
        # Create topology: A-B (single link)
        twin.add_node(TwinNode(node_id="A"))
        twin.add_node(TwinNode(node_id="B"))
        twin.add_link(TwinLink(source="A", target="B"))

        # With bidirectional=True, should count link once
        links_affected = twin._calculate_links_affected(
            {"A"}, consider_bidirectional=True
        )
        assert links_affected == 1

        # With bidirectional=False, should still count once (only one link exists)
        links_affected = twin._calculate_links_affected(
            {"A"}, consider_bidirectional=False
        )
        assert links_affected == 1

    def test_calculate_links_affected_star_topology(self):
        """Test calculation for star topology."""
        twin = MeshDigitalTwin()
        # Create star: center node connected to 5 others
        center = "center"
        twin.add_node(TwinNode(node_id=center))
        for i in range(5):
            node_id = f"node_{i}"
            twin.add_node(TwinNode(node_id=node_id))
            twin.add_link(TwinLink(source=center, target=node_id))

        # Fail center node (should affect all 5 links)
        links_affected = twin._calculate_links_affected(
            {center}, consider_bidirectional=True
        )
        assert links_affected == 5

    def test_calculate_links_affected_by_partition(self):
        """Test calculation for network partition."""
        twin = MeshDigitalTwin()
        # Create topology: A-B-C-D (linear, partition between B and C)
        twin.add_node(TwinNode(node_id="A"))
        twin.add_node(TwinNode(node_id="B"))
        twin.add_node(TwinNode(node_id="C"))
        twin.add_node(TwinNode(node_id="D"))
        twin.add_link(TwinLink(source="A", target="B"))
        twin.add_link(TwinLink(source="B", target="C"))
        twin.add_link(TwinLink(source="C", target="D"))

        # Partition: group_a={A,B}, group_b={C,D}
        # Should affect 1 link: B-C
        links_affected = twin._calculate_links_affected_by_partition(
            {"A", "B"}, {"C", "D"}
        )
        assert links_affected == 1

    def test_calculate_links_affected_empty(self):
        """Test calculation with no failed nodes."""
        twin = MeshDigitalTwin()
        twin.create_test_topology(num_nodes=5, connectivity=0.8)

        links_affected = twin._calculate_links_affected(
            set(), consider_bidirectional=True
        )
        assert links_affected == 0

    def test_calculate_links_affected_nonexistent_node(self):
        """Test calculation with nonexistent node."""
        twin = MeshDigitalTwin()
        twin.create_test_topology(num_nodes=5, connectivity=0.8)

        # Should not crash, just return 0
        links_affected = twin._calculate_links_affected(
            {"nonexistent"}, consider_bidirectional=True
        )
        assert links_affected == 0


class TestNodeFailureSimulation:
    """Tests for node failure simulation."""

    def test_simulate_node_failure(self):
        twin = MeshDigitalTwin()
        twin.create_test_topology(num_nodes=5, connectivity=0.8)

        node_id = list(twin.nodes.keys())[0]
        result = twin.simulate_node_failure(node_id)

        assert result.scenario_name == "node_failure"
        assert result.nodes_affected == 1
        assert result.links_affected > 0  # Should have affected links
        assert result.mttr_seconds > 0
        assert len(result.events) > 0

    def test_failure_recovery(self):
        twin = MeshDigitalTwin()
        twin.create_test_topology(num_nodes=5, connectivity=0.8)

        node_id = list(twin.nodes.keys())[0]
        twin.simulate_node_failure(node_id)

        # Node should recover
        assert twin.nodes[node_id].state == NodeState.HEALTHY

    def test_nonexistent_node_failure(self):
        twin = MeshDigitalTwin()
        result = twin.simulate_node_failure("nonexistent")

        assert result.nodes_affected == 0
        assert "error" in result.events[0]


class TestNetworkPartition:
    """Tests for network partition simulation."""

    def test_simulate_partition(self):
        twin = MeshDigitalTwin()
        twin.create_test_topology(num_nodes=6, connectivity=0.8)

        nodes = list(twin.nodes.keys())
        group_a = nodes[:3]
        group_b = nodes[3:]

        result = twin.simulate_network_partition(group_a, group_b)

        assert result.scenario_name == "network_partition"
        assert result.nodes_affected == 6
        assert (
            result.links_affected > 0
        )  # Should have affected links between partitions
        assert result.mttr_seconds > 0

    def test_partition_heals(self):
        twin = MeshDigitalTwin()
        twin.create_test_topology(num_nodes=4, connectivity=1.0)

        nodes = list(twin.nodes.keys())
        twin.simulate_network_partition(nodes[:2], nodes[2:])

        # All links should be back up
        up_links = sum(1 for l in twin.links.values() if l.state == LinkState.UP)
        assert up_links == len(twin.links)


class TestCascadeFailure:
    """Tests for cascade failure simulation."""

    def test_simulate_cascade(self):
        twin = MeshDigitalTwin()
        twin.create_test_topology(num_nodes=10, connectivity=0.5)

        initial = list(twin.nodes.keys())[:2]
        result = twin.simulate_cascade_failure(initial, propagation_probability=0.5)

        assert result.scenario_name == "cascade_failure"
        assert result.nodes_affected >= 2  # At least initial failures
        assert result.links_affected > 0  # Should have affected links

    def test_cascade_recovery(self):
        twin = MeshDigitalTwin()
        twin.create_test_topology(num_nodes=5, connectivity=0.8)

        initial = [list(twin.nodes.keys())[0]]
        twin.simulate_cascade_failure(initial, propagation_probability=0.3)

        # All nodes should recover
        healthy = sum(1 for n in twin.nodes.values() if n.state == NodeState.HEALTHY)
        assert healthy == len(twin.nodes)


class TestChaosScenarioRunner:
    """Tests for ChaosScenarioRunner."""

    def test_runner_creation(self):
        twin = MeshDigitalTwin()
        runner = ChaosScenarioRunner(twin)

        assert runner.twin == twin
        assert len(runner.results) == 0

    def test_pod_kill_scenario(self):
        twin = MeshDigitalTwin()
        twin.create_test_topology(num_nodes=10, connectivity=0.5)

        runner = ChaosScenarioRunner(twin)
        results = runner.run_pod_kill_scenario(kill_percentage=20, iterations=3)

        assert len(results) > 0
        assert all(r.scenario_name == "node_failure" for r in results)

    def test_partition_scenario(self):
        twin = MeshDigitalTwin()
        twin.create_test_topology(num_nodes=8, connectivity=0.6)

        runner = ChaosScenarioRunner(twin)
        results = runner.run_network_partition_scenario(iterations=2)

        assert len(results) == 2
        assert all(r.scenario_name == "network_partition" for r in results)

    def test_cascade_scenario(self):
        twin = MeshDigitalTwin()
        twin.create_test_topology(num_nodes=10, connectivity=0.5)

        runner = ChaosScenarioRunner(twin)
        results = runner.run_cascade_scenario(num_initial_failures=2, iterations=2)

        assert len(results) == 2
        assert all(r.scenario_name == "cascade_failure" for r in results)

    def test_runner_summary(self):
        twin = MeshDigitalTwin()
        twin.create_test_topology(num_nodes=10, connectivity=0.5)

        runner = ChaosScenarioRunner(twin)
        runner.run_pod_kill_scenario(iterations=5)
        runner.run_network_partition_scenario(iterations=3)

        summary = runner.get_summary()

        assert summary["scenarios_run"] > 0
        assert "avg_mttr" in summary
        assert "p95_mttr" in summary


class TestMTTRStatistics:
    """Tests for MTTR statistics."""

    def test_mttr_tracking(self):
        twin = MeshDigitalTwin()
        twin.create_test_topology(num_nodes=5, connectivity=0.8)

        # Run multiple simulations
        for node_id in list(twin.nodes.keys())[:3]:
            twin.simulate_node_failure(node_id)

        stats = twin.get_mttr_statistics()

        assert stats["samples"] == 3
        assert stats["mean"] > 0
        assert stats["p95"] >= stats["mean"]

    def test_empty_mttr_stats(self):
        twin = MeshDigitalTwin()
        stats = twin.get_mttr_statistics()

        assert stats["samples"] == 0
        assert stats["mean"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

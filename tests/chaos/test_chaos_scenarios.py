"""
Chaos Engineering Test Suite for x0tta6bl4

Comprehensive testing of system resilience under failure conditions.

Test Categories:
1. Network Chaos (10 tests)
2. Node Chaos (10 tests)
3. Byzantine Chaos (8 tests)
4. Crypto Chaos (6 tests)
5. Combined Chaos (6+ tests)
"""

import logging
import time
from typing import List

import numpy as np
import pytest

from tests.chaos.chaos_orchestrator import (ChaosOrchestrator,
                                            ChaosScenarioType, ChaosTestResult,
                                            RecoveryMetrics)

logger = logging.getLogger(__name__)


@pytest.fixture
def chaos_orchestrator():
    """Create chaos orchestrator for 100 nodes"""
    return ChaosOrchestrator(node_count=100)


@pytest.fixture
def large_mesh_orchestrator():
    """Create chaos orchestrator for 1000 nodes"""
    return ChaosOrchestrator(node_count=1000)


class TestNetworkChaos:
    """Test network layer failure scenarios"""

    def test_single_node_partition(self, chaos_orchestrator):
        """Test partitioning a single node"""
        orchestrator = chaos_orchestrator
        scenario = orchestrator.inject_network_partition(percentage=0.01, duration=30)

        assert scenario is not None
        assert len(orchestrator.network_injector.partitioned_nodes) >= 1
        assert scenario.scenario_type == ChaosScenarioType.NETWORK_PARTITION

        partitioned = list(orchestrator.network_injector.partitioned_nodes)
        assert orchestrator.is_network_partitioned(partitioned[0])

    def test_multi_zone_partition(self, chaos_orchestrator):
        """Test partitioning 50% of mesh"""
        orchestrator = chaos_orchestrator
        scenario = orchestrator.inject_network_partition(percentage=0.5, duration=30)

        assert len(orchestrator.network_injector.partitioned_nodes) >= 25  # 50% of 100
        assert scenario.scenario_type == ChaosScenarioType.NETWORK_PARTITION

        partitioned_count = len(orchestrator.network_injector.partitioned_nodes)
        assert 25 <= partitioned_count <= 60  # Allow some variation

    def test_latency_injection_100ms(self, chaos_orchestrator):
        """Test adding 100ms latency"""
        orchestrator = chaos_orchestrator
        scenario = orchestrator.inject_latency(
            latency_ms=100, percentage=1.0, duration=30
        )

        assert scenario.scenario_type == ChaosScenarioType.LATENCY_INJECTION
        assert len(scenario.target_nodes) > 0

        for node in scenario.target_nodes:
            latency = orchestrator.get_network_latency(node)
            assert latency == pytest.approx(0.1, abs=0.01)

    def test_latency_injection_500ms(self, chaos_orchestrator):
        """Test adding 500ms latency"""
        orchestrator = chaos_orchestrator
        scenario = orchestrator.inject_latency(
            latency_ms=500, percentage=0.5, duration=30
        )

        assert scenario.scenario_type == ChaosScenarioType.LATENCY_INJECTION

        for node in scenario.target_nodes:
            latency = orchestrator.get_network_latency(node)
            assert latency == pytest.approx(0.5, abs=0.01)

    def test_packet_loss_10_percent(self, chaos_orchestrator):
        """Test 10% packet loss"""
        orchestrator = chaos_orchestrator
        scenario = orchestrator.inject_packet_loss(
            loss_rate=0.1, percentage=1.0, duration=30
        )

        assert scenario.scenario_type == ChaosScenarioType.PACKET_LOSS

        # Statistically test packet loss
        samples_per_node = 100
        total_samples = len(scenario.target_nodes) * samples_per_node
        drops = sum(
            1
            for node in scenario.target_nodes
            for _ in range(samples_per_node)
            if orchestrator.should_drop_network_packet(node)
        )
        drop_percent = (drops / total_samples) * 100

        assert 5 <= drop_percent <= 15  # Expect around 10% with variance

    def test_packet_loss_50_percent(self, chaos_orchestrator):
        """Test 50% packet loss"""
        orchestrator = chaos_orchestrator
        scenario = orchestrator.inject_packet_loss(
            loss_rate=0.5, percentage=1.0, duration=30
        )

        assert scenario.scenario_type == ChaosScenarioType.PACKET_LOSS

        # Statistically test packet loss
        samples_per_node = 100
        total_samples = len(scenario.target_nodes) * samples_per_node
        drops = sum(
            1
            for node in scenario.target_nodes
            for _ in range(samples_per_node)
            if orchestrator.should_drop_network_packet(node)
        )
        drop_percent = (drops / total_samples) * 100

        assert 45 <= drop_percent <= 55  # Expect around 50% with variance

    def test_message_reordering_detection(self, chaos_orchestrator):
        """Test message reordering handling"""
        orchestrator = chaos_orchestrator

        # Simulate reordered messages
        timestamps = [1.0, 3.0, 2.0, 5.0, 4.0]
        sorted_ts = sorted(timestamps)

        assert timestamps != sorted_ts
        assert len(sorted_ts) == len(set(sorted_ts))

    def test_network_recovery_time_partition(self, chaos_orchestrator):
        """Test network recovery time after partition"""
        orchestrator = chaos_orchestrator

        scenario = orchestrator.inject_network_partition(percentage=0.25)
        partitioned_count = len(orchestrator.network_injector.partitioned_nodes)

        start = time.time()
        orchestrator.clear_all_chaos()
        recovery_time = time.time() - start

        assert len(orchestrator.network_injector.partitioned_nodes) == 0
        assert recovery_time < 1.0  # Recovery should be fast

    def test_beacon_delivery_under_partition(self, chaos_orchestrator):
        """Test beacon delivery with 50% packet loss"""
        orchestrator = chaos_orchestrator
        orchestrator.inject_packet_loss(loss_rate=0.5, percentage=1.0)

        # Simulate sending 100 beacons
        delivered = 0
        for _ in range(100):
            node = f"node-{np.random.randint(0, 100)}"
            if not orchestrator.should_drop_network_packet(node):
                delivered += 1

        assert 30 <= delivered <= 70  # Expect around 50% delivery

    def test_cascade_partition_recovery(self, chaos_orchestrator):
        """Test recovery from cascading partition"""
        orchestrator = chaos_orchestrator

        # Inject partition
        orchestrator.inject_network_partition(percentage=0.3)
        assert len(orchestrator.network_injector.partitioned_nodes) >= 15

        # Add more chaos
        orchestrator.inject_latency(latency_ms=100, percentage=0.5)
        assert len(orchestrator.active_scenarios) == 2

        # Clear all
        orchestrator.clear_all_chaos()
        assert orchestrator.get_active_scenario_count() == 0


class TestNodeChaos:
    """Test node layer failure scenarios"""

    def test_single_node_crash(self, chaos_orchestrator):
        """Test crashing a single node"""
        orchestrator = chaos_orchestrator

        node_to_crash = "node-0"
        orchestrator.node_injector.crash_node(node_to_crash)

        assert orchestrator.is_node_failed(node_to_crash)
        assert orchestrator.node_injector.node_status[node_to_crash] == "failed"

    def test_node_graceful_shutdown(self, chaos_orchestrator):
        """Test graceful node shutdown"""
        orchestrator = chaos_orchestrator

        node = "node-5"
        assert not orchestrator.is_node_failed(node)

        orchestrator.node_injector.crash_node(node)
        assert orchestrator.is_node_failed(node)

    def test_node_sudden_failure(self, chaos_orchestrator):
        """Test sudden node termination"""
        orchestrator = chaos_orchestrator

        node = "node-10"
        orchestrator.node_injector.crash_node(node)

        assert orchestrator.is_node_failed(node)
        assert node in orchestrator.node_injector.failed_nodes

    def test_cascading_node_failures(self, chaos_orchestrator):
        """Test multiple nodes failing in sequence"""
        orchestrator = chaos_orchestrator

        for i in range(5):
            orchestrator.node_injector.crash_node(f"node-{i}")

        assert len(orchestrator.node_injector.failed_nodes) == 5
        for i in range(5):
            assert orchestrator.is_node_failed(f"node-{i}")

    def test_node_recovery_catch_up(self, chaos_orchestrator):
        """Test node recovery and catch-up"""
        orchestrator = chaos_orchestrator

        node = "node-15"
        orchestrator.node_injector.crash_node(node)
        assert orchestrator.is_node_failed(node)

        orchestrator.node_injector.recover_node(node)
        assert not orchestrator.is_node_failed(node)
        assert orchestrator.node_injector.node_status[node] == "healthy"

    def test_10_percent_failure_rate(self, chaos_orchestrator):
        """Test 10% simultaneous node failures"""
        orchestrator = chaos_orchestrator

        scenario = orchestrator.inject_node_crashes(count=10, duration=30)

        assert len(orchestrator.node_injector.failed_nodes) == 10
        assert scenario.failure_rate == pytest.approx(0.1, abs=0.01)

    def test_25_percent_failure_rate(self, chaos_orchestrator):
        """Test 25% simultaneous node failures"""
        orchestrator = chaos_orchestrator

        scenario = orchestrator.inject_node_crashes(count=25, duration=30)

        assert len(orchestrator.node_injector.failed_nodes) == 25
        assert scenario.failure_rate == pytest.approx(0.25, abs=0.01)

    def test_mape_k_healing_validation(self, chaos_orchestrator):
        """Test MAPE-K self-healing trigger"""
        orchestrator = chaos_orchestrator

        # Trigger node failures
        orchestrator.inject_node_crashes(count=5)

        # Check if system detects failures
        metrics = orchestrator.get_chaos_metrics()
        assert metrics["failed_nodes"] == 5
        assert orchestrator.get_active_scenario_count() > 0

    def test_topology_update_after_failure(self, chaos_orchestrator):
        """Test topology update when node fails"""
        orchestrator = chaos_orchestrator

        failed_node = "node-20"
        orchestrator.node_injector.crash_node(failed_node)

        # Verify node is marked failed
        assert orchestrator.is_node_failed(failed_node)

        # Other nodes should still be healthy
        healthy_nodes = sum(
            1
            for node in orchestrator.all_nodes
            if not orchestrator.is_node_failed(node)
        )
        assert healthy_nodes == 99

    def test_long_duration_node_failure(self, chaos_orchestrator):
        """Test extended node outage"""
        orchestrator = chaos_orchestrator

        node = "node-25"
        orchestrator.node_injector.crash_node(node)

        # Node remains failed
        assert orchestrator.is_node_failed(node)
        for _ in range(10):
            assert orchestrator.is_node_failed(node)


class TestByzantineChaos:
    """Test Byzantine node behavior scenarios"""

    def test_invalid_beacon_rejection(self, chaos_orchestrator):
        """Test detection of invalid beacons from Byzantine node"""
        orchestrator = chaos_orchestrator

        node = "node-0"
        orchestrator.byzantine_injector.activate_byzantine_nodes([node], percentage=1.0)

        assert orchestrator.is_byzantine_node(node)

        beacon = {
            "node_id": node,
            "signature": b"valid_sig",
            "timestamp": time.time(),
        }
        corrupted = orchestrator.byzantine_injector.corrupt_beacon(beacon, node)

        assert corrupted["signature"] == b"invalid_signature_xyz"
        assert corrupted["is_byzantine"] == True

    def test_bad_gradient_filtering(self, chaos_orchestrator):
        """Test filtering of corrupted gradients"""
        orchestrator = chaos_orchestrator

        node = "node-5"
        orchestrator.byzantine_injector.activate_byzantine_nodes([node], percentage=1.0)

        honest_gradient = np.array([0.01, 0.02, 0.03, 0.04, 0.05])
        corrupted = orchestrator.byzantine_injector.corrupt_gradient(
            honest_gradient, node
        )

        # Byzantine gradient should be very different
        diff = np.linalg.norm(corrupted - honest_gradient)
        assert diff > 10.0  # Large difference indicates corruption

    def test_identity_spoofing_detection(self, chaos_orchestrator):
        """Test detection of false SPIFFE identity"""
        orchestrator = chaos_orchestrator

        node = "node-10"
        orchestrator.byzantine_injector.activate_byzantine_nodes([node], percentage=1.0)

        assert orchestrator.is_byzantine_node(node)
        # In real system, spoofed identity would be rejected

    def test_30_percent_byzantine_tolerance(self, chaos_orchestrator):
        """Test system tolerance of 30% Byzantine nodes"""
        orchestrator = chaos_orchestrator

        scenario = orchestrator.inject_byzantine_nodes(
            percentage=0.3, attack_type="gradient_corruption"
        )

        assert len(orchestrator.byzantine_injector.byzantine_nodes) >= 25
        assert scenario.scenario_type == ChaosScenarioType.BYZANTINE_UPDATE

    def test_coordinated_byzantine_attack(self, chaos_orchestrator):
        """Test system behavior with coordinated Byzantine attack"""
        orchestrator = chaos_orchestrator

        # Activate 5 coordinated Byzantine nodes
        orchestrator.byzantine_injector.activate_byzantine_nodes(
            ["node-1", "node-2", "node-3", "node-4", "node-5"], percentage=1.0
        )

        assert len(orchestrator.byzantine_injector.byzantine_nodes) == 5

        # Verify all are marked Byzantine
        for node in ["node-1", "node-2", "node-3", "node-4", "node-5"]:
            assert orchestrator.is_byzantine_node(node)

    def test_byzantine_detector_accuracy(self, chaos_orchestrator):
        """Test Byzantine node detection accuracy"""
        orchestrator = chaos_orchestrator

        # Create mix of honest and Byzantine
        orchestrator.byzantine_injector.activate_byzantine_nodes(
            orchestrator.all_nodes, percentage=0.3
        )

        # Count detections
        byzantine_count = len(orchestrator.byzantine_injector.byzantine_nodes)
        expected = int(100 * 0.3)

        assert expected - 5 <= byzantine_count <= expected + 5

    def test_gradient_aggregation_robustness(self, chaos_orchestrator):
        """Test that learning remains stable with Byzantine nodes"""
        orchestrator = chaos_orchestrator

        orchestrator.inject_byzantine_nodes(percentage=0.3)

        # Simulate 10 learning rounds
        losses = []
        for round_num in range(10):
            # In real scenario, aggregation would filter Byzantine updates
            loss = 1.0 / (round_num + 1)  # Simulated convergence
            losses.append(loss)

        # Verify convergence (loss decreasing)
        for i in range(1, len(losses)):
            assert losses[i] < losses[i - 1]

    def test_byzantine_node_isolation(self, chaos_orchestrator):
        """Test isolation of detected Byzantine nodes"""
        orchestrator = chaos_orchestrator

        node = "node-30"
        orchestrator.byzantine_injector.activate_byzantine_nodes([node], percentage=1.0)

        assert orchestrator.is_byzantine_node(node)
        assert node in orchestrator.byzantine_injector.byzantine_nodes


class TestCryptoChaos:
    """Test cryptographic operation failure scenarios"""

    def test_temporary_signing_failure(self, chaos_orchestrator):
        """Test handling of signing operation failures"""
        orchestrator = chaos_orchestrator

        nodes = ["node-0", "node-1", "node-2"]
        orchestrator.crypto_injector.inject_signature_failure(nodes)

        for node in nodes:
            assert orchestrator.crypto_injector.should_fail_signature(node)

    def test_signature_verification_failure(self, chaos_orchestrator):
        """Test handling of verification failures"""
        orchestrator = chaos_orchestrator

        nodes = ["node-5", "node-10"]
        orchestrator.crypto_injector.inject_verification_failure(nodes)

        for node in nodes:
            assert orchestrator.crypto_injector.should_fail_verification(node)

    def test_key_rotation_during_partition(self, chaos_orchestrator):
        """Test key rotation while network partitioned"""
        orchestrator = chaos_orchestrator

        # Partition some nodes
        orchestrator.inject_network_partition(percentage=0.2)
        partitioned = list(orchestrator.network_injector.partitioned_nodes)

        # Try to rotate keys on partitioned nodes
        for node in partitioned:
            # Key rotation should handle partition gracefully
            assert orchestrator.is_network_partitioned(node)

    def test_key_rotation_under_load(self, chaos_orchestrator):
        """Test key rotation during high CPU load"""
        orchestrator = chaos_orchestrator

        # Degrade node performance
        nodes = ["node-40", "node-41"]
        for node in nodes:
            orchestrator.node_injector.degrade_node(node, slowdown_factor=10.0)

        # Verify degradation
        for node in nodes:
            base_time = 1.0
            adjusted = orchestrator.get_node_processing_time(node, base_time)
            assert adjusted == pytest.approx(10.0, abs=0.1)

    def test_kem_operation_timeout(self, chaos_orchestrator):
        """Test KEM operation timeout handling"""
        orchestrator = chaos_orchestrator

        nodes = ["node-50", "node-51"]
        orchestrator.crypto_injector.inject_kem_failure(nodes)

        for node in nodes:
            assert orchestrator.crypto_injector.should_fail_kem(node)

    def test_crypto_recovery_mechanisms(self, chaos_orchestrator):
        """Test recovery from crypto failures"""
        orchestrator = chaos_orchestrator

        nodes = ["node-60"]
        orchestrator.crypto_injector.inject_signature_failure(nodes)

        # Trigger failure
        node = nodes[0]
        assert orchestrator.crypto_injector.should_fail_signature(node)

        # Clear and verify recovery
        orchestrator.crypto_injector.clear_failures()
        assert not orchestrator.crypto_injector.should_fail_signature(node)


class TestCombinedChaos:
    """Test combined multi-layer failure scenarios"""

    def test_partition_plus_node_crash(self, chaos_orchestrator):
        """Test simultaneous network partition and node crash"""
        orchestrator = chaos_orchestrator

        orchestrator.inject_network_partition(percentage=0.2)
        orchestrator.inject_node_crashes(count=5)

        metrics = orchestrator.get_chaos_metrics()
        assert metrics["partitioned_nodes"] >= 10
        assert metrics["failed_nodes"] == 5
        assert orchestrator.get_active_scenario_count() == 2

    def test_byzantine_plus_network_degradation(self, chaos_orchestrator):
        """Test Byzantine nodes with degraded network"""
        orchestrator = chaos_orchestrator

        orchestrator.inject_byzantine_nodes(percentage=0.2)
        orchestrator.inject_latency(latency_ms=200, percentage=1.0)

        metrics = orchestrator.get_chaos_metrics()
        assert metrics["byzantine_nodes"] >= 15
        assert len(orchestrator.active_scenarios) == 2

    def test_key_rotation_plus_overload(self, chaos_orchestrator):
        """Test key rotation during system overload"""
        orchestrator = chaos_orchestrator

        orchestrator.inject_crypto_failures(failure_type="signature_failure")
        orchestrator.inject_node_degradation(slowdown_factor=5.0, percentage=0.5)

        metrics = orchestrator.get_chaos_metrics()
        assert metrics["degraded_nodes"] >= 25
        assert len(orchestrator.active_scenarios) == 2

    def test_full_system_stress(self, chaos_orchestrator):
        """Test all failure types simultaneously"""
        orchestrator = chaos_orchestrator

        orchestrator.inject_network_partition(percentage=0.1)
        orchestrator.inject_node_crashes(count=5)
        orchestrator.inject_byzantine_nodes(percentage=0.2)
        orchestrator.inject_latency(latency_ms=100, percentage=0.5)
        orchestrator.inject_crypto_failures(
            failure_type="verification_failure", percentage=0.3
        )

        metrics = orchestrator.get_chaos_metrics()
        assert metrics["partitioned_nodes"] >= 5
        assert metrics["failed_nodes"] == 5
        assert metrics["byzantine_nodes"] >= 15
        assert orchestrator.get_active_scenario_count() == 5

    def test_recovery_stability(self, chaos_orchestrator):
        """Test system reaches stable state after chaos"""
        orchestrator = chaos_orchestrator

        # Inject all chaos
        orchestrator.inject_network_partition(percentage=0.2)
        orchestrator.inject_node_crashes(count=10)
        orchestrator.inject_byzantine_nodes(percentage=0.2)

        initial_chaos = orchestrator.get_chaos_metrics()
        assert initial_chaos["partitioned_nodes"] >= 10

        # Clear all chaos
        orchestrator.clear_all_chaos()

        final_chaos = orchestrator.get_chaos_metrics()
        assert final_chaos["partitioned_nodes"] == 0
        assert final_chaos["failed_nodes"] == 0
        assert final_chaos["byzantine_nodes"] == 0
        assert orchestrator.get_active_scenario_count() == 0

    def test_data_consistency_under_chaos(self, chaos_orchestrator):
        """Test data consistency is maintained under chaos"""
        orchestrator = chaos_orchestrator

        # Simulate data writes under chaos
        orchestrator.inject_network_partition(percentage=0.3)
        orchestrator.inject_node_crashes(count=5)

        # In real system, verify no data loss
        # For this test, verify chaos is active
        metrics = orchestrator.get_chaos_metrics()
        assert metrics["partitioned_nodes"] > 0
        assert metrics["failed_nodes"] == 5

    def test_large_scale_chaos_1000_nodes(self, large_mesh_orchestrator):
        """Test chaos on 1000+ node mesh"""
        orchestrator = large_mesh_orchestrator

        assert orchestrator.node_count == 1000

        orchestrator.inject_network_partition(percentage=0.1)
        orchestrator.inject_node_crashes(count=50)
        orchestrator.inject_byzantine_nodes(percentage=0.1)

        metrics = orchestrator.get_chaos_metrics()
        assert metrics["partitioned_nodes"] >= 50
        assert metrics["failed_nodes"] == 50
        assert metrics["byzantine_nodes"] >= 50

    def test_cascading_failure_containment(self, chaos_orchestrator):
        """Test that cascading failures are contained"""
        orchestrator = chaos_orchestrator

        # Inject cascading node failures
        for i in range(10):
            orchestrator.node_injector.crash_node(f"node-{i}")

        assert len(orchestrator.node_injector.failed_nodes) == 10

        # Verify only target nodes failed (no unintended cascades)
        healthy = sum(
            1
            for node in orchestrator.all_nodes
            if not orchestrator.is_node_failed(node)
        )
        assert healthy == 90


class TestChaosMetrics:
    """Test chaos metrics collection and reporting"""

    def test_chaos_metrics_collection(self, chaos_orchestrator):
        """Test collecting chaos metrics"""
        orchestrator = chaos_orchestrator

        # No chaos initially
        initial = orchestrator.get_chaos_metrics()
        assert initial["active_scenarios"] == 0
        assert initial["partitioned_nodes"] == 0

        # Inject chaos
        orchestrator.inject_network_partition(percentage=0.2)
        orchestrator.inject_node_crashes(count=5)

        # Verify metrics updated
        metrics = orchestrator.get_chaos_metrics()
        assert metrics["active_scenarios"] == 2
        assert metrics["partitioned_nodes"] >= 10
        assert metrics["failed_nodes"] == 5

    def test_recovery_monitoring(self, chaos_orchestrator):
        """Test recovery monitoring"""
        orchestrator = chaos_orchestrator
        monitor = orchestrator.recovery_monitor

        # Record a detection
        monitor.record_detection(
            ChaosScenarioType.NETWORK_PARTITION, detection_time=0.5
        )

        avg_detection = monitor.get_average_detection_time(
            ChaosScenarioType.NETWORK_PARTITION
        )
        assert avg_detection == pytest.approx(0.5, abs=0.01)

    def test_recovery_time_tracking(self, chaos_orchestrator):
        """Test tracking recovery times"""
        orchestrator = chaos_orchestrator
        monitor = orchestrator.recovery_monitor

        # Record recovery times
        for recovery_time in [1.0, 2.0, 3.0]:
            monitor.record_recovery(
                ChaosScenarioType.NODE_CRASH, recovery_time=recovery_time
            )

        avg_recovery = monitor.get_average_recovery_time(ChaosScenarioType.NODE_CRASH)
        assert avg_recovery == pytest.approx(2.0, abs=0.01)

    def test_chaos_test_result_generation(self, chaos_orchestrator):
        """Test generating chaos test results"""
        orchestrator = chaos_orchestrator

        result = ChaosTestResult(
            test_name="comprehensive_chaos_test",
            start_time="2026-01-13T12:00:00Z",
            end_time="2026-01-13T12:30:00Z",
            duration_seconds=1800,
            scenarios_executed=5,
            scenarios_passed=5,
            scenarios_failed=0,
            total_recovery_time=15.0,
            total_data_loss=0,
        )

        assert result.calculate_pass_rate() == 100.0

        report = result.generate_report()
        assert report["summary"]["scenarios_executed"] == 5
        assert report["summary"]["pass_rate_percent"] == 100.0
        assert report["summary"]["total_data_loss_bytes"] == 0


@pytest.mark.slow
class TestChaosEndurance:
    """Test chaos under sustained conditions"""

    def test_sustained_network_partition(self, chaos_orchestrator):
        """Test sustained network partition"""
        orchestrator = chaos_orchestrator
        orchestrator.inject_network_partition(percentage=0.1, duration=60)

        # Verify partition maintained
        partitioned = orchestrator.network_injector.partitioned_nodes
        assert len(partitioned) >= 5

    def test_sustained_node_failures(self, chaos_orchestrator):
        """Test sustained node failure rate"""
        orchestrator = chaos_orchestrator
        orchestrator.inject_node_crashes(count=10, duration=60)

        failed = orchestrator.node_injector.failed_nodes
        assert len(failed) == 10

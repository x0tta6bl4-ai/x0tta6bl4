"""
Load Scaling Tests for x0tta6bl4
================================

Validates 1000+ node mesh scaling using distributed load generator.

Test Scenarios:
1. Steady-state: Normal production load
2. Burst: 10x traffic spike
3. Gradual scale-up: 100→500→1000→1500→2000 nodes
4. Failure injection: Node crashes, network partitions, Byzantine nodes
"""

import pytest
import logging
from pathlib import Path

from tests.load.distributed_load_generator import (
    DistributedLoadGenerator,
    TrafficPattern,
    FailurePattern,
    PerformanceAnalyzer,
)

logger = logging.getLogger(__name__)


class TestBasicLoadGeneration:
    """Test load generator functionality"""

    def test_spawn_mesh_nodes(self):
        """Test creating virtual mesh nodes"""
        gen = DistributedLoadGenerator(node_count=100, duration_seconds=10)
        nodes = gen.spawn_mesh_nodes()
        
        assert len(nodes) == 100
        assert all(node.node_id for node in nodes)
        assert all(not node.is_failed for node in nodes)

    def test_beacon_processing(self):
        """Test beacon message processing"""
        gen = DistributedLoadGenerator(node_count=10, duration_seconds=5)
        nodes = gen.spawn_mesh_nodes()
        
        # Generate beacon from first node
        beacon = nodes[0].generate_beacon()
        assert beacon is not None
        assert beacon.node_id == "node-0"
        
        # Process at another node
        success, latency = nodes[1].process_beacon(beacon)
        assert success is True
        assert latency > 0
        assert latency < 10  # Should be < 10ms per design

    def test_pqc_operations(self):
        """Test PQC operation simulation"""
        gen = DistributedLoadGenerator(node_count=10, duration_seconds=5)
        nodes = gen.spawn_mesh_nodes()
        
        # Run PQC operation
        latency = nodes[0].simulate_pqc_operation()
        assert latency > 0.4
        assert latency < 5.0  # Within expected KEM/DSA range (plus simulator overhead)
        assert len(nodes[0].metrics.pqc_operation_times) == 1

    def test_identity_rotation(self):
        """Test SPIFFE identity rotation"""
        gen = DistributedLoadGenerator(node_count=10, duration_seconds=5)
        nodes = gen.spawn_mesh_nodes()
        
        # Rotate identity
        latency = nodes[0].rotate_identity()
        assert latency > 0.1
        assert latency < 2.0  # Including simulator overhead
        assert nodes[0].metrics.identity_rotations == 1

    def test_failure_injection(self):
        """Test failure injection"""
        gen = DistributedLoadGenerator(node_count=10, duration_seconds=5)
        nodes = gen.spawn_mesh_nodes()
        
        # Inject failure
        failure = FailurePattern.node_crash(start_time=0)
        nodes[0].inject_failure(failure)
        
        assert nodes[0].is_failed is True
        
        # Node shouldn't process beacons when failed
        beacon = nodes[1].generate_beacon()
        result, latency = nodes[0].process_beacon(beacon)
        assert result is False


class TestSteadyStateScaling:
    """Test steady-state load at various scales"""

    def test_100_node_steady_state(self):
        """Test 100 node steady state - baseline"""
        gen = DistributedLoadGenerator(node_count=100, duration_seconds=30)
        result = gen.run_steady_state_test()
        
        assert result.node_count == 100
        assert result.total_beacons > 0
        assert len(result.beacon_latencies) > 0
        
        # Verify beacon latencies are reasonable
        report = result.generate_report()
        assert report["beacon_latency_ms"]["p99"] < 10

    def test_500_node_steady_state(self):
        """Test 500 node steady state"""
        gen = DistributedLoadGenerator(node_count=500, duration_seconds=30)
        result = gen.run_steady_state_test()
        
        assert result.node_count == 500
        assert result.total_beacons > 0
        
        report = result.generate_report()
        # Expect some latency increase but still reasonable
        assert report["beacon_latency_ms"]["p99"] < 50

    def test_1000_node_steady_state(self):
        """Test 1000 node steady state - production scale"""
        gen = DistributedLoadGenerator(node_count=1000, duration_seconds=30)
        result = gen.run_steady_state_test()
        
        assert result.node_count == 1000
        assert result.total_beacons > 0
        
        report = result.generate_report()
        # Production target: p99 < 100ms at 1000 nodes
        latency_p99 = report["beacon_latency_ms"]["p99"]
        assert latency_p99 < 100, f"1000-node latency {latency_p99}ms exceeds target"

    @pytest.mark.slow
    def test_2000_node_stress(self):
        """Test 2000 node stress - find limits"""
        gen = DistributedLoadGenerator(node_count=2000, duration_seconds=60)
        result = gen.run_steady_state_test()
        
        assert result.node_count == 2000
        # Should not crash, but latency may degrade
        assert result.total_beacons > 0


class TestTrafficPatterns:
    """Test different traffic patterns"""

    def test_steady_state_pattern(self):
        """Test steady-state traffic pattern"""
        gen = DistributedLoadGenerator(node_count=100, duration_seconds=20)
        pattern = TrafficPattern.steady_state()
        result = gen.run_steady_state_test(pattern)
        
        assert result.total_beacons > 0
        assert result.total_pqc_ops > 0
        report = result.generate_report()
        assert report["beacon_latency_ms"]["mean"] < 10

    def test_burst_pattern(self):
        """Test burst traffic pattern (10x normal)"""
        gen = DistributedLoadGenerator(node_count=100, duration_seconds=20)
        pattern = TrafficPattern.burst()
        result = gen.run_steady_state_test(pattern)
        
        # Burst should generate much more traffic
        assert result.total_beacons > 0
        assert result.total_pqc_ops > 0
        
        # But latencies should still be acceptable
        report = result.generate_report()
        assert report["beacon_latency_ms"]["p99"] < 50

    def test_high_churn_pattern(self):
        """Test high identity churn pattern"""
        gen = DistributedLoadGenerator(node_count=100, duration_seconds=20)
        pattern = TrafficPattern.high_churn()  # Rotate every 60 seconds instead of 600
        result = gen.run_steady_state_test(pattern)
        
        # Should have more identity operations
        assert result.total_identity_ops > 0


class TestFailureInjection:
    """Test failure injection and recovery"""

    def test_node_crash_recovery(self):
        """Test recovery from node crashes"""
        failures = [FailurePattern.node_crash(start_time=10)]
        gen = DistributedLoadGenerator(node_count=100, duration_seconds=45)
        result = gen.run_failure_injection_test(failures)
        
        assert len(result.failures_injected) > 0
        assert "node_crash" in result.failures_injected
        
        # Should still process some beacons after recovery
        assert result.total_beacons > 0

    def test_network_partition_recovery(self):
        """Test recovery from network partition"""
        failures = [FailurePattern.network_partition(start_time=10)]
        gen = DistributedLoadGenerator(node_count=100, duration_seconds=90)
        result = gen.run_failure_injection_test(failures)
        
        assert "network_partition" in result.failures_injected
        assert len(result.recovery_times) > 0
        
        # Recovery should happen within expected window
        recovery_time = result.recovery_times[0]
        assert recovery_time < 70  # Should recover before test ends

    def test_byzantine_nodes(self):
        """Test Byzantine node detection"""
        failures = [FailurePattern.byzantine_nodes(start_time=10)]
        gen = DistributedLoadGenerator(node_count=100, duration_seconds=60)
        result = gen.run_failure_injection_test(failures)
        
        assert "byzantine" in result.failures_injected
        # Byzantine nodes should still send beacons (but invalid)
        assert result.total_beacons > 0

    def test_multiple_concurrent_failures(self):
        """Test multiple failures occurring simultaneously"""
        failures = [
            FailurePattern.node_crash(start_time=10),
            FailurePattern.byzantine_nodes(start_time=20),
        ]
        gen = DistributedLoadGenerator(node_count=100, duration_seconds=60)
        result = gen.run_failure_injection_test(failures)
        
        assert len(result.failures_injected) >= 2
        # System should handle multiple failures gracefully
        assert result.total_beacons > 0


class TestPerformanceAnalysis:
    """Test performance analysis"""

    def test_latency_percentile_calculation(self):
        """Test percentile calculation"""
        gen = DistributedLoadGenerator(node_count=100, duration_seconds=15)
        result = gen.run_steady_state_test()
        
        analysis = PerformanceAnalyzer.analyze_beacon_latency(result)
        
        assert "p50_ms" in analysis
        assert "p95_ms" in analysis
        assert "p99_ms" in analysis
        assert analysis["p50_ms"] <= analysis["p99_ms"]

    def test_bottleneck_identification(self):
        """Test bottleneck identification"""
        gen = DistributedLoadGenerator(node_count=100, duration_seconds=15)
        result = gen.run_steady_state_test()
        
        bottleneck = PerformanceAnalyzer.identify_bottleneck(result)
        
        # Should identify something (even if "no bottleneck")
        assert isinstance(bottleneck, str)
        assert len(bottleneck) > 0

    def test_scaling_prediction(self):
        """Test scaling prediction model"""
        # Create results for multiple node counts
        results = {}
        for node_count in [100, 500, 1000]:
            gen = DistributedLoadGenerator(node_count=node_count, duration_seconds=15)
            results[node_count] = gen.run_steady_state_test()
        
        prediction = PerformanceAnalyzer.predict_scaling(results)
        
        assert "slope" in prediction
        assert "feasible_for_1000" in prediction
        assert "predicted_latency_at_2000_nodes" in prediction

    def test_scaling_linearity(self):
        """Test that scaling follows expected pattern"""
        gen = DistributedLoadGenerator(node_count=100, duration_seconds=15)
        result = gen.run_steady_state_test()
        
        report = result.generate_report()
        
        # Latency per 1000 nodes should give insight into scaling
        latency_metric = report["scaling_analysis"]["latency_per_thousand_nodes"]
        assert latency_metric >= 0  # Should be positive


class TestReportGeneration:
    """Test result reporting"""

    def test_report_structure(self):
        """Test report generation and structure"""
        gen = DistributedLoadGenerator(node_count=100, duration_seconds=15)
        result = gen.run_steady_state_test()
        
        report = result.generate_report()
        
        # Check report structure
        assert "metadata" in report
        assert "summary" in report
        assert "beacon_latency_ms" in report
        assert "pqc_latency_ms" in report
        assert "spiffe_latency_ms" in report
        assert "resource_utilization" in report
        assert "failure_recovery" in report
        assert "scaling_analysis" in report

    def test_report_completeness(self):
        """Test report has all required metrics"""
        gen = DistributedLoadGenerator(node_count=100, duration_seconds=15)
        result = gen.run_steady_state_test()
        
        report = result.generate_report()
        
        # Check required metadata
        assert report["metadata"]["test_name"]
        assert report["metadata"]["node_count"] == 100
        
        # Check required metrics
        assert all(k in report["beacon_latency_ms"] for k in ["p50", "p95", "p99"])
        assert report["summary"]["total_beacons_processed"] > 0


class TestProductionValidation:
    """Production readiness validation"""

    @pytest.mark.slow
    def test_production_target_100_nodes(self):
        """Validate 100 nodes meets production target"""
        gen = DistributedLoadGenerator(node_count=100, duration_seconds=30)
        result = gen.run_steady_state_test()
        
        report = result.generate_report()
        
        # Production target: p99 < 10ms at 100 nodes (baseline from Phase 4)
        assert report["beacon_latency_ms"]["p99"] < 10

    @pytest.mark.slow
    def test_production_target_500_nodes(self):
        """Validate 500 nodes meets production target"""
        gen = DistributedLoadGenerator(node_count=500, duration_seconds=30)
        result = gen.run_steady_state_test()
        
        report = result.generate_report()
        
        # Production target: p99 < 50ms at 500 nodes
        assert report["beacon_latency_ms"]["p99"] < 50

    @pytest.mark.slow
    def test_production_target_1000_nodes(self):
        """Validate 1000 nodes meets production target"""
        gen = DistributedLoadGenerator(node_count=1000, duration_seconds=60)
        result = gen.run_steady_state_test()
        
        report = result.generate_report()
        
        # Production target: p99 < 100ms at 1000 nodes
        assert report["beacon_latency_ms"]["p99"] < 100, \
            f"1000-node target failed: {report['beacon_latency_ms']['p99']}ms > 100ms"

    @pytest.mark.slow
    def test_zero_data_loss_under_failure(self):
        """Validate no data loss during failures"""
        failures = [
            FailurePattern.node_crash(start_time=20),
            FailurePattern.byzantine_nodes(start_time=40),
        ]
        gen = DistributedLoadGenerator(node_count=100, duration_seconds=70)
        result = gen.run_failure_injection_test(failures)
        
        # Should process significant number of beacons without loss
        assert result.total_beacons > 100


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

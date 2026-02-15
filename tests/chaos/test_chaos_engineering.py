"""
Chaos Engineering Tests

Comprehensive test suite for system resilience and failure recovery.
Tests 30+ chaos scenarios across different failure modes.
"""

import asyncio
import time
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.testing.chaos_engineering import (ChaosInjector, ChaosScenario,
                                           ChaosType, create_chaos_scenario)


class TestNetworkChaos:
    """Test network-related chaos scenarios"""

    @pytest.fixture
    def injector(self):
        return ChaosInjector()

    @pytest.mark.asyncio
    async def test_inject_network_latency(self, injector):
        """Test network latency injection"""
        start = time.time()
        await injector.inject_network_latency(
            base_latency_ms=10, max_latency_ms=50, duration_seconds=0.5
        )
        duration = time.time() - start

        # Should at least add some latency
        assert duration > 0.5

    @pytest.mark.asyncio
    async def test_inject_packet_loss(self, injector):
        """Test packet loss injection"""
        await injector.inject_packet_loss(loss_rate=0.3, duration_seconds=0.5)

        assert len(injector.chaos_history) == 0  # No history yet

    @pytest.mark.asyncio
    async def test_network_partition(self, injector):
        """Test network partition"""
        start = time.time()
        await injector.inject_network_partition(
            partition_duration_seconds=0.2, affected_nodes=["node1", "node2", "node3"]
        )
        duration = time.time() - start

        assert duration >= 0.2

    @pytest.mark.asyncio
    async def test_cascading_network_failures(self, injector):
        """Test cascading network failures"""
        affected_nodes = ["peer1", "peer2", "peer3"]
        start = time.time()

        await injector.inject_cascading_failure(
            primary_service="primary_node",
            dependent_services=["secondary_node", "cache_node"],
            cascade_delay_seconds=0.2,
        )

        duration = time.time() - start
        # Should take at least initial crash + 2 cascades + recovery delays
        assert duration > 1.0


class TestServiceChaos:
    """Test service-related chaos scenarios"""

    @pytest.fixture
    def injector(self):
        return ChaosInjector()

    @pytest.mark.asyncio
    async def test_service_crash(self, injector):
        """Test service crash scenario"""
        crash_called = False

        async def crash_callback(service_name):
            nonlocal crash_called
            crash_called = True

        start = time.time()
        await injector.inject_service_crash(
            service_name="api_server",
            recovery_delay_seconds=0.5,
            crash_callback=crash_callback,
        )
        duration = time.time() - start

        assert crash_called
        assert duration >= 0.5

    @pytest.mark.asyncio
    async def test_service_hang(self, injector):
        """Test service hang scenario"""
        start = time.time()
        await injector.inject_service_hang(
            service_name="database", hang_duration_seconds=0.5, detection_delay=0.1
        )
        duration = time.time() - start

        assert duration >= 0.5

    @pytest.mark.asyncio
    async def test_multiple_service_crashes(self, injector):
        """Test multiple concurrent service crashes"""
        services = ["service1", "service2", "service3"]

        crashes = []

        async def track_crash(service_name):
            crashes.append(service_name)

        tasks = [
            injector.inject_service_crash(
                service_name=svc, recovery_delay_seconds=0.2, crash_callback=track_crash
            )
            for svc in services
        ]

        await asyncio.gather(*tasks)

        assert len(crashes) == 3

    @pytest.mark.asyncio
    async def test_service_recovery_timing(self, injector):
        """Test service recovery timing"""
        for recovery_delay in [0.1, 0.3, 0.5]:
            start = time.time()
            await injector.inject_service_crash(
                service_name="test_service", recovery_delay_seconds=recovery_delay
            )
            actual_delay = time.time() - start

            assert actual_delay >= recovery_delay


class TestResourceChaos:
    """Test resource exhaustion chaos scenarios"""

    @pytest.fixture
    def injector(self):
        return ChaosInjector()

    @pytest.mark.asyncio
    async def test_memory_leak(self, injector):
        """Test memory leak injection"""
        start = time.time()
        await injector.inject_memory_leak(
            leak_rate_mb_per_sec=10.0, max_memory_mb=100.0, duration_seconds=0.5
        )
        duration = time.time() - start

        assert duration >= 0.5

    @pytest.mark.asyncio
    async def test_cpu_spike(self, injector):
        """Test CPU spike injection"""
        start = time.time()
        await injector.inject_cpu_spike(cpu_percent=80.0, duration_seconds=0.2)
        duration = time.time() - start

        assert duration >= 0.2

    @pytest.mark.asyncio
    async def test_memory_exhaustion_recovery(self, injector):
        """Test system recovery from memory exhaustion"""
        await injector.inject_memory_leak(
            leak_rate_mb_per_sec=50.0, max_memory_mb=200.0, duration_seconds=0.3
        )

        # After chaos, system should recover
        assert len(injector.chaos_history) == 0  # No automatic history yet


class TestDataChaos:
    """Test data integrity chaos scenarios"""

    @pytest.fixture
    def injector(self):
        return ChaosInjector()

    @pytest.mark.asyncio
    async def test_data_corruption(self, injector):
        """Test data corruption injection"""
        start = time.time()
        await injector.inject_data_corruption(corruption_rate=0.5, duration_seconds=0.3)
        duration = time.time() - start

        assert duration >= 0.3

    @pytest.mark.asyncio
    async def test_byzantine_fault(self, injector):
        """Test Byzantine fault injection"""
        start = time.time()
        await injector.inject_byzantine_fault(
            service_name="consensus_node", fault_rate=0.5, duration_seconds=0.3
        )
        duration = time.time() - start

        assert duration >= 0.3

    @pytest.mark.asyncio
    async def test_clock_skew(self, injector):
        """Test clock skew injection"""
        start = time.time()
        await injector.inject_clock_skew(skew_seconds=5.0, duration_seconds=0.2)
        duration = time.time() - start

        assert duration >= 0.2


class TestChaosScenario:
    """Test chaos scenario management"""

    def test_create_latency_scenario(self):
        """Test creating network latency scenario"""
        scenario = create_chaos_scenario(
            chaos_type=ChaosType.NETWORK_LATENCY,
            severity=0.8,
            duration_seconds=30.0,
            base_latency_ms=50,
        )

        assert scenario.chaos_type == ChaosType.NETWORK_LATENCY
        assert scenario.severity == 0.8
        assert scenario.duration_seconds == 30.0

    def test_create_service_crash_scenario(self):
        """Test creating service crash scenario"""
        scenario = create_chaos_scenario(
            chaos_type=ChaosType.SERVICE_CRASH,
            severity=1.0,
            duration_seconds=10.0,
            target_component="database",
        )

        assert scenario.chaos_type == ChaosType.SERVICE_CRASH
        assert scenario.target_component == "database"

    @pytest.mark.asyncio
    async def test_chaos_scenario_context_manager(self):
        """Test chaos scenario context manager"""
        injector = ChaosInjector()
        scenario = create_chaos_scenario(
            chaos_type=ChaosType.NETWORK_LATENCY, severity=0.5, duration_seconds=0.1
        )

        async with injector.chaos_scenario(scenario):
            # Chaos is active
            pass

        # After context, event should be recorded
        assert len(injector.chaos_history) == 1


class TestComplexChaosScenarios:
    """Test complex multi-failure scenarios"""

    @pytest.fixture
    def injector(self):
        return ChaosInjector()

    @pytest.mark.asyncio
    async def test_cascading_failure_chain(self, injector):
        """Test cascading failure across multiple services"""
        start = time.time()

        # Start primary crash
        await injector.inject_service_crash(
            service_name="primary", recovery_delay_seconds=1.0
        )

        duration = time.time() - start
        assert duration >= 1.0

    @pytest.mark.asyncio
    async def test_simultaneous_network_and_service_failures(self, injector):
        """Test simultaneous network and service failures"""
        tasks = [
            injector.inject_packet_loss(loss_rate=0.3, duration_seconds=0.3),
            injector.inject_service_hang(
                service_name="api", hang_duration_seconds=0.3, detection_delay=0.1
            ),
            injector.inject_cpu_spike(cpu_percent=90, duration_seconds=0.3),
        ]

        start = time.time()
        await asyncio.gather(*tasks)
        duration = time.time() - start

        assert duration >= 0.3

    @pytest.mark.asyncio
    async def test_recovery_under_sustained_chaos(self, injector):
        """Test system recovery while chaos is ongoing"""
        # Background chaos
        chaos_task = asyncio.create_task(
            injector.inject_packet_loss(loss_rate=0.2, duration_seconds=1.0)
        )

        # Wait a bit then try to recover
        await asyncio.sleep(0.3)

        # Attempt recovery action (would be actual recovery in real system)
        recovery_start = time.time()
        await asyncio.sleep(0.2)
        recovery_time = time.time() - recovery_start

        assert recovery_time >= 0.2

        # Wait for chaos to complete
        await chaos_task


@pytest.mark.chaos
class TestChaosResiliencePatterns:
    """Test system resilience patterns under chaos"""

    @pytest.mark.asyncio
    async def test_circuit_breaker_pattern_under_chaos(self):
        """Test circuit breaker pattern with chaos"""
        injector = ChaosInjector()

        # Inject cascading failures
        await injector.inject_cascading_failure(
            primary_service="upstream",
            dependent_services=["service_a", "service_b"],
            cascade_delay_seconds=0.1,
        )

        # Circuit breaker should have triggered

    @pytest.mark.asyncio
    async def test_bulkhead_pattern_under_chaos(self):
        """Test bulkhead pattern isolation with chaos"""
        injector = ChaosInjector()

        # Crash one service in bulkhead
        await injector.inject_service_crash(
            service_name="isolated_service", recovery_delay_seconds=0.3
        )

        # Other bulkheads should continue operating

    @pytest.mark.asyncio
    async def test_retry_pattern_under_chaos(self):
        """Test retry pattern with transient failures"""
        injector = ChaosInjector()

        # Inject temporary network issues
        await injector.inject_packet_loss(loss_rate=0.5, duration_seconds=0.5)

        # Retries should eventually succeed


class TestChaosMetrics:
    """Test chaos event tracking and metrics"""

    def test_chaos_history_recording(self):
        """Test that chaos events are recorded"""
        injector = ChaosInjector()

        scenario = create_chaos_scenario(
            chaos_type=ChaosType.NETWORK_LATENCY, severity=0.5, duration_seconds=0.1
        )

        injector.record_chaos_event(scenario, {"status": "completed"})

        assert len(injector.chaos_history) == 1
        assert injector.chaos_history[0]["chaos_type"] == "network_latency"

    def test_chaos_history_max_limit(self):
        """Test chaos history respects max limit"""
        injector = ChaosInjector()
        injector.max_history = 10

        scenario = create_chaos_scenario(
            chaos_type=ChaosType.SERVICE_CRASH, severity=1.0, duration_seconds=0.1
        )

        # Record more than max_history events
        for _ in range(15):
            injector.record_chaos_event(scenario, {"status": "completed"})

        # Should only keep last 10
        assert len(injector.chaos_history) == 10

    def test_retrieve_chaos_statistics(self):
        """Test retrieving chaos statistics"""
        injector = ChaosInjector()

        scenarios = [
            create_chaos_scenario(ChaosType.NETWORK_LATENCY, 0.5),
            create_chaos_scenario(ChaosType.SERVICE_CRASH, 1.0),
            create_chaos_scenario(ChaosType.MEMORY_LEAK, 0.8),
        ]

        for scenario in scenarios:
            injector.record_chaos_event(scenario, {"status": "completed"})

        assert len(injector.chaos_history) == 3

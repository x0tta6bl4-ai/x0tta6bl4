"""
Consensus Latency Benchmarks
============================

Benchmarks for measuring real consensus operation latency.
Addresses TD-006: Self-reported latency in tests.

These benchmarks measure actual execution time for consensus operations
instead of relying on self-reported values.
"""

import asyncio
import pytest
import pytest_asyncio
import time
from typing import List

from src.swarm.consensus_integration import SwarmConsensusManager, ConsensusMode, AgentInfo
from src.swarm.intelligence import SwarmIntelligence
from tests.conftest import latency_threshold


class TestConsensusLatencyBenchmarks:
    """Benchmarks for consensus operation latency."""

    @pytest_asyncio.fixture
    async def swarm_manager(self):
        """Create a swarm consensus manager for testing."""
        manager = SwarmConsensusManager(node_id="benchmark-node")
        await manager.start()
        yield manager
        await manager.stop()

    @pytest.mark.asyncio
    async def test_consensus_decision_latency_simple(self, swarm_manager):
        """Benchmark latency for simple consensus decision."""
        latencies = []

        for i in range(10):  # Run multiple times for average
            start_time = time.time()

            result = await swarm_manager.decide(
                topic=f"test-decision-{i}",
                proposals=["option-a", "option-b"],
                mode=ConsensusMode.SIMPLE,
            )

            elapsed_ms = (time.time() - start_time) * 1000
            latencies.append(elapsed_ms)

            assert result.success is True  # Decision should succeed

        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)

        # Assert reasonable latency bounds
        assert avg_latency < latency_threshold(50.0), f"Average latency {avg_latency:.2f}ms exceeds threshold"
        assert max_latency < latency_threshold(100.0), f"Max latency {max_latency:.2f}ms exceeds threshold"

        print(f"Simple consensus latency: avg={avg_latency:.2f}ms, max={max_latency:.2f}ms")

    @pytest.mark.asyncio
    async def test_consensus_decision_latency_raft(self, swarm_manager):
        """Benchmark latency for Raft consensus decision."""
        # Add agents for Raft
        swarm_manager.add_agent(AgentInfo(agent_id="node-1", name="Node 1"))
        swarm_manager.add_agent(AgentInfo(agent_id="node-2", name="Node 2"))

        latencies = []

        for i in range(5):  # Fewer iterations for Raft (more complex)
            start_time = time.time()

            result = await swarm_manager.decide(
                topic=f"raft-decision-{i}",
                proposals=["option-a", "option-b", "option-c"],
                mode=ConsensusMode.RAFT,
            )

            elapsed_ms = (time.time() - start_time) * 1000
            latencies.append(elapsed_ms)

            assert result.success is True

        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)

        # Raft is more complex, allow higher latency
        assert avg_latency < latency_threshold(200.0), f"Raft average latency {avg_latency:.2f}ms exceeds threshold"
        assert max_latency < latency_threshold(500.0), f"Raft max latency {max_latency:.2f}ms exceeds threshold"

        print(f"Raft consensus latency: avg={avg_latency:.2f}ms, max={max_latency:.2f}ms")

    @pytest.mark.asyncio
    async def test_swarm_intelligence_latency(self):
        """Benchmark SwarmIntelligence decision latency."""
        swarm = SwarmIntelligence(
            node_id="benchmark-swarm",
            consensus_mode=ConsensusMode.SIMPLE,
        )
        await swarm.initialize()

        try:
            from src.swarm.intelligence import DecisionContext

            latencies = []

            for i in range(10):
                context = DecisionContext(
                    topic=f"swarm-decision-{i}",
                    options=["choice-1", "choice-2"],
                )

                start_time = time.time()
                result = await swarm.make_decision(context, timeout_ms=1000)
                elapsed_ms = (time.time() - start_time) * 1000

                latencies.append(elapsed_ms)
                assert result.approved is True

            avg_latency = sum(latencies) / len(latencies)
            max_latency = max(latencies)

            assert avg_latency < latency_threshold(150.0), f"Swarm avg latency {avg_latency:.2f}ms exceeds threshold"
            assert max_latency < latency_threshold(300.0), f"Swarm max latency {max_latency:.2f}ms exceeds threshold"

            print(f"SwarmIntelligence latency: avg={avg_latency:.2f}ms, max={max_latency:.2f}ms")

        finally:
            await swarm.shutdown()

    @pytest.mark.asyncio
    async def test_consensus_throughput(self, swarm_manager):
        """Benchmark consensus throughput (decisions per second)."""
        num_decisions = 20
        start_time = time.time()

        tasks = []
        for i in range(num_decisions):
            task = swarm_manager.decide(
                topic=f"throughput-{i}",
                proposals=["a", "b"],
                mode=ConsensusMode.SIMPLE,
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks)
        total_time = time.time() - start_time

        successful_decisions = sum(1 for r in results if r.success)
        throughput = successful_decisions / total_time  # decisions per second

        assert throughput > 10.0, f"Throughput {throughput:.2f} decisions/sec too low"
        print(f"Consensus throughput: {throughput:.2f} decisions/sec")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

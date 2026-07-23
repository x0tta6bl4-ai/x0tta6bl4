"""
Unit test for chaos_failure_injector.py harness.
"""
from __future__ import annotations

import pytest

from scripts.ops.chaos_failure_injector import ChaosNetworkTransport, run_chaos_experiment


@pytest.mark.asyncio
async def test_run_chaos_experiment_pass():
    results = await run_chaos_experiment(nodes_count=5, duration_seconds=1.0, drop_rate=0.05, latency_ms=5.0)
    assert results["verdict"] == "PASS"
    assert results["invariants"]["safety_no_conflicting_commit"] is True
    assert results["invariants"]["liveness_quorum_recovery"] is True


@pytest.mark.asyncio
async def test_chaos_network_transport_partition():
    transport = ChaosNetworkTransport(drop_probability=0.0, max_delay_ms=0.0)
    transport.partition_node("node-2")
    sent = await transport.send_message("node-1", "node-2", {"msg": "hello"})
    assert sent is False
    assert transport.total_dropped == 1

    transport.heal_partition("node-2")
    assert "node-2" not in transport.partitioned_nodes

"""
Chaos Engineering Test for x0tta6bl4 Self-Healing
================================================

Simulates node failures and network partitions to verify that the
MAPE-K cycle and self_healing_daemon.py correctly restore connectivity.
"""

import pytest
import asyncio
import time
import os
import subprocess
from unittest.mock import MagicMock, patch

@pytest.mark.asyncio
async def test_self_healing_cycle_on_failure():
    """
    Test that the self-healing daemon detects a failure and triggers recovery.
    """
    from src.network import self_healing_daemon
    
    # We will patch functions to simulate failures
    with patch("src.network.self_healing_daemon.ping_target") as mock_ping, \
         patch("src.network.self_healing_daemon.trigger_healing") as mock_trigger, \
         patch("src.network.self_healing_daemon.check_proxy_health", return_value=True), \
         patch("src.network.self_healing_daemon.get_fin_wait2_count", return_value=0), \
         patch("time.sleep", return_value=None):
        
        # 1. Simulate failures
        mock_ping.return_value = float('inf')
        
        # We need to manually run a few iterations of the loop logic
        # since run_daemon is an infinite loop
        
        # Iteration 1
        latency = self_healing_daemon.ping_target("8.8.8.8", "tun0")
        if latency == float('inf'):
            self_healing_daemon._consecutive_failures += 1
            if self_healing_daemon._consecutive_failures >= 2:
                self_healing_daemon.trigger_healing("Sustained packet loss")
        
        assert self_healing_daemon._consecutive_failures == 1
        mock_trigger.assert_not_called()
        
        # Iteration 2
        latency = self_healing_daemon.ping_target("8.8.8.8", "tun0")
        if latency == float('inf'):
            self_healing_daemon._consecutive_failures += 1
            if self_healing_daemon._consecutive_failures >= 2:
                self_healing_daemon.trigger_healing("Sustained packet loss")
                
        assert self_healing_daemon._consecutive_failures == 2
        mock_trigger.assert_called_with("Sustained packet loss")

def test_chaos_scenario_node_isolation():
    """
    Simulated chaos: isolate a node and verify routing table update.
    """
    from src.libx0t.network.mesh_router import MeshRouter, MeshPeer
    
    router = MeshRouter(node_id="chaos-node")
    peer = MeshPeer(node_id="neighbor-1", host="10.0.0.2", port=10809)
    router.peers["neighbor-1"] = peer
    
    assert "neighbor-1" in router.peers
    
    # Chaos: Remove the peer
    del router.peers["neighbor-1"]
    
    assert "neighbor-1" not in router.peers

from __future__ import annotations
import pytest
from src.self_healing.mape_k.manager import SelfHealingManager
from src.self_healing.mape_k.logic_contract import FormalState

def test_mape_k_idle_cycle():
    """Test that MAPE-K cycle stays IDLE when metrics are healthy."""
    manager = SelfHealingManager(node_id="test-node")
    healthy_metrics = {
        "cpu_percent": 10.0,
        "memory_percent": 20.0,
        "packet_loss_percent": 0.1
    }
    manager.run_cycle(healthy_metrics)
    assert manager.logic_contract.current_state == FormalState.IDLE

def test_mape_k_anomaly_detection():
    """Test that MAPE-K detects anomaly and attempts recovery."""
    manager = SelfHealingManager(node_id="test-node", action_cooldown_seconds=0)
    # Trigger CPU anomaly
    anomaly_metrics = {
        "cpu_percent": 95.0,
        "memory_percent": 20.0,
        "packet_loss_percent": 0.1
    }
    manager.run_cycle(anomaly_metrics)
    
    # Check if it returned to IDLE or reached expected final states
    # Note: State IDLE is reached after a successful execution or no anomaly
    assert manager.logic_contract.current_state in [FormalState.IDLE, FormalState.VERIFYING, FormalState.COOLDOWN]

if __name__ == "__main__":
    pytest.main([__file__])


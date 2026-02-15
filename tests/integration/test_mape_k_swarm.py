import asyncio
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.consciousness import ConsciousnessEngine, ConsciousnessState
from src.core.mape_k_loop import MAPEKLoop


# Mock PARL Controller
class MockPARLController:
    def __init__(self, risk_to_return=0.0):
        self.risk_to_return = risk_to_return

    async def execute_parallel(
        self, tasks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        results = []
        for task in tasks:
            results.append(
                {
                    "success": True,
                    "result": {
                        "task_type": task["task_type"],
                        "status": "completed",
                        "risk_score": self.risk_to_return,
                    },
                }
            )
        return results


@pytest.mark.asyncio
async def test_mape_k_swarm_integration_high_risk():
    """
    Test that a high risk reported by Swarm degrades the Consciousness State.
    """
    # 1. Setup Dependencies
    consciousness = ConsciousnessEngine()
    mesh = AsyncMock()
    mesh.get_statistics.return_value = {}
    prometheus = MagicMock()
    zero_trust = MagicMock()
    zero_trust.get_validation_stats.return_value = {}

    # 2. Setup Swarm with High Risk (0.5)
    # A 0.5 penalty should reduce Phi significantly
    # Normal Phi ~1.618. Penalty 0.5 -> 1.618 * 0.5 = 0.809
    # This sits on the border of CONTEMPLATIVE/MYSTICAL
    parl = MockPARLController(risk_to_return=0.5)

    loop = MAPEKLoop(
        consciousness_engine=consciousness,
        mesh_manager=mesh,
        prometheus=prometheus,
        zero_trust=zero_trust,
        parl_controller=parl,
    )

    # 3. Simulate Monitor Phase
    raw_metrics = {
        "cpu_percent": 60.0,  # Optimal
        "memory_percent": 65.0,  # Optimal
        "latency_ms": 85.0,  # Optimal
        "packet_loss": 0.0,  # Optimal
        "mesh_connectivity": 50,  # Excellent
    }
    # Without penalty, this should be EUPHORIC/HARMONIC (Phi ~1.618)

    # 4. Run Analyze Phase
    metrics = await loop._analyze(raw_metrics)

    print(f"\nPhi-Ratio with 0.5 Risk Penalty: {metrics.phi_ratio}")
    print(f" resulting State: {metrics.state}")

    # 5. Asset Degradation
    # With perfect metrics, phi should be ~1.6. With 50% penalty, it drops to ~0.8
    assert metrics.phi_ratio < 1.0
    assert metrics.state in [
        ConsciousnessState.CONTEMPLATIVE,
        ConsciousnessState.MYSTICAL,
    ]


@pytest.mark.asyncio
async def test_mape_k_swarm_integration_no_risk():
    """
    Test that zero risk from Swarm maintains Harmonic/Euphoric state.
    """
    # 1. Setup Dependencies
    consciousness = ConsciousnessEngine()
    mesh = AsyncMock()
    mesh.get_statistics.return_value = {}
    prometheus = MagicMock()
    zero_trust = MagicMock()
    zero_trust.get_validation_stats.return_value = {}

    # 2. Setup Swarm with Zero Risk
    parl = MockPARLController(risk_to_return=0.0)

    loop = MAPEKLoop(
        consciousness_engine=consciousness,
        mesh_manager=mesh,
        prometheus=prometheus,
        zero_trust=zero_trust,
        parl_controller=parl,
    )

    # 3. Simulate Monitor Phase (Perfect condition)
    raw_metrics = {
        "cpu_percent": 60.0,
        "memory_percent": 65.0,
        "latency_ms": 85.0,
        "packet_loss": 0.0,
        "mesh_connectivity": 50,
    }

    # 4. Run Analyze Phase
    metrics = await loop._analyze(raw_metrics)

    print(f"\nPhi-Ratio with 0.0 Risk Penalty: {metrics.phi_ratio}")
    print(f" resulting State: {metrics.state}")

    # 5. Assert Harmony
    assert metrics.phi_ratio > 1.4
    assert metrics.state == ConsciousnessState.EUPHORIC


if __name__ == "__main__":
    asyncio.run(test_mape_k_swarm_integration_high_risk())
    asyncio.run(test_mape_k_swarm_integration_no_risk())

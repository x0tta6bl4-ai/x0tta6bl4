import asyncio
import time

import pytest

from src.federated_learning.coordinator import (CoordinatorConfig,
                                                FederatedCoordinator)
from src.federated_learning.parl_integration import (PARLFederatedOrchestrator,
                                                     PARLFLConfig)


@pytest.mark.asyncio
async def test_parl_federated_learning_speedup():
    """
    Test that PARL integration provides speedup over sequential execution
    (simulated by sleep delays).
    """
    # Setup Coordinator
    config = CoordinatorConfig(
        min_participants=10,
        target_participants=50,  # Scale up to see parallel benefits
        collection_timeout=10.0,
    )
    coordinator = FederatedCoordinator("test_coord", config)

    # Register 50 nodes
    for i in range(50):
        coordinator.register_node(f"node_{i}")

    # Setup PARL Orchestrator
    parl_config = PARLFLConfig(max_workers=50, parallel_training_steps=1500)
    orchestrator = PARLFederatedOrchestrator(coordinator, parl_config)

    try:
        # Measure time
        start_time = time.time()

        # Run Round 1
        round_obj = await orchestrator.run_round(round_number=1)

        elapsed = time.time() - start_time

        assert round_obj is not None
        assert round_obj.status.value == "completed"
        assert len(round_obj.participating_nodes) >= 10

        print(
            f"\nPARL FL Round completed in {elapsed:.4f}s with {len(round_obj.participating_nodes)} participants"
        )

        # With 50 tasks taking ~0.1s each:
        # Sequential would be ~5.0s
        # Parallel (50 workers) should be ~0.2s overhead
        # If elapsed < 1.0s, we confirm massive speedup
        assert elapsed < 2.0, "PARL failed to provide expected speedup!"

    finally:
        await orchestrator.terminate()


if __name__ == "__main__":
    asyncio.run(test_parl_federated_learning_speedup())

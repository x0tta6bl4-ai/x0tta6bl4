import asyncio
import logging
import os
import sys
from unittest.mock import AsyncMock, MagicMock

# Add project root to path
sys.path.append(os.getcwd())

from src.core.consciousness import (ConsciousnessEngine, ConsciousnessMetrics,
                                    ConsciousnessState)
from src.core.mape_k_loop import MAPEKLoop

# Configure logging to show our thoughts
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


async def main():
    print("🤖 Initializing MAPE-K Automation Verification...")

    # 1. Real Consciousness Logic with LLM
    # enable_advanced_metrics=True will try to load LocalLLM
    consciousness = ConsciousnessEngine(enable_advanced_metrics=True)

    if not consciousness.llm:
        print("⚠️ LocalLLM not initialized. Is llama-cpp-python installed?")
        # We can still run, but won't get LLM thoughts
    elif not consciousness.llm.is_ready():
        print("⚠️ LocalLLM initialized but not ready (model missing?).")
    else:
        print("✅ LocalLLM ready for thoughts.")

    # 2. Mock other dependencies
    mesh = MagicMock()
    prometheus = MagicMock()
    zero_trust = MagicMock()
    parl = AsyncMock()
    parl.execute_parallel.return_value = []  # No swarm risks

    # 3. Create Loop
    loop = MAPEKLoop(
        consciousness_engine=consciousness,
        mesh_manager=mesh,
        prometheus=prometheus,
        zero_trust=zero_trust,
        parl_controller=parl,
    )

    # Override frequency for testing
    loop.thought_frequency = 2
    print(
        f"⚙️ Thought frequency set to every {loop.thought_frequency} cycles for testing."
    )

    # Mock internal methods to avoid real system calls
    loop._monitor = AsyncMock(
        return_value={
            "cpu_percent": 50.0,
            "memory_percent": 50.0,
            "latency_ms": 20.0,
            "packet_loss": 0.0,
            "mesh_connectivity": 10,
        }
    )
    loop._plan = MagicMock(return_value={})
    loop._execute = AsyncMock(return_value=[])
    loop._knowledge = AsyncMock()

    # 4. Run Cycles
    print("\n🔄 Starting 3 cycles...")

    for i in range(1, 4):
        print(f"\n--- Cycle {i} ---")
        await loop._execute_cycle()
        # Sleep briefly to let logs flush
        await asyncio.sleep(0.1)

    print("\n✅ Verification Complete. Check logs above for '🧠 SYSTEM THOUGHT'.")


if __name__ == "__main__":
    asyncio.run(main())

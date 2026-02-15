import os
import sys
import time

# Add project root to path
sys.path.append(os.getcwd())

from src.core.consciousness import (ConsciousnessEngine, ConsciousnessMetrics,
                                    ConsciousnessState)


def main():
    print("🔮 Initializing ConsciousnessEngine...")
    engine = ConsciousnessEngine(enable_advanced_metrics=True)

    if not engine.llm:
        print(
            "❌ LLM not initialized (enable_advanced_metrics=False or dependencies missing)."
        )
        return

    if not engine.llm.is_ready():
        print("⚠️ LLM initialized but not ready (model missing?).")
        # Proceed anyway to see if it gracefully handles it, or return

    # Create a mock metric state
    metrics = ConsciousnessMetrics(
        phi_ratio=1.618,
        state=ConsciousnessState.EUPHORIC,
        frequency_alignment=1.0,
        entropy=0.1,
        harmony_index=0.95,
        mesh_health=1.0,
        timestamp=time.time(),
    )

    print("\n--- Generating Thought for EUPHORIC state ---")
    start = time.time()
    thought = engine.get_system_thought(metrics)
    duration = time.time() - start
    print(f"Thought: {thought}")
    print(f"(Generation took {duration:.2f}s)")

    # Create a degraded state
    metrics_bad = ConsciousnessMetrics(
        phi_ratio=0.5,
        state=ConsciousnessState.MYSTICAL,
        frequency_alignment=0.3,
        entropy=0.8,
        harmony_index=0.2,
        mesh_health=0.4,
        timestamp=time.time(),
    )

    print("\n--- Generating Thought for MYSTICAL state ---")
    start = time.time()
    thought_bad = engine.get_system_thought(metrics_bad)
    duration = time.time() - start
    print(f"Thought: {thought_bad}")
    print(f"(Generation took {duration:.2f}s)")


if __name__ == "__main__":
    main()

"""
Verify DAO-Consciousness Connection

Tests the impact of DAO Alignment on System Consciousness (Phi Ratio).
1. Defines 'Perfect' system metrics.
2. Calculates Phi with DAO Alignment = 1.0 (Harmonic).
3. Calculates Phi with DAO Alignment = 0.2 (Conflict).
4. Asserts that conflict reduces the Consciousness State.
"""

import logging
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.consciousness import ConsciousnessEngine, ConsciousnessState

# Configure Logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("DAO_VERIFY")


def main():
    logger.info("🧠 Initializing Consciousness Engine...")
    engine = ConsciousnessEngine(enable_advanced_metrics=False)

    # 1. Perfect System Metrics
    perfect_metrics = {
        "cpu_percent": 60.0,  # Optimal
        "memory_percent": 65.0,  # Optimal
        "latency_ms": 85.0,  # Target
        "packet_loss": 0.0,  # Perfect
        "mesh_connectivity": 50,  # Good
        "dao_alignment": 1.0,  # Perfect Agreement
    }

    logger.info(f"📊 Baseline Metrics: {perfect_metrics}")

    # 2. Calculate Baseline Phi
    phi_baseline = engine.calculate_phi_ratio(perfect_metrics)
    state_baseline = engine.evaluate_state(phi_baseline)

    logger.info(
        f"✨ Baseline Result: Phi={phi_baseline:.4f}, State={state_baseline.value}"
    )

    if state_baseline not in [ConsciousnessState.EUPHORIC, ConsciousnessState.HARMONIC]:
        logger.error("Baseline state is not Optimal! Check calculations.")
        return

    # 3. Introduce DAO Conflict
    conflict_metrics = perfect_metrics.copy()
    conflict_metrics["dao_alignment"] = (
        0.2  # High conflict (e.g., DAO rejected key proposal)
    )

    logger.info(f"📉 Simulating DAO Conflict (Alignment=0.2)...")

    phi_conflict = engine.calculate_phi_ratio(conflict_metrics)
    state_conflict = engine.evaluate_state(phi_conflict)

    logger.info(
        f"💔 Conflict Result: Phi={phi_conflict:.4f}, State={state_conflict.value}"
    )

    # 4. Verify Impact
    diff = phi_baseline - phi_conflict
    logger.info(f"📉 Phi Drop: {diff:.4f}")

    if phi_conflict < phi_baseline:
        logger.info("✅ SUCCESS: DAO Conflict reduced System Consciousness.")
    else:
        logger.error("❌ FAILURE: DAO Conflict did not affect Consciousness.")
        return

    if state_conflict != state_baseline:
        logger.info(
            f"✅ SUCCESS: State shift observed ({state_baseline.value} -> {state_conflict.value})"
        )
    else:
        logger.warning(
            "⚠️  NOTE: State did not shift (penalty might be too mild or baseline too high)."
        )


if __name__ == "__main__":
    main()

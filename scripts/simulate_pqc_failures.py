"""
Direct Simulation of PQC Anomaly Handling in MAPE-K
===================================================

This script tests the MAPE-K response logic by directly 
triggering anomaly events in the PQCMAPEKIntegration.
"""

import asyncio
import logging
import time
from typing import Dict, Any

from src.network.ebpf.pqc_mapek_integration import (
    PQCMAPEKIntegration,
    PQCAnomalyType,
)

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("pqc-sim")

async def simulate_anomalies():
    logger.info("=== Starting Direct PQC Anomaly Simulation ===")
    
    # 1. Setup Integration
    integration = PQCMAPEKIntegration(
        pqc_daemon=None, # Not needed for direct handler calls
        enable_metrics=False
    )
    logger.info("MAPE-K Integration ready.")

    # 2. Simulate Verification Failures
    FAILURE_COUNT = 10
    logger.info(f"Triggering {FAILURE_COUNT} 'verification_failed' anomalies...")
    
    for i in range(FAILURE_COUNT):
        integration.handle_daemon_anomaly("verification_failed", {
            "session_id": f"session_{i}",
            "pubkey_id": "malicious_node_pubkey"
        })
        # MAPE-K logic typically aggregates or escalates
        await asyncio.sleep(0.01)

    # 3. Simulate Unknown Pubkey (High Priority)
    logger.info("Triggering 'unknown_pubkey' anomaly...")
    integration.handle_daemon_anomaly("unknown_pubkey", {
        "session_id": "session_unknown",
        "pubkey_id": "totally_new_pubkey"
    })

    # 4. Analyze Results
    anomalies = integration.anomaly_history
    logger.info(f"Total anomalies recorded: {len(anomalies)}")
    
    triggered_types = [a.anomaly_type for a in anomalies]
    logger.info(f"Triggered anomaly types in history: {triggered_types}")

    # 5. Check for Escalation (HIGH_FAILURE_RATE)
    # The integration should have triggered HIGH_FAILURE_RATE after X failures
    has_high_failure_rate = any(a.anomaly_type == PQCAnomalyType.HIGH_FAILURE_RATE for a in anomalies)
    has_unknown_pubkey = any(a.anomaly_type == PQCAnomalyType.UNKNOWN_PUBKEY for a in anomalies)

    if has_high_failure_rate:
        logger.info("✅ SUCCESS: HIGH_FAILURE_RATE escalation triggered.")
    else:
        logger.error("❌ FAILURE: HIGH_FAILURE_RATE escalation NOT triggered.")

    if has_unknown_pubkey:
        logger.info("✅ SUCCESS: UNKNOWN_PUBKEY anomaly detected.")
    else:
        logger.error("❌ FAILURE: UNKNOWN_PUBKEY anomaly NOT detected.")

    return has_high_failure_rate and has_unknown_pubkey

if __name__ == "__main__":
    success = asyncio.run(simulate_anomalies())
    import sys
    sys.exit(0 if success else 1)

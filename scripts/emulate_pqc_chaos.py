"""
Local Emulation of PQC Chaos Scenario
=====================================

This script emulates the 'pqc-failure' chaos scenario without requiring 
a full Kubernetes + Chaos Mesh environment. It directly interacts with 
the PQC Verification Daemon and MAPE-K integration.
"""

import asyncio
import logging
import time
import secrets
import hashlib
from typing import Dict, Any

from src.network.ebpf.pqc_verification_daemon import (
    PQCVerificationEvent,
    MockPQCVerificationDaemon,
)
from src.network.ebpf.pqc_mapek_integration import (
    PQCMAPEKIntegration,
    PQCAnomalyType,
)

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("pqc-chaos-emu")

async def run_pqc_chaos_emulation():
    logger.info("=== Starting PQC Chaos Emulation ===")
    
    # 1. Setup the system
    daemon = MockPQCVerificationDaemon()
    integration = PQCMAPEKIntegration(
        pqc_daemon=daemon,
        enable_metrics=False
    )
    # Link daemon to MAPE-K integration
    daemon.anomaly_callback = integration.handle_daemon_anomaly
    
    daemon.start()
    logger.info("System initialized: Daemon and MAPE-K integration ready.")

    # 2. Baseline State
    stats = daemon.get_stats()
    logger.info(f"Baseline stats: {stats}")

    # 3. Inject Failures (The "Chaos" part)
    FAILURE_COUNT = 15
    logger.info(f"Injecting {FAILURE_COUNT} verification failures to trigger HIGH_FAILURE_RATE...")
    
    pubkey_id = hashlib.sha256(b"target-peer").digest()[:16]
    daemon.register_public_key(pubkey_id, secrets.token_bytes(1952)) # Register valid key

    for i in range(FAILURE_COUNT):
        event = PQCVerificationEvent(
            session_id=secrets.token_bytes(16),
            signature=b"MALFORMED_SIGNATURE_" + secrets.token_bytes(32),
            payload_hash=secrets.token_bytes(32),
            pubkey_id=pubkey_id,
            timestamp=time.time_ns()
        )
        # We manually call _verify_event to simulate receiving from eBPF
        daemon._verify_event(event)
        
        if (i+1) % 5 == 0:
            logger.info(f"Injected {i+1} failures...")
        
        # Give MAPE-K time to process if needed (though it's synchronous in this mock)
        await asyncio.sleep(0.01)

    # 4. Analyze MAPE-K Response
    logger.info("Analyzing MAPE-K anomalies...")
    
    anomalies = integration.anomaly_history
    logger.info(f"Total anomalies detected: {len(anomalies)}")
    
    triggered_types = [a.anomaly_type for a in anomalies]
    logger.info(f"Triggered anomaly types: {triggered_types}")

    # 5. Validation
    success = False
    if PQCAnomalyType.HIGH_FAILURE_RATE in triggered_types:
        logger.info("✅ SUCCESS: MAPE-K detected HIGH_FAILURE_RATE anomaly.")
        success = True
    elif PQCAnomalyType.VERIFICATION_FAILED in triggered_types:
        logger.info("✅ SUCCESS: MAPE-K detected multiple VERIFICATION_FAILED events.")
        success = True
    else:
        logger.error("❌ FAILURE: MAPE-K failed to detect PQC chaos.")

    # Check for consecutive failures logic
    mapek_metrics = integration.get_metrics_for_mapek()
    logger.info(f"Final MAPE-K Metrics: {mapek_metrics}")

    daemon.stop()
    logger.info("=== PQC Chaos Emulation Complete ===")
    return success

if __name__ == "__main__":
    asyncio.run(run_pqc_chaos_emulation())

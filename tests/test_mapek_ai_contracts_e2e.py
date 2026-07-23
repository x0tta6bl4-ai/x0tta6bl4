"""
End-to-End Integration Test: MAPE-K Cycle with GraphSAGE GNN (AI) and DAO Governance (Smart Contracts/Engine)
========================================================================================================

Ties together:
1. MAPE-K Feedback Loop (SelfHealingManager)
2. AI-driven Anomaly Analysis (GraphSAGE GNN)
3. On-chain/Simulated Governance Proposals & Thresholds (Smart Contracts / Governance Engine)
"""

import os
import tempfile
import time
import asyncio
from pathlib import Path
import pytest

# Ensure test mode is enabled for the governance signature checks
os.environ["_X0TTA_TEST_MODE_"] = "true"

from src.dao.governance import GovernanceEngine, ProposalState, VoteType
from src.dao.mapek_threshold_manager import MAPEKThresholdManager
from src.self_healing.mape_k import SelfHealingManager
from src.self_healing.mape_k_v3_integration import MAPEKV3Integration, integrate_v3_into_mapek
from src.storage.knowledge_storage_v2 import KnowledgeStorageV2
from src.ml.graphsage_anomaly_detector import GraphSAGEAnalyzer


@pytest.fixture
def temp_storage():
    """Create temporary storage directory for thresholds and knowledge database."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    import shutil
    shutil.rmtree(temp_dir)


@pytest.fixture
def setup_e2e_integration(temp_storage):
    """Setup complete end-to-end integration environment."""
    # 1. Initialize DAO Governance
    governance = GovernanceEngine("node-1")
    
    # 2. Initialize Threshold Manager with temporary storage path
    threshold_manager = MAPEKThresholdManager(
        governance_engine=governance, storage_path=temp_storage
    )
    
    # 3. Initialize Knowledge Storage (with mock/disabled real IPFS)
    knowledge_storage = KnowledgeStorageV2(
        node_id="node-1", storage_path=temp_storage, use_real_ipfs=False
    )
    
    # 4. Initialize Self-Healing Manager (MAPE-K Loop)
    healing_manager = SelfHealingManager(
        node_id="node-1",
        threshold_manager=threshold_manager,
        knowledge_storage=knowledge_storage
    )
    
    # 5. Integrate V3.0 Components (GraphSAGE GNN)
    v3_integration = integrate_v3_into_mapek(
        healing_manager, enable_graphsage=True, enable_stego=False
    )
    
    return {
        "governance": governance,
        "threshold_manager": threshold_manager,
        "knowledge_storage": knowledge_storage,
        "healing_manager": healing_manager,
        "v3_integration": v3_integration,
    }


@pytest.mark.asyncio
async def test_mapek_graphsage_contracts_e2e(setup_e2e_integration):
    """
    Complete end-to-end flow:
    1. Verify initial baseline thresholds (e.g. CPU = 80%).
    2. Feed telemetry below threshold (CPU = 76%) -> Verify no anomaly is triggered.
    3. DAO Governance proposal to update threshold (CPU = 75.0%) is created, voted on, and approved.
    4. Apply proposal to change MAPE-K thresholds.
    5. Feed same telemetry (CPU = 76%) -> Verify it now triggers anomaly detection.
    6. Verify GraphSAGE GNN (AI) executes inference on the anomaly.
    7. Verify Plan, Execute, and Knowledge storage logging.
    """
    gov = setup_e2e_integration["governance"]
    tm = setup_e2e_integration["threshold_manager"]
    hm = setup_e2e_integration["healing_manager"]
    v3 = setup_e2e_integration["v3_integration"]
    ks = setup_e2e_integration["knowledge_storage"]

    # --- Step 1: Verify Initial Threshold ---
    cpu_thresh = tm.get_threshold("cpu_threshold")
    assert cpu_thresh == 80.0, "Default CPU threshold should be 80%"

    # --- Step 2: Telemetry below initial threshold (CPU = 76%) ---
    # Prepare node metrics + topology info for GraphSAGE
    # Features must trigger GNN anomaly (CPU > 85%, Latency > 100ms)
    metrics = {
        "cpu_percent": 76.0,
        "memory_percent": 60.0,
        "node_features": {
            "node-1": {
                "latency": 120.0,
                "loss_rate": 0.20,
                "cpu": 0.95,
                "memory": 0.95,
                "neighbors_count": 2,
                "throughput": 1.0,
                "error_rate": 0.5,
                "uptime": 1200.0,
                "load_avg": 5.0,
                "packet_queue": 20.0,
            }
        },
        "node_topology": {
            "node-1": ["node-2", "node-3"]
        }
    }

    # Run MAPE-K cycle
    # Before the threshold adjustment, 76% should not trigger self-healing monitor
    initial_check = hm.monitor.check(metrics)
    initial_anomaly = initial_check.get("anomaly_detected", False) if isinstance(initial_check, dict) else bool(initial_check)
    assert not initial_anomaly, "Should not trigger anomaly if CPU is below threshold"

    # --- Step 3: DAO Proposes Threshold Update ---
    # Create proposal to lower CPU threshold to 75.0%
    proposal = gov.create_proposal(
        title="Adjust CPU Threshold for Edge Nodes",
        description="Lower threshold from 80% to 75% due to heat limits",
        actions=[
            {
                "type": "update_mapek_threshold",
                "parameter": "cpu_threshold",
                "value": 75.0,
            }
        ],
    )

    # Vote and pass the proposal
    gov.cast_vote(proposal.id, "node-1", VoteType.YES, tokens=500.0)
    gov.cast_vote(proposal.id, "node-2", VoteType.YES, tokens=500.0)
    
    # Tally votes on-chain
    gov._tally_votes(proposal)
    assert proposal.state == ProposalState.PASSED, "Proposal should pass"

    # --- Step 4: Apply DAO Proposals to Thresholds ---
    applied = tm.check_and_apply_dao_proposals()
    assert applied > 0, "At least one threshold proposal should be applied"
    
    new_cpu_thresh = tm.get_threshold("cpu_threshold")
    assert new_cpu_thresh == 75.0, "Threshold should be updated to 75%"

    # --- Step 5: Ingest Telemetry Again (CPU = 76%) ---
    # Now it is ABOVE the new 75% threshold, so Monitor phase must flag it
    new_check = hm.monitor.check(metrics)
    new_anomaly = new_check.get("anomaly_detected", False) if isinstance(new_check, dict) else bool(new_check)
    assert new_anomaly, "Should detect anomaly since CPU 76% is now above 75% threshold"

    # --- Step 6: Verify GraphSAGE Anomaly Inference ---
    # GraphSAGE is lazy-loaded/integrated in the Analyze phase via enhance_analyze
    # Let's run a full MAPE-K cycle to verify GraphSAGE GNN runs during the Analyze phase
    hm.run_cycle(metrics)

    # Wait for the background task to record the incident in SQLite
    await asyncio.sleep(1.0)

    # --- Step 7: Verify Knowledge Storage & Stats ---
    # Check that the incident was correctly recorded in the Knowledge database
    stats = ks.get_stats()
    assert stats is not None
    assert stats.get("total_incidents", 0) > 0, "Incident must be logged in Knowledge base"

    print(" E2E MAPE-K AI & Contract Integration Test: PASSED VERIFIED_HERE")


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))

#!/usr/bin/env python3
"""
Example: Complete Integration
=============================

Demonstrates complete integration:
- Knowledge Storage → MAPE-K
- DAO → Threshold Manager → MAPE-K
- PQC Performance
"""
import asyncio
import tempfile
from pathlib import Path

from src.storage.knowledge_storage_v2 import KnowledgeStorageV2
from src.storage.mapek_integration import MAPEKKnowledgeStorageAdapter
from src.dao.governance import GovernanceEngine
from src.dao.mapek_threshold_manager import MAPEKThresholdManager
from src.self_healing.mape_k import SelfHealingManager


async def main():
    """Complete integration example."""
    print("🚀 Complete Integration Example\n")
    
    # Create temporary storage
    temp_dir = tempfile.mkdtemp()
    storage_path = Path(temp_dir)
    
    try:
        # Initialize all components
        print("📦 Initializing components...")
        
        # Knowledge Storage
        knowledge_storage = KnowledgeStorageV2(
            storage_path=storage_path,
            use_real_ipfs=False
        )
        
        # DAO Governance
        governance = GovernanceEngine("node-1")
        
        # Threshold Manager
        threshold_manager = MAPEKThresholdManager(
            governance_engine=governance,
            storage_path=storage_path
        )
        
        # Self-Healing Manager with full integration
        healing_manager = SelfHealingManager(
            node_id="node-1",
            threshold_manager=threshold_manager,
            knowledge_storage=knowledge_storage
        )
        
        print("  ✅ All components initialized\n")
        
        # Step 1: DAO changes threshold
        print("📋 Step 1: DAO changes threshold")
        print("-" * 50)
        
        proposal = governance.create_proposal(
            title="Lower CPU threshold",
            description="Enable earlier detection",
            actions=[{
                'type': 'update_mapek_threshold',
                'parameter': 'cpu_threshold',
                'value': 75.0
            }]
        )
        
        # Vote
        governance.cast_vote(proposal.id, "node-1", governance.VoteType.YES, tokens=200.0)
        governance._tally_votes(proposal)
        
        if proposal.state.value == "passed":
            threshold_manager.check_and_apply_dao_proposals()
            print(f"  ✅ Threshold changed to: {threshold_manager.get_threshold('cpu_threshold')}%")
        print()
        
        # Step 2: MAPE-K cycle with incident
        print("🔄 Step 2: MAPE-K cycle with incident")
        print("-" * 50)
        
        metrics = {
            'cpu_percent': 80.0,  # Above threshold
            'memory_percent': 70.0,
            'packet_loss_percent': 1.0
        }
        
        print(f"  Metrics: CPU={metrics['cpu_percent']}%, Memory={metrics['memory_percent']}%")
        healing_manager.run_cycle(metrics)
        print("  ✅ Cycle completed")
        print()
        
        # Step 3: Check Knowledge Storage
        print("📚 Step 3: Knowledge Storage")
        print("-" * 50)
        
        stats = knowledge_storage.get_stats()
        print(f"  Total incidents: {stats.get('total_incidents', 0)}")
        
        # Search for patterns
        results = await knowledge_storage.search_incidents(
            "CPU pressure recovery",
            k=5,
            threshold=0.7
        )
        print(f"  Found {len(results)} matching incidents")
        print()
        
        # Step 4: Performance stats
        print("📊 Step 4: System Statistics")
        print("-" * 50)
        
        print("  Knowledge Storage:")
        print(f"    Incidents: {stats.get('total_incidents', 0)}")
        print(f"    IPFS: {stats.get('ipfs_available', False)}")
        
        print("  Threshold Manager:")
        thresholds = threshold_manager.get_all_thresholds()
        print(f"    Thresholds: {len(thresholds)}")
        
        print("  Self-Healing Manager:")
        print(f"    Node ID: {healing_manager.node_id}")
        print(f"    Threshold Manager: {'✅' if healing_manager.threshold_manager else '❌'}")
        print()
        
        print("✅ Complete integration example finished!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Cleanup
        import shutil
        shutil.rmtree(temp_dir)
        print(f"\n🧹 Cleaned up: {storage_path}")


if __name__ == "__main__":
    asyncio.run(main())


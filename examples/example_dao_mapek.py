#!/usr/bin/env python3
"""
Example: DAO → MAPE-K Integration
=================================

Demonstrates how DAO governance affects MAPE-K thresholds:
- Create threshold proposal
- Vote on proposal
- Apply threshold changes
- Use in MAPE-K cycle
"""
import tempfile
from pathlib import Path

from src.dao.governance import GovernanceEngine, ProposalState
from src.dao.mapek_threshold_manager import MAPEKThresholdManager
from src.dao.mapek_threshold_proposal import MAPEKThresholdProposal, ThresholdChange
from src.self_healing.mape_k import SelfHealingManager


def main():
    """Example usage of DAO → MAPE-K integration."""
    print("🚀 DAO → MAPE-K Integration Example\n")
    
    # Create temporary storage
    temp_dir = tempfile.mkdtemp()
    storage_path = Path(temp_dir)
    
    try:
        # Initialize components
        governance = GovernanceEngine("node-1")
        threshold_manager = MAPEKThresholdManager(
            governance_engine=governance,
            storage_path=storage_path
        )
        
        print("✅ Components initialized\n")
        
        # Show current thresholds
        print("📊 Current Thresholds:")
        thresholds = threshold_manager.get_all_thresholds()
        for param, value in thresholds.items():
            print(f"  {param}: {value}")
        print()
        
        # Create threshold proposal
        print("📋 Creating threshold proposal...")
        proposal_manager = MAPEKThresholdProposal(governance)
        
        changes = [
            ThresholdChange(
                parameter="cpu_threshold",
                current_value=80.0,
                proposed_value=70.0,
                rationale="Enable earlier detection of CPU issues"
            ),
            ThresholdChange(
                parameter="memory_threshold",
                current_value=90.0,
                proposed_value=85.0,
                rationale="Reduce memory pressure before critical state"
            )
        ]
        
        proposal = proposal_manager.create_threshold_proposal(
            title="Lower CPU and Memory thresholds",
            changes=changes,
            rationale="Enable proactive healing by detecting issues earlier"
        )
        
        print(f"  ✅ Created proposal: {proposal.id}")
        print(f"  Title: {proposal.title}")
        print()
        
        # Vote on proposal
        print("🗳️  Voting on proposal...")
        governance.cast_vote(proposal.id, "node-1", governance.VoteType.YES, tokens=100.0)
        governance.cast_vote(proposal.id, "node-2", governance.VoteType.YES, tokens=150.0)
        governance.cast_vote(proposal.id, "node-3", governance.VoteType.YES, tokens=80.0)
        print("  ✅ 3 votes cast")
        print()
        
        # Tally votes
        print("📊 Tallying votes...")
        governance._tally_votes(proposal)
        print(f"  State: {proposal.state.value}")
        print()
        
        # Apply if passed
        if proposal.state == ProposalState.PASSED:
            print("✅ Proposal passed! Applying threshold changes...")
            applied = threshold_manager.check_and_apply_dao_proposals()
            print(f"  Applied {applied} proposal(s)")
            print()
            
            # Show new thresholds
            print("📊 New Thresholds:")
            new_thresholds = threshold_manager.get_all_thresholds()
            for param, value in new_thresholds.items():
                old_value = thresholds.get(param, 0)
                change = value - old_value
                print(f"  {param}: {old_value} → {value} ({change:+.1f})")
            print()
            
            # Use in SelfHealingManager
            print("🔄 Using in SelfHealingManager...")
            healing_manager = SelfHealingManager(
                node_id="node-1",
                threshold_manager=threshold_manager
            )
            
            # Run MAPE-K cycle
            metrics = {
                'cpu_percent': 75.0,  # Above new threshold (70.0)
                'memory_percent': 80.0,
                'packet_loss_percent': 2.0
            }
            
            print(f"  Running cycle with metrics: CPU={metrics['cpu_percent']}%")
            healing_manager.run_cycle(metrics)
            print("  ✅ Cycle completed (would trigger with new threshold)")
        else:
            print("❌ Proposal not passed")
        
        print("\n✅ Example completed successfully!")
        
    finally:
        # Cleanup
        import shutil
        shutil.rmtree(temp_dir)
        print(f"\n🧹 Cleaned up temporary storage: {storage_path}")


if __name__ == "__main__":
    main()


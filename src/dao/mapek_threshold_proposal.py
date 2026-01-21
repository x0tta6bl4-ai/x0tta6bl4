"""
DAO Proposal for MAPE-K Threshold Changes
==========================================

Allows DAO to change MAPE-K thresholds through governance.
"""
import logging
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from src.dao.governance import GovernanceEngine, Proposal, ProposalState
from src.dao.quadratic_voting import QuadraticVoting, Vote

logger = logging.getLogger(__name__)

# Импорт для интеграции с MAPEKThresholdManager
try:
    from src.dao.mapek_threshold_manager import MAPEKThresholdManager
    THRESHOLD_MANAGER_AVAILABLE = True
except ImportError:
    THRESHOLD_MANAGER_AVAILABLE = False
    logger.warning("MAPEKThresholdManager not available, using defaults")


@dataclass
class ThresholdChange:
    """Proposed threshold change."""
    parameter: str  # e.g., "cpu_threshold"
    current_value: float
    proposed_value: float
    rationale: str = ""


class MAPEKThresholdProposal:
    """
    Proposal to change MAPE-K thresholds.
    
    Example:
    - Change CPU threshold from 80% to 70%
    - Change memory threshold from 90% to 85%
    - Change check interval from 60s to 45s
    """
    
    def __init__(
        self,
        governance_engine: GovernanceEngine,
        threshold_manager: Optional['MAPEKThresholdManager'] = None
    ):
        self.governance = governance_engine
        self.quadratic_voting = QuadraticVoting()
        self.threshold_manager = threshold_manager
    
    def create_threshold_proposal(
        self,
        title: str,
        changes: List[ThresholdChange],
        rationale: str = "",
        duration_seconds: float = 48 * 3600  # 48 hours
    ) -> Proposal:
        """
        Create a proposal to change MAPE-K thresholds.
        
        Args:
            title: Proposal title
            changes: List of threshold changes
            rationale: Explanation for changes
            duration_seconds: Voting duration
            
        Returns:
            Created proposal
        """
        description = f"""
        {rationale}
        
        Proposed changes:
        """
        for change in changes:
            description += f"\n- {change.parameter}: {change.current_value} → {change.proposed_value}"
            if change.rationale:
                description += f" ({change.rationale})"
        
        # Create actions (what will be executed if proposal passes)
        actions = []
        for change in changes:
            actions.append({
                'type': 'update_mapek_threshold',
                'parameter': change.parameter,
                'value': change.proposed_value
            })
        
        proposal = self.governance.create_proposal(
            title=title,
            description=description,
            duration_seconds=duration_seconds,
            actions=actions
        )
        
        # Store threshold changes in proposal metadata
        proposal.threshold_changes = changes  # type: ignore
        
        logger.info(f"📋 Created threshold proposal: {proposal.id}")
        return proposal
    
    def execute_threshold_proposal(self, proposal: Proposal) -> bool:
        """
        Execute threshold proposal (after it passes).
        
        Args:
            proposal: Passed proposal
            
        Returns:
            True if executed successfully
        """
        if proposal.state != ProposalState.PASSED:
            logger.error(f"❌ Proposal {proposal.id} not passed, cannot execute")
            return False
        
        # Execute actions
        for action in proposal.actions:
            if action['type'] == 'update_mapek_threshold':
                parameter = action['parameter']
                value = action['value']
                logger.info(f"✅ Executing: {parameter} = {value}")
                
                # Update actual MAPE-K thresholds via threshold manager
                if self.threshold_manager:
                    try:
                        self.threshold_manager.update_threshold(parameter, value)
                        logger.info(f"✅ Updated threshold {parameter} = {value} via ThresholdManager")
                    except Exception as e:
                        logger.error(f"❌ Failed to update threshold via ThresholdManager: {e}")
                        return False
                else:
                    logger.warning(f"⚠️ ThresholdManager not available, threshold {parameter} = {value} not applied")
        
        proposal.state = ProposalState.EXECUTED
        logger.info(f"✅ Threshold proposal executed: {proposal.id}")
        return True
    
    def get_current_thresholds(self) -> Dict[str, float]:
        """
        Get current MAPE-K thresholds.
        
        Returns:
            Dict of parameter -> value
        """
        # Read from actual MAPE-K configuration via threshold manager
        if self.threshold_manager:
            try:
                thresholds = self.threshold_manager.get_all_thresholds()
                logger.debug(f"📊 Loaded thresholds from ThresholdManager: {thresholds}")
                return thresholds
            except Exception as e:
                logger.warning(f"⚠️ Failed to load thresholds from ThresholdManager: {e}")
        
        # Fallback to defaults if threshold manager not available
        defaults = {
            'cpu_threshold': 80.0,
            'memory_threshold': 90.0,
            'network_loss_threshold': 5.0,
            'latency_threshold': 100.0,
            'check_interval': 60.0
        }
        logger.debug(f"📊 Using default thresholds: {defaults}")
        return defaults


# Example usage
if __name__ == "__main__":
    # Create governance engine
    governance = GovernanceEngine("node-1")
    
    # Create threshold proposal manager
    threshold_manager = MAPEKThresholdProposal(governance)
    
    # Create proposal to lower CPU threshold
    changes = [
        ThresholdChange(
            parameter="cpu_threshold",
            current_value=80.0,
            proposed_value=70.0,
            rationale="Enable earlier detection of CPU issues"
        ),
        ThresholdChange(
            parameter="check_interval",
            current_value=60.0,
            proposed_value=45.0,
            rationale="Faster detection cycle"
        )
    ]
    
    proposal = threshold_manager.create_threshold_proposal(
        title="Lower CPU threshold for proactive healing",
        changes=changes,
        rationale="Reduce MTTR by detecting issues earlier"
    )
    
    print(f"Created proposal: {proposal.id}")
    print(f"Title: {proposal.title}")
    print(f"Actions: {proposal.actions}")


"""
MAPE-K Threshold Manager
========================

Manages MAPE-K thresholds with DAO governance integration.
Allows DAO to change thresholds and automatically applies them.
"""
import logging
import json
import time
from typing import Dict, Any, Optional, List
from pathlib import Path

from src.dao.governance import GovernanceEngine, Proposal, ProposalState
from src.dao.mapek_threshold_proposal import MAPEKThresholdProposal, ThresholdChange
from src.storage.ipfs_client import IPFSClient

logger = logging.getLogger(__name__)


class MAPEKThresholdManager:
    """
    Manages MAPE-K thresholds with DAO governance.
    
    Features:
    - Read current thresholds
    - Apply DAO-approved threshold changes
    - Store thresholds in IPFS (for distribution)
    - Verify threshold application
    """
    
    def __init__(
        self,
        governance_engine: GovernanceEngine,
        ipfs_client: Optional[IPFSClient] = None,
        storage_path: Optional[Path] = None
    ):
        """
        Initialize threshold manager.
        
        Args:
            governance_engine: DAO governance engine
            ipfs_client: IPFS client for distribution
            storage_path: Path for local storage
        """
        self.governance = governance_engine
        self.ipfs_client = ipfs_client
        self.storage_path = storage_path or Path("/var/lib/x0tta6bl4")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Current thresholds (loaded from storage or defaults)
        self.thresholds: Dict[str, float] = self._load_thresholds()
        
        # Threshold proposal manager (with reference to this manager for execution)
        self.proposal_manager = MAPEKThresholdProposal(governance_engine, threshold_manager=self)
        
        logger.info("✅ MAPE-K Threshold Manager initialized")
    
    def _load_thresholds(self) -> Dict[str, float]:
        """Load thresholds from storage or use defaults."""
        threshold_file = self.storage_path / "mapek_thresholds.json"
        
        if threshold_file.exists():
            try:
                with open(threshold_file, 'r') as f:
                    thresholds = json.load(f)
                    logger.info(f"📂 Loaded thresholds from {threshold_file}")
                    return thresholds
            except Exception as e:
                logger.warning(f"⚠️ Failed to load thresholds: {e}")
        
        # Default thresholds
        defaults = {
            'cpu_threshold': 80.0,
            'memory_threshold': 90.0,
            'network_loss_threshold': 5.0,
            'latency_threshold': 100.0,
            'check_interval': 60.0
        }
        logger.info("📂 Using default thresholds")
        return defaults
    
    def _save_thresholds(self):
        """Save thresholds to local storage."""
        threshold_file = self.storage_path / "mapek_thresholds.json"
        
        try:
            with open(threshold_file, 'w') as f:
                json.dump(self.thresholds, f, indent=2)
            logger.info(f"💾 Saved thresholds to {threshold_file}")
        except Exception as e:
            logger.error(f"❌ Failed to save thresholds: {e}")
    
    async def _publish_thresholds_to_ipfs(self) -> Optional[str]:
        """Publish thresholds to IPFS for distribution."""
        if not self.ipfs_client:
            return None
        
        try:
            data = {
                'thresholds': self.thresholds,
                'timestamp': time.time(),
                'version': '2.0'
            }
            data_json = json.dumps(data)
            cid = await self.ipfs_client.add(data_json, pin=True)
            logger.info(f"📦 Published thresholds to IPFS: {cid}")
            return cid
        except Exception as e:
            logger.error(f"❌ Failed to publish to IPFS: {e}")
            return None
    
    def get_threshold(self, parameter: str, default: Optional[float] = None) -> float:
        """
        Get current threshold for parameter.
        
        Args:
            parameter: Parameter name (e.g., "cpu_threshold")
            default: Default value if not found
            
        Returns:
            Threshold value
        """
        return self.thresholds.get(parameter, default or 80.0)
    
    def get_all_thresholds(self) -> Dict[str, float]:
        """Get all current thresholds."""
        return self.thresholds.copy()
    
    def update_threshold(self, parameter: str, value: float) -> bool:
        """
        Update a single threshold.
        
        Args:
            parameter: Parameter name (e.g., "cpu_threshold")
            value: New threshold value
            
        Returns:
            True if updated successfully
        """
        return self.apply_threshold_changes({parameter: value}, source="manual")
    
    def apply_threshold_changes(
        self,
        changes: Dict[str, float],
        source: str = "manual"
    ) -> bool:
        """
        Apply threshold changes.
        
        Args:
            changes: Dict of parameter -> new value
            source: Source of changes ("dao", "manual", etc.)
            
        Returns:
            True if applied successfully
        """
        try:
            # Apply changes
            for parameter, value in changes.items():
                old_value = self.thresholds.get(parameter)
                self.thresholds[parameter] = value
                logger.info(
                    f"✅ Updated threshold: {parameter} = {value} "
                    f"(was {old_value}, source: {source})"
                )
            
            # Save to local storage
            self._save_thresholds()
            
            # Publish to IPFS (async, non-blocking)
            if self.ipfs_client:
                try:
                    import asyncio
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.create_task(self._publish_thresholds_to_ipfs())
                    else:
                        loop.run_until_complete(self._publish_thresholds_to_ipfs())
                except Exception as e:
                    logger.warning(f"⚠️ Failed to publish to IPFS: {e}")
            
            logger.info(f"✅ Threshold changes applied (source: {source})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to apply threshold changes: {e}")
            return False
    
    def check_and_apply_dao_proposals(self) -> int:
        """
        Check for passed DAO proposals and apply threshold changes.
        
        Returns:
            Number of proposals applied
        """
        applied_count = 0
        
        # Check all proposals
        for proposal_id, proposal in self.governance.proposals.items():
            if proposal.state == ProposalState.PASSED:
                # Check if it's a threshold proposal
                if hasattr(proposal, 'threshold_changes') or any(
                    action.get('type') == 'update_mapek_threshold'
                    for action in proposal.actions
                ):
                    # Extract threshold changes from actions
                    changes = {}
                    for action in proposal.actions:
                        if action.get('type') == 'update_mapek_threshold':
                            parameter = action.get('parameter')
                            value = action.get('value')
                            if parameter and value is not None:
                                changes[parameter] = value
                    
                    if changes:
                        # Apply changes
                        if self.apply_threshold_changes(changes, source="dao"):
                            # Mark proposal as executed
                            self.governance.execute_proposal(proposal_id)
                            applied_count += 1
                            logger.info(f"✅ Applied DAO proposal: {proposal_id}")
        
        return applied_count
    
    def create_threshold_proposal(
        self,
        title: str,
        changes: List[ThresholdChange],
        rationale: str = ""
    ) -> Proposal:
        """
        Create a proposal to change thresholds.
        
        Args:
            title: Proposal title
            changes: List of threshold changes
            rationale: Explanation
            
        Returns:
            Created proposal
        """
        return self.proposal_manager.create_threshold_proposal(
            title=title,
            changes=changes,
            rationale=rationale
        )
    
    def verify_threshold_application(self, parameter: str, expected_value: float) -> bool:
        """
        Verify that threshold was applied correctly.
        
        Args:
            parameter: Parameter name
            expected_value: Expected value
            
        Returns:
            True if matches
        """
        current_value = self.get_threshold(parameter)
        matches = abs(current_value - expected_value) < 0.01  # Allow small floating point differences
        
        if not matches:
            logger.warning(
                f"⚠️ Threshold mismatch: {parameter} = {current_value}, "
                f"expected {expected_value}"
            )
        
        return matches


# Helper function to create threshold manager
def create_threshold_manager(
    governance_engine: GovernanceEngine,
    node_id: str = "default"
) -> MAPEKThresholdManager:
    """
    Create threshold manager with IPFS integration.
    
    Args:
        governance_engine: DAO governance engine
        node_id: Node identifier
        
    Returns:
        Threshold manager instance
    """
    from src.storage.ipfs_client import IPFSClient
    
    # Create IPFS client
    ipfs_client = IPFSClient()
    
    # Create threshold manager
    manager = MAPEKThresholdManager(
        governance_engine=governance_engine,
        ipfs_client=ipfs_client
    )
    
    return manager


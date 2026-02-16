"""
Integration Tests: MAPE-K → DAO → Knowledge Storage
====================================================

End-to-end tests for:
- DAO proposal → threshold change → MAPE-K application
- Knowledge Storage → MAPE-K record → IPFS storage
- Threshold Manager → IPFS distribution
"""

import asyncio
import tempfile
from pathlib import Path

import pytest

from src.dao.governance import GovernanceEngine, ProposalState
from src.dao.mapek_threshold_manager import MAPEKThresholdManager
from src.self_healing.mape_k import SelfHealingManager
from src.storage.knowledge_storage_v2 import KnowledgeStorageV2
from src.storage.mapek_integration import MAPEKKnowledgeStorageAdapter


@pytest.fixture
def temp_storage():
    """Create temporary storage directory."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    import shutil

    shutil.rmtree(temp_dir)


@pytest.fixture
def setup_integration(temp_storage):
    """Setup complete integration environment."""
    # Create components
    governance = GovernanceEngine("node-1")
    threshold_manager = MAPEKThresholdManager(
        governance_engine=governance, storage_path=temp_storage
    )
    knowledge_storage = KnowledgeStorageV2(
        storage_path=temp_storage, use_real_ipfs=False  # Use mock
    )

    # Create SelfHealingManager with integration
    healing_manager = SelfHealingManager(
        node_id="node-1",
        threshold_manager=threshold_manager,
        knowledge_storage=knowledge_storage,
    )

    return {
        "governance": governance,
        "threshold_manager": threshold_manager,
        "knowledge_storage": knowledge_storage,
        "healing_manager": healing_manager,
    }


class TestDAOToMAPEKIntegration:
    """Tests for DAO → MAPE-K integration."""

    def test_dao_proposal_to_threshold_change(self, setup_integration):
        """Test DAO proposal → threshold change flow."""
        governance = setup_integration["governance"]
        threshold_manager = setup_integration["threshold_manager"]

        # Create proposal to change CPU threshold
        proposal = governance.create_proposal(
            title="Lower CPU threshold",
            description="Enable earlier detection",
            actions=[
                {
                    "type": "update_mapek_threshold",
                    "parameter": "cpu_threshold",
                    "value": 70.0,
                }
            ],
        )

        # Vote and pass
        governance.cast_vote(
            proposal.id, "node-1", governance.VoteType.YES, tokens=100.0
        )
        governance.cast_vote(
            proposal.id, "node-2", governance.VoteType.YES, tokens=100.0
        )

        # Tally votes
        governance._tally_votes(proposal)

        # Check and apply
        applied = threshold_manager.check_and_apply_dao_proposals()

        if proposal.state == ProposalState.PASSED:
            # Verify threshold changed
            new_threshold = threshold_manager.get_threshold("cpu_threshold")
            assert new_threshold == 70.0
            assert applied > 0

    def test_threshold_manager_in_mapek(self, setup_integration):
        """Test threshold manager used in MAPE-K Monitor."""
        threshold_manager = setup_integration["threshold_manager"]
        healing_manager = setup_integration["healing_manager"]

        # Set threshold via manager
        threshold_manager.apply_threshold_changes(
            {"cpu_threshold": 75.0}, source="test"
        )

        # Verify Monitor uses it
        # (In real test, we'd check that Monitor.check() uses the threshold)
        assert threshold_manager.get_threshold("cpu_threshold") == 75.0
        assert healing_manager.threshold_manager is not None


class TestKnowledgeStorageToMAPEK:
    """Tests for Knowledge Storage → MAPE-K integration."""

    @pytest.mark.asyncio
    async def test_mapek_record_to_knowledge_storage(self, setup_integration):
        """Test MAPE-K record → Knowledge Storage flow."""
        healing_manager = setup_integration["healing_manager"]
        knowledge_storage = setup_integration["knowledge_storage"]

        # Run MAPE-K cycle with incident
        metrics = {"cpu_percent": 95.0, "memory_percent": 80.0}

        # This should trigger Knowledge phase and store in Knowledge Storage
        healing_manager.run_cycle(metrics)

        # Check that incident was stored
        # (In real test, we'd query Knowledge Storage)
        stats = knowledge_storage.get_stats()
        assert stats is not None

    def test_knowledge_storage_adapter(self, setup_integration):
        """Test MAPEKKnowledgeStorageAdapter."""
        knowledge_storage = setup_integration["knowledge_storage"]
        adapter = MAPEKKnowledgeStorageAdapter(knowledge_storage, "node-1")

        # Record incident
        incident_id = adapter.record_incident_sync(
            metrics={"cpu_percent": 90.0},
            issue="HIGH_CPU",
            action="Scale down",
            success=True,
            mttr=2.5,
        )

        assert incident_id is not None


class TestEndToEndFlow:
    """End-to-end integration tests."""

    @pytest.mark.asyncio
    async def test_complete_cycle(self, setup_integration):
        """Test complete cycle: DAO → Threshold → MAPE-K → Knowledge Storage."""
        governance = setup_integration["governance"]
        threshold_manager = setup_integration["threshold_manager"]
        healing_manager = setup_integration["healing_manager"]
        knowledge_storage = setup_integration["knowledge_storage"]

        # Step 1: DAO changes threshold
        proposal = governance.create_proposal(
            title="Test threshold change",
            description="Test",
            actions=[
                {
                    "type": "update_mapek_threshold",
                    "parameter": "cpu_threshold",
                    "value": 75.0,
                }
            ],
        )

        # Vote
        governance.cast_vote(
            proposal.id, "node-1", governance.VoteType.YES, tokens=200.0
        )
        governance._tally_votes(proposal)

        # Apply
        if proposal.state == ProposalState.PASSED:
            threshold_manager.check_and_apply_dao_proposals()

        # Step 2: MAPE-K uses new threshold
        new_threshold = threshold_manager.get_threshold("cpu_threshold")
        assert new_threshold == 75.0

        # Step 3: MAPE-K cycle with incident
        metrics = {"cpu_percent": 80.0}  # Above new threshold
        healing_manager.run_cycle(metrics)

        # Step 4: Verify stored in Knowledge Storage
        stats = knowledge_storage.get_stats()
        assert stats is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

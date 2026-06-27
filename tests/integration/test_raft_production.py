"""
Integration tests for Production Raft Consensus.

Tests production-ready Raft with:
- Persistent storage
- Snapshot support
- State recovery
"""

import shutil
import tempfile
from pathlib import Path

import pytest

try:
    from src.consensus.raft_production import (ProductionRaftNode,
                                               RaftPersistentStorage,
                                               get_production_raft_node)

    RAFT_PRODUCTION_AVAILABLE = True
except ImportError:
    RAFT_PRODUCTION_AVAILABLE = False
    ProductionRaftNode = None  # type: ignore
    RaftPersistentStorage = None  # type: ignore


@pytest.mark.skipif(
    not RAFT_PRODUCTION_AVAILABLE, reason="Production Raft not available"
)
class TestRaftProductionIntegration:
    """Integration tests for Production Raft"""

    @pytest.fixture
    def temp_storage(self):
        """Create temporary storage directory"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    def test_persistent_storage_save_load(self, temp_storage):
        """Test persistent storage save and load"""
        storage = RaftPersistentStorage(storage_path=temp_storage)

        # Save state
        storage.save_state("node-1", term=5, voted_for="node-2")

        # Load state
        state = storage.load_state()

        assert state is not None
        assert state["current_term"] == 5
        assert state["voted_for"] == "node-2"

    def test_production_node_initialization(self, temp_storage):
        """Test production node initialization"""
        node = ProductionRaftNode(
            node_id="node-1", peers=["node-2", "node-3"], storage_path=temp_storage
        )

        assert node.node_id == "node-1"
        assert node.peers == ["node-2", "node-3"]
        assert node.storage is not None

    def test_production_node_status(self, temp_storage):
        """Test production node status"""
        node = ProductionRaftNode(
            node_id="node-1", peers=["node-2", "node-3"], storage_path=temp_storage
        )

        status = node.get_status()

        assert status["node_id"] == "node-1"
        assert "state" in status
        assert "term" in status
        assert "commit_index" in status
        assert "log_length" in status

    def test_snapshot_creation(self, temp_storage):
        """Test snapshot creation"""
        node = ProductionRaftNode(
            node_id="node-1", peers=["node-2", "node-3"], storage_path=temp_storage
        )

        snapshot_data = {"key": "value", "count": 42}
        success = node.create_snapshot(
            last_included_index=10, snapshot_data=snapshot_data
        )

        assert success is True

        # Verify snapshot file exists in production snapshot directory.
        # Default create_snapshot() uses compressed JSON.
        snapshot_dir = Path(temp_storage) / "snapshots"
        snapshot_file = snapshot_dir / "snapshot_0000000010.json.gz"
        fallback_file = snapshot_dir / "snapshot_0000000010.json"
        assert snapshot_file.exists() or fallback_file.exists()


@pytest.mark.skipif(
    not RAFT_PRODUCTION_AVAILABLE, reason="Production Raft not available"
)
class TestRaftProductionE2E:
    """End-to-end tests for Production Raft"""

    @pytest.fixture
    def temp_storage(self):
        """Create temporary storage directory"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    def test_complete_raft_lifecycle(self, temp_storage):
        """Test complete Raft lifecycle with persistence"""
        # Create node
        node = ProductionRaftNode(
            node_id="node-1", peers=["node-2", "node-3"], storage_path=temp_storage
        )

        # Get initial status
        status1 = node.get_status()
        initial_term = status1["term"]

        # Create new node (simulating restart)
        node2 = ProductionRaftNode(
            node_id="node-1", peers=["node-2", "node-3"], storage_path=temp_storage
        )

        # Should restore state
        status2 = node2.get_status()
        assert status2["term"] == initial_term

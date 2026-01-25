"""
Unit tests for Raft snapshot functionality.

Tests snapshot creation, persistence, and recovery.
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

try:
    from src.consensus.raft_production import (
        ProductionRaftNode,
        RaftPersistentStorage,
        get_production_raft_node
    )
    from src.consensus.raft_consensus import LogEntry
    RAFT_PRODUCTION_AVAILABLE = True
except ImportError:
    RAFT_PRODUCTION_AVAILABLE = False
    ProductionRaftNode = None
    RaftPersistentStorage = None


@pytest.mark.skipif(not RAFT_PRODUCTION_AVAILABLE, reason="Production Raft not available")
class TestSnapshotMetadata:
    """Test snapshot metadata storage"""
    
    @pytest.fixture
    def temp_storage(self):
        """Create temporary storage directory"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    def test_save_and_load_snapshot_metadata(self, temp_storage):
        """Test save and load snapshot metadata"""
        storage = RaftPersistentStorage(storage_path=temp_storage)
        
        # Save metadata
        assert storage.save_snapshot_metadata(10, 5)
        
        # Load metadata
        metadata = storage.load_snapshot_metadata()
        assert metadata is not None
        assert metadata["last_included_index"] == 10
        assert metadata["last_included_term"] == 5
        assert "timestamp" in metadata
    
    def test_load_snapshot_metadata_nonexistent(self, temp_storage):
        """Test loading non-existent snapshot metadata"""
        storage = RaftPersistentStorage(storage_path=temp_storage)
        metadata = storage.load_snapshot_metadata()
        assert metadata is None


@pytest.mark.skipif(not RAFT_PRODUCTION_AVAILABLE, reason="Production Raft not available")
class TestLogTruncation:
    """Test log truncation after snapshot"""
    
    @pytest.fixture
    def temp_storage(self):
        """Create temporary storage directory"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    def test_truncate_log_before_snapshot(self, temp_storage):
        """Test log truncation"""
        storage = RaftPersistentStorage(storage_path=temp_storage)
        
        # Create log with 10 entries
        log = [
            LogEntry(term=i, index=i, command=f"cmd_{i}", timestamp=datetime.now())
            for i in range(10)
        ]
        
        # Truncate at index 5
        truncated = storage.truncate_log_before_snapshot(5, log)
        
        assert len(truncated) == 5
        assert truncated[0].index == 5
        assert truncated[-1].index == 9
    
    def test_truncate_log_edge_cases(self, temp_storage):
        """Test log truncation edge cases"""
        storage = RaftPersistentStorage(storage_path=temp_storage)
        
        log = [
            LogEntry(term=i, index=i, command=f"cmd_{i}", timestamp=datetime.now())
            for i in range(5)
        ]
        
        # Truncate at invalid index (beyond log)
        truncated = storage.truncate_log_before_snapshot(10, log)
        assert len(truncated) == 5  # Should return unchanged log


@pytest.mark.skipif(not RAFT_PRODUCTION_AVAILABLE, reason="Production Raft not available")
class TestSnapshotCreation:
    """Test snapshot creation and persistence"""
    
    @pytest.fixture
    def temp_storage(self):
        """Create temporary storage directory"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    def test_create_snapshot(self, temp_storage):
        """Test creating a snapshot"""
        node = ProductionRaftNode(
            node_id="test-node",
            peers=["peer1", "peer2"],
            storage_path=temp_storage,
            network_enabled=False
        )
        
        # Add some log entries
        for i in range(1, 6):
            node.raft_node.log.append(LogEntry(
                term=1,
                index=i,
                command={"op": "set", "key": f"k{i}", "value": i},
                timestamp=datetime.now()
            ))
        
        # Create snapshot
        snapshot_data = {"state_version": 1, "keys": {"k1": 1, "k2": 2}}
        assert node.create_snapshot(3, snapshot_data, compress=False)
        
        # Verify snapshot file exists
        snapshot_file = node.storage.snapshot_dir / "snapshot_0000000003.json"
        assert snapshot_file.exists()
        
        # Verify metadata saved
        metadata = node.storage.load_snapshot_metadata()
        assert metadata["last_included_index"] == 3
        assert metadata["last_included_term"] == 1
        
        # Verify log was truncated
        assert len(node.raft_node.log) == 2  # Entries 3 and 4 remain (0-indexed)
    
    def test_create_compressed_snapshot(self, temp_storage):
        """Test creating a compressed snapshot"""
        node = ProductionRaftNode(
            node_id="test-node",
            peers=["peer1", "peer2"],
            storage_path=temp_storage,
            network_enabled=False
        )
        
        # Add log entries
        for i in range(1, 6):
            node.raft_node.log.append(LogEntry(
                term=1,
                index=i,
                command={"op": "set", "key": f"k{i}", "value": i},
                timestamp=datetime.now()
            ))
        
        # Create compressed snapshot
        snapshot_data = {"state_version": 1}
        assert node.create_snapshot(2, snapshot_data, compress=True)
        
        # Verify compressed file exists
        snapshot_file = node.storage.snapshot_dir / "snapshot_0000000002.json.gz"
        assert snapshot_file.exists()
    
    def test_snapshot_invalid_index(self, temp_storage):
        """Test snapshot with invalid index"""
        node = ProductionRaftNode(
            node_id="test-node",
            peers=["peer1", "peer2"],
            storage_path=temp_storage,
            network_enabled=False
        )
        
        # Try to snapshot at index beyond log
        assert not node.create_snapshot(100, {})


@pytest.mark.skipif(not RAFT_PRODUCTION_AVAILABLE, reason="Production Raft not available")
class TestSnapshotLoading:
    """Test snapshot loading and restoration"""
    
    @pytest.fixture
    def temp_storage(self):
        """Create temporary storage directory"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    def test_load_snapshot(self, temp_storage):
        """Test loading a snapshot"""
        node = ProductionRaftNode(
            node_id="test-node",
            peers=["peer1", "peer2"],
            storage_path=temp_storage,
            network_enabled=False
        )
        
        # Create log and snapshot
        for i in range(1, 6):
            node.raft_node.log.append(LogEntry(
                term=1,
                index=i,
                command={"op": "set", "key": f"k{i}", "value": i},
                timestamp=datetime.now()
            ))
        
        snapshot_data = {"state_version": 1, "data": [1, 2, 3]}
        node.create_snapshot(3, snapshot_data, compress=False)
        
        # Load the snapshot
        loaded = node.load_snapshot(3)
        assert loaded is not None
        assert loaded["last_included_index"] == 3
        assert loaded["data"] == snapshot_data
    
    def test_load_latest_snapshot(self, temp_storage):
        """Test loading latest snapshot"""
        node = ProductionRaftNode(
            node_id="test-node",
            peers=["peer1", "peer2"],
            storage_path=temp_storage,
            network_enabled=False
        )
        
        # Create log and multiple snapshots
        for i in range(1, 10):
            node.raft_node.log.append(LogEntry(
                term=1,
                index=i,
                command={"op": "set"},
                timestamp=datetime.now()
            ))
        
        # Create first snapshot
        node.create_snapshot(3, {"version": 1}, compress=False)
        
        # Create second snapshot
        for i in range(4, 8):
            node.raft_node.log.append(LogEntry(
                term=1,
                index=i,
                command={"op": "set"},
                timestamp=datetime.now()
            ))
        node.create_snapshot(6, {"version": 2}, compress=False)
        
        # Load latest (should be index 6)
        loaded = node.load_snapshot()
        assert loaded is not None
        assert loaded["last_included_index"] == 6
        assert loaded["data"]["version"] == 2
    
    def test_load_nonexistent_snapshot(self, temp_storage):
        """Test loading non-existent snapshot"""
        node = ProductionRaftNode(
            node_id="test-node",
            peers=["peer1", "peer2"],
            storage_path=temp_storage,
            network_enabled=False
        )
        
        loaded = node.load_snapshot(999)
        assert loaded is None


@pytest.mark.skipif(not RAFT_PRODUCTION_AVAILABLE, reason="Production Raft not available")
class TestSnapshotRestoration:
    """Test restoring node state from snapshots"""
    
    @pytest.fixture
    def temp_storage(self):
        """Create temporary storage directory"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    def test_restore_from_snapshot(self, temp_storage):
        """Test restoring node state from snapshot"""
        # Create first node and snapshot
        node1 = ProductionRaftNode(
            node_id="test-node",
            peers=["peer1", "peer2"],
            storage_path=temp_storage,
            network_enabled=False
        )
        
        # Create log and snapshot
        for i in range(1, 10):
            node1.raft_node.log.append(LogEntry(
                term=1,
                index=i,
                command={"op": "set"},
                timestamp=datetime.now()
            ))
        
        node1.raft_node.commit_index = 5
        node1.create_snapshot(5, {"state": "snapshot_state"}, compress=False)
        
        # Create second node that restores from snapshot
        node2 = ProductionRaftNode(
            node_id="test-node",
            peers=["peer1", "peer2"],
            storage_path=temp_storage,
            network_enabled=False
        )
        
        # Node2 should have restored from snapshot
        assert node2.raft_node.last_applied == 5
        assert node2.raft_node.commit_index >= 5
    
    def test_restore_from_snapshot_no_snapshot(self, temp_storage):
        """Test restore when no snapshot exists"""
        node = ProductionRaftNode(
            node_id="test-node",
            peers=["peer1", "peer2"],
            storage_path=temp_storage,
            network_enabled=False
        )
        
        # Should not fail even without snapshot
        assert node.restore_from_snapshot() is False
        assert node.raft_node.last_applied == 0


@pytest.mark.skipif(not RAFT_PRODUCTION_AVAILABLE, reason="Production Raft not available")
class TestSnapshotIntegration:
    """Integration tests for snapshot workflow"""
    
    @pytest.fixture
    def temp_storage(self):
        """Create temporary storage directory"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    def test_complete_snapshot_workflow(self, temp_storage):
        """Test complete snapshot creation and recovery workflow"""
        # Create node and populate log
        node = ProductionRaftNode(
            node_id="node1",
            peers=["node2", "node3"],
            storage_path=temp_storage,
            network_enabled=False
        )
        
        # Populate log with entries
        for i in range(1, 20):
            node.raft_node.log.append(LogEntry(
                term=1,
                index=i,
                command={"op": "put", "key": f"key_{i}", "value": f"value_{i}"},
                timestamp=datetime.now()
            ))
        
        initial_log_size = len(node.raft_node.log)
        
        # Create snapshot at index 15
        snapshot_data = {
            "keys": {f"key_{i}": f"value_{i}" for i in range(1, 16)},
            "snapshot_index": 15
        }
        assert node.create_snapshot(15, snapshot_data)
        
        # Verify log was truncated
        assert len(node.raft_node.log) < initial_log_size
        
        # Create new node instance and verify restoration
        node2 = ProductionRaftNode(
            node_id="node1",
            peers=["node2", "node3"],
            storage_path=temp_storage,
            network_enabled=False
        )
        
        # Should have restored snapshot
        assert node2.raft_node.last_applied == 15
        
        # Verify snapshot can be loaded
        loaded_snapshot = node2.load_snapshot()
        assert loaded_snapshot is not None
        assert loaded_snapshot["data"]["snapshot_index"] == 15
    
    def test_multiple_snapshots_sequence(self, temp_storage):
        """Test creating multiple snapshots in sequence"""
        node = ProductionRaftNode(
            node_id="node1",
            peers=["node2"],
            storage_path=temp_storage,
            network_enabled=False
        )
        
        # Create snapshots at different indices
        snapshots_created = []
        for snapshot_index in [10, 20, 30]:
            # Populate log up to snapshot index
            while len(node.raft_node.log) <= snapshot_index:
                idx = len(node.raft_node.log)
                node.raft_node.log.append(LogEntry(
                    term=1,
                    index=idx,
                    command={"data": idx},
                    timestamp=datetime.now()
                ))
            
            # Create snapshot
            assert node.create_snapshot(
                snapshot_index,
                {"snapshot_num": len(snapshots_created) + 1}
            )
            snapshots_created.append(snapshot_index)
        
        # Verify last snapshot is the one loaded
        latest = node.load_snapshot()
        assert latest is not None
        assert latest["last_included_index"] == 30

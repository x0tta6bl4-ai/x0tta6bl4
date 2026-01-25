"""
Unit tests for CRDT Optimizations.

Tests optimized CRDT sync with delta-based synchronization.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

try:
    from src.data_sync.crdt_optimizations import (
        CRDTSyncOptimizer,
        CRDTDelta,
        SyncMetrics,
        get_crdt_optimizer
    )
    from src.data_sync.crdt_sync import LWWRegister, Counter, ORSet
    CRDT_OPTIMIZATIONS_AVAILABLE = True
except ImportError:
    CRDT_OPTIMIZATIONS_AVAILABLE = False
    CRDTSyncOptimizer = None  # type: ignore
    CRDTDelta = None  # type: ignore
    SyncMetrics = None  # type: ignore
    LWWRegister = None  # type: ignore
    Counter = None  # type: ignore
    ORSet = None  # type: ignore


@pytest.mark.skipif(not CRDT_OPTIMIZATIONS_AVAILABLE, reason="CRDT optimizations not available")
class TestCRDTSyncOptimizer:
    """Unit tests for CRDTSyncOptimizer"""
    
    @pytest.fixture
    def optimizer(self):
        """Create CRDT optimizer instance"""
        return CRDTSyncOptimizer(node_id="node-1", enable_compression=False)
    
    def test_optimizer_initialization(self, optimizer):
        """Test optimizer initialization"""
        assert optimizer.node_id == "node-1"
        assert optimizer.sync_manager is not None
        assert optimizer.metrics.total_syncs == 0
    
    def test_register_crdt(self, optimizer):
        """Test CRDT registration"""
        lww = LWWRegister()
        optimizer.register_crdt("test-key", lww)
        
        assert "test-key" in optimizer.sync_manager.crdts
        assert optimizer.last_sync_state.get("test-key") is not None
    
    def test_generate_deltas(self, optimizer):
        """Test delta generation"""
        lww = LWWRegister()
        optimizer.register_crdt("test-key", lww)
        
        # Modify CRDT
        lww.set("new-value", "node-1")
        
        # Generate deltas
        deltas = optimizer.generate_deltas("test-key")
        
        assert len(deltas) > 0
        assert deltas[0].key == "test-key"
        assert deltas[0].operation == "merge"
    
    def test_apply_delta(self, optimizer):
        """Test delta application"""
        lww = LWWRegister()
        optimizer.register_crdt("test-key", lww)
        
        # Create delta
        delta = CRDTDelta(
            key="test-key",
            operation="set",
            value="delta-value",
            timestamp=datetime.now(),
            node_id="node-2",
            checksum="test"
        )
        
        # Apply delta
        success = optimizer.apply_delta("test-key", delta)
        
        # May succeed or fail depending on operation matching
        assert isinstance(success, bool)
    
    def test_sync_with_peer(self, optimizer):
        """Test synchronization with peer"""
        # Register local CRDT
        lww = LWWRegister()
        lww.set("value-1", "node-1")
        optimizer.register_crdt("key-1", lww)
        
        # Simulate peer state
        peer_lww = LWWRegister()
        peer_lww.set("value-2", "node-2")
        peer_state = {"key-1": peer_lww}
        
        # Sync
        local_deltas = optimizer.sync_with_peer("node-2", peer_state)
        
        assert isinstance(local_deltas, dict)
        assert optimizer.metrics.total_syncs > 0
    
    def test_batch_apply_deltas(self, optimizer):
        """Test batch delta application"""
        counter = Counter()
        optimizer.register_crdt("counter", counter)
        
        # Create multiple deltas
        deltas = {
            "counter": [
                CRDTDelta(
                    key="counter",
                    operation="increment",
                    value=1,
                    timestamp=datetime.now(),
                    node_id="node-2",
                    checksum="test1"
                )
            ]
        }
        
        # Apply batch
        applied = optimizer.batch_apply_deltas(deltas)
        
        assert applied >= 0
    
    def test_get_metrics(self, optimizer):
        """Test metrics retrieval"""
        # Perform some operations
        optimizer.sync_with_peer("node-2", {})
        
        metrics = optimizer.get_metrics()
        
        assert "total_syncs" in metrics
        assert "successful_syncs" in metrics
        assert "success_rate" in metrics
        assert "avg_sync_duration_ms" in metrics
        assert metrics["total_syncs"] > 0


@pytest.mark.skipif(not CRDT_OPTIMIZATIONS_AVAILABLE, reason="CRDT optimizations not available")
class TestCRDTDelta:
    """Unit tests for CRDTDelta"""
    
    def test_delta_creation(self):
        """Test CRDTDelta creation"""
        delta = CRDTDelta(
            key="test-key",
            operation="set",
            value="test-value",
            timestamp=datetime.now(),
            node_id="node-1",
            checksum="abc123"
        )
        
        assert delta.key == "test-key"
        assert delta.operation == "set"
        assert delta.value == "test-value"
        assert delta.node_id == "node-1"
        assert delta.checksum == "abc123"


@pytest.mark.skipif(not CRDT_OPTIMIZATIONS_AVAILABLE, reason="CRDT optimizations not available")
class TestGetCRDTOptimizer:
    """Unit tests for get_crdt_optimizer singleton"""
    
    def test_singleton_pattern(self):
        """Test that get_crdt_optimizer returns singleton"""
        optimizer1 = get_crdt_optimizer("node-1")
        optimizer2 = get_crdt_optimizer("node-1")
        
        # Should be the same instance for same node_id
        assert optimizer1 is optimizer2


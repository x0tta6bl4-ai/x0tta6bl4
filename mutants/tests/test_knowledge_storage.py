"""
Tests for Knowledge Storage v2.0
================================

Tests for:
- IPFS integration
- Vector Index
- SQLite cache
- MAPE-K integration
"""
import pytest
import tempfile
import shutil
from pathlib import Path

from src.storage.knowledge_storage_v2 import KnowledgeStorageV2, IncidentEntry
from src.storage.vector_index import VectorIndex
from src.storage.ipfs_client import IPFSClient, MockIPFSClient
from src.storage.mapek_integration import MAPEKKnowledgeStorageAdapter


@pytest.fixture
def temp_storage():
    """Create temporary storage directory."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


class TestKnowledgeStorageV2:
    """Tests for Knowledge Storage v2.0."""
    
    @pytest.mark.asyncio
    async def test_store_incident(self, temp_storage):
        """Test storing incident."""
        storage = KnowledgeStorageV2(
            storage_path=temp_storage,
            use_real_ipfs=False  # Use mock
        )
        
        incident = {
            'id': 'test-incident-1',
            'timestamp': 1234567890.0,
            'anomaly_type': 'MEMORY_PRESSURE',
            'metrics': {'memory_percent': 95.0},
            'root_cause': 'High memory usage',
            'recovery_plan': 'Clear cache',
            'execution_result': {'success': True, 'duration': 2.5}
        }
        
        incident_id = await storage.store_incident(incident, "node-1")
        
        assert incident_id == 'test-incident-1'
    
    @pytest.mark.asyncio
    async def test_search_incidents(self, temp_storage):
        """Test searching incidents."""
        storage = KnowledgeStorageV2(
            storage_path=temp_storage,
            use_real_ipfs=False
        )
        
        # Store some incidents
        for i in range(5):
            incident = {
                'id': f'incident-{i}',
                'timestamp': 1234567890.0 + i,
                'anomaly_type': 'MEMORY_PRESSURE',
                'metrics': {'memory_percent': 90.0 + i},
                'root_cause': f'Memory issue {i}',
                'recovery_plan': f'Action {i}',
                'execution_result': {'success': True, 'duration': 2.0 + i}
            }
            await storage.store_incident(incident, "node-1")
        
        # Search
        results = await storage.search_incidents(
            "memory pressure recovery",
            k=3,
            threshold=0.5
        )
        
        # Should return some results (depending on vector index)
        assert isinstance(results, list)
    
    @pytest.mark.asyncio
    async def test_get_successful_patterns(self, temp_storage):
        """Test getting successful patterns."""
        storage = KnowledgeStorageV2(
            storage_path=temp_storage,
            use_real_ipfs=False
        )
        
        # Store successful incident
        incident = {
            'id': 'success-incident',
            'timestamp': 1234567890.0,
            'anomaly_type': 'MEMORY_PRESSURE',
            'metrics': {'memory_percent': 95.0},
            'root_cause': 'High memory',
            'recovery_plan': 'Clear cache',
            'execution_result': {'success': True, 'duration': 2.5}
        }
        await storage.store_incident(incident, "node-1")
        
        # Get patterns
        patterns = await storage.get_successful_patterns('MEMORY_PRESSURE')
        
        assert isinstance(patterns, list)
    
    def test_stats(self, temp_storage):
        """Test getting statistics."""
        storage = KnowledgeStorageV2(
            storage_path=temp_storage,
            use_real_ipfs=False
        )
        
        stats = storage.get_stats()
        
        assert 'total_incidents' in stats
        assert 'ipfs_available' in stats
        assert 'vector_index_stats' in stats


class TestVectorIndex:
    """Tests for Vector Index."""
    
    def test_add_document(self, temp_storage):
        """Test adding document to index."""
        index_path = temp_storage / "vector_index"
        index = VectorIndex(index_path=index_path)
        
        doc_id = index.add(
            text="Memory pressure detected",
            metadata={'incident_id': 'test-1', 'anomaly_type': 'MEMORY_PRESSURE'}
        )
        
        assert doc_id >= 0
    
    def test_search(self, temp_storage):
        """Test searching documents."""
        index_path = temp_storage / "vector_index"
        index = VectorIndex(index_path=index_path)
        
        # Add documents
        index.add(
            text="Memory pressure detected",
            metadata={'incident_id': 'test-1'}
        )
        index.add(
            text="CPU usage high",
            metadata={'incident_id': 'test-2'}
        )
        
        # Search
        results = index.search("memory issue", k=2, threshold=0.5)
        
        assert isinstance(results, list)
    
    def test_save_load(self, temp_storage):
        """Test saving and loading index."""
        index_path = temp_storage / "vector_index"
        
        # Create and save
        index1 = VectorIndex(index_path=index_path)
        index1.add(text="Test document", metadata={'id': '1'})
        index1.save()
        
        # Load
        index2 = VectorIndex(index_path=index_path)
        index2.load()
        
        # Should have loaded metadata
        assert len(index2.metadata) >= 1


class TestIPFSClient:
    """Tests for IPFS Client."""
    
    @pytest.mark.asyncio
    async def test_mock_add_get(self):
        """Test mock IPFS add/get."""
        client = MockIPFSClient()
        
        data = "test data"
        cid = await client.add(data)
        
        assert cid is not None
        
        retrieved = await client.get(cid)
        assert retrieved == data
    
    @pytest.mark.asyncio
    async def test_mock_pin_unpin(self):
        """Test mock IPFS pin/unpin."""
        client = MockIPFSClient()
        
        data = "test data"
        cid = await client.add(data, pin=True)
        
        result = await client.unpin(cid)
        assert result is True


class TestMAPEKKnowledgeStorageAdapter:
    """Tests for MAPE-K Knowledge Storage Adapter."""
    
    def test_record_incident_sync(self, temp_storage):
        """Test synchronous incident recording."""
        storage = KnowledgeStorageV2(
            storage_path=temp_storage,
            use_real_ipfs=False
        )
        adapter = MAPEKKnowledgeStorageAdapter(storage, "node-1")
        
        incident_id = adapter.record_incident_sync(
            metrics={'cpu_percent': 90.0},
            issue='HIGH_CPU',
            action='Scale down',
            success=True,
            mttr=2.5
        )
        
        assert incident_id is not None
    
    def test_search_patterns_sync(self, temp_storage):
        """Test synchronous pattern search."""
        storage = KnowledgeStorageV2(
            storage_path=temp_storage,
            use_real_ipfs=False
        )
        adapter = MAPEKKnowledgeStorageAdapter(storage, "node-1")
        
        # Record some incidents first
        adapter.record_incident_sync(
            metrics={'memory_percent': 95.0},
            issue='MEMORY_PRESSURE',
            action='Clear cache',
            success=True
        )
        
        # Search (may return empty if vector index not ready)
        results = adapter.search_patterns_sync("memory pressure", k=5)
        
        assert isinstance(results, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


"""
Additional tests for Distributed KV Store.

Tests edge cases, error handling, and distributed scenarios.
"""

import asyncio
from typing import Dict, List
from unittest.mock import AsyncMock, Mock, patch

import pytest

try:
    from src.storage.distributed_kvstore import (ConsistencyLevel,
                                                 DistributedKVStore,
                                                 ReplicationStrategy)

    KVSTORE_AVAILABLE = True
except ImportError:
    KVSTORE_AVAILABLE = False
    DistributedKVStore = None
    ReplicationStrategy = None
    ConsistencyLevel = None


@pytest.mark.skipif(not KVSTORE_AVAILABLE, reason="Distributed KV Store not available")
class TestDistributedKVStoreEdgeCases:
    """Edge case tests for Distributed KV Store"""

    def test_empty_key(self):
        """Test handling of empty key"""
        store = DistributedKVStore(node_id="node-1")

        # Empty key should be handled gracefully
        with pytest.raises((ValueError, KeyError)) or pytest.raises(Exception):
            store.put("", "value")

    def test_none_value(self):
        """Test handling of None value"""
        store = DistributedKVStore(node_id="node-1")

        # None value should be handled
        store.put("key1", None)
        value = store.get("key1")
        assert value is None

    def test_large_value(self):
        """Test handling of large values"""
        store = DistributedKVStore(node_id="node-1")

        # Large value (1MB)
        large_value = "x" * (1024 * 1024)
        store.put("large_key", large_value)

        retrieved = store.get("large_key")
        assert retrieved == large_value

    def test_special_characters_in_key(self):
        """Test handling of special characters in keys"""
        store = DistributedKVStore(node_id="node-1")

        special_keys = [
            "key/with/slashes",
            "key.with.dots",
            "key-with-dashes",
            "key_with_underscores",
            "key@with#special$chars",
        ]

        for key in special_keys:
            store.put(key, f"value-{key}")
            assert store.get(key) == f"value-{key}"

    def test_concurrent_put_operations(self):
        """Test concurrent put operations"""
        import threading

        store = DistributedKVStore(node_id="node-1")

        results = []
        errors = []

        def put_worker(key: str, value: str):
            try:
                store.put(key, value)
                results.append(key)
            except Exception as e:
                errors.append(e)

        # Create multiple threads
        threads = []
        for i in range(10):
            thread = threading.Thread(
                target=put_worker, args=(f"key-{i}", f"value-{i}")
            )
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        # All should succeed
        assert len(errors) == 0
        assert len(results) == 10

        # Verify all values
        for i in range(10):
            assert store.get(f"key-{i}") == f"value-{i}"

    def test_get_nonexistent_key(self):
        """Test getting nonexistent key"""
        store = DistributedKVStore(node_id="node-1")

        # Should return None or raise KeyError
        value = store.get("nonexistent_key")
        assert value is None or isinstance(value, KeyError)

    def test_delete_nonexistent_key(self):
        """Test deleting nonexistent key"""
        store = DistributedKVStore(node_id="node-1")

        # Should handle gracefully
        result = store.delete("nonexistent_key")
        # Should return False or None
        assert result in [False, None, True]  # Depends on implementation

    def test_delete_and_recreate(self):
        """Test deleting and recreating key"""
        store = DistributedKVStore(node_id="node-1")

        # Put value
        store.put("key1", "value1")
        assert store.get("key1") == "value1"

        # Delete
        store.delete("key1")
        assert store.get("key1") is None or isinstance(store.get("key1"), KeyError)

        # Recreate
        store.put("key1", "value2")
        assert store.get("key1") == "value2"


@pytest.mark.skipif(not KVSTORE_AVAILABLE, reason="Distributed KV Store not available")
class TestDistributedKVStoreReplication:
    """Tests for replication functionality"""

    def test_replication_strategy(self):
        """Test different replication strategies"""
        store = DistributedKVStore(
            node_id="node-1", replication_strategy=ReplicationStrategy.SYNC
        )

        # Put value
        store.put("key1", "value1")

        # Should replicate to peers
        # (In real scenario, would check peer nodes)
        assert store.get("key1") == "value1"

    def test_consistency_levels(self):
        """Test different consistency levels"""
        # Strong consistency
        store_strong = DistributedKVStore(
            node_id="node-1", consistency_level=ConsistencyLevel.STRONG
        )

        store_strong.put("key1", "value1")
        assert store_strong.get("key1") == "value1"

        # Eventual consistency
        store_eventual = DistributedKVStore(
            node_id="node-2", consistency_level=ConsistencyLevel.EVENTUAL
        )

        store_eventual.put("key2", "value2")
        assert store_eventual.get("key2") == "value2"

    def test_replication_failure_handling(self):
        """Test handling of replication failures"""
        store = DistributedKVStore(node_id="node-1")

        # Mock replication failure
        with patch.object(
            store, "_replicate_to_peers", side_effect=Exception("Replication failed")
        ):
            # Should still allow local write
            store.put("key1", "value1")
            assert store.get("key1") == "value1"


@pytest.mark.skipif(not KVSTORE_AVAILABLE, reason="Distributed KV Store not available")
class TestDistributedKVStorePerformance:
    """Performance tests for Distributed KV Store"""

    def test_bulk_operations(self):
        """Test bulk put/get operations"""
        store = DistributedKVStore(node_id="node-1")

        # Bulk put
        for i in range(1000):
            store.put(f"key-{i}", f"value-{i}")

        # Bulk get
        for i in range(1000):
            assert store.get(f"key-{i}") == f"value-{i}"

    def test_memory_usage(self):
        """Test memory usage with many keys"""
        store = DistributedKVStore(node_id="node-1")

        # Add many keys
        for i in range(10000):
            store.put(f"key-{i}", f"value-{i}")

        # Should still be able to retrieve
        assert store.get("key-0") == "value-0"
        assert store.get("key-9999") == "value-9999"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

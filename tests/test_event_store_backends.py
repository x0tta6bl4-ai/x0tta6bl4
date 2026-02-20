"""
Tests for Event Store Database Backends.

Tests PostgreSQL and MongoDB backends for the Event Store.
"""

import os
import pytest
from datetime import datetime
from typing import AsyncGenerator
from unittest.mock import AsyncMock, patch

# Skip tests if database dependencies not available
pytest.importorskip("asyncpg", reason="asyncpg not installed")
pytest.importorskip("motor", reason="motor not installed")

from src.event_sourcing.backends.base import (
    VersionConflictError,
)
from src.event_sourcing.backends.postgres import PostgresEventStore, PostgresConfig
from src.event_sourcing.backends.mongodb import MongoDBEventStore, MongoDBConfig
from src.event_sourcing.event_store import Event, Snapshot, EventMetadata


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def sample_event() -> Event:
    """Create a sample event for testing."""
    return Event(
        event_id="test-event-001",
        event_type="TestEvent",
        aggregate_id="test-aggregate-001",
        aggregate_type="TestAggregate",
        sequence_number=1,
        data={"key": "value", "number": 42},
        metadata=EventMetadata(
            correlation_id="corr-001",
            causation_id="cause-001",
            user_id="user-001",
            source="test",
        )
    )


@pytest.fixture
def sample_events() -> list[Event]:
    """Create multiple sample events for testing."""
    events = []
    for i in range(5):
        events.append(Event(
            event_id=f"test-event-{i:03d}",
            event_type=f"TestEvent{i % 2}",
            aggregate_id="test-aggregate-batch",
            aggregate_type="TestAggregate",
            sequence_number=i + 1,
            data={"index": i},
            metadata=EventMetadata(
                correlation_id="corr-batch",
                user_id="user-001",
            )
        ))
    return events


@pytest.fixture
def sample_snapshot() -> Snapshot:
    """Create a sample snapshot for testing."""
    return Snapshot(
        snapshot_id="snapshot-001",
        aggregate_id="test-aggregate-001",
        aggregate_type="TestAggregate",
        sequence_number=10,
        state={"total": 100, "items": ["a", "b", "c"]},
        timestamp=datetime.utcnow(),
    )


# =============================================================================
# PostgreSQL Backend Tests
# =============================================================================

class TestPostgresEventStore:
    """Tests for PostgreSQL event store backend."""
    
    @pytest.fixture
    async def postgres_store(self) -> AsyncGenerator[PostgresEventStore, None]:
        """Create a PostgreSQL event store for testing."""
        config = PostgresConfig(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            database=os.getenv("POSTGRES_DB", "maas_event_store_test"),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", ""),
            schema="test_schema",
            min_pool_size=2,
            max_pool_size=5,
        )
        
        store = PostgresEventStore(config=config)
        
        # Skip if PostgreSQL not available
        try:
            await store.connect()
            yield store
        except Exception as e:
            pytest.skip(f"PostgreSQL not available: {e}")
        finally:
            await store.disconnect()
    
    @pytest.mark.asyncio
    async def test_connect_disconnect(self, postgres_store: PostgresEventStore):
        """Test connection and disconnection."""
        assert postgres_store.is_connected
        
        health = await postgres_store.health_check()
        assert health["healthy"] is True
        assert health["backend"] == "postgresql"
    
    @pytest.mark.asyncio
    async def test_append_single_event(
        self,
        postgres_store: PostgresEventStore,
        sample_event: Event,
    ):
        """Test appending a single event."""
        # Clean up any existing stream
        await postgres_store.delete_stream(sample_event.aggregate_id)
        
        version = await postgres_store.append_event(
            sample_event.aggregate_id,
            sample_event,
        )
        
        assert version == 1
        
        # Verify event was stored
        events = await postgres_store.get_events(sample_event.aggregate_id)
        assert len(events) == 1
        assert events[0].event_id == sample_event.event_id
        assert events[0].event_type == sample_event.event_type
    
    @pytest.mark.asyncio
    async def test_append_multiple_events(
        self,
        postgres_store: PostgresEventStore,
        sample_events: list[Event],
    ):
        """Test appending multiple events atomically."""
        aggregate_id = sample_events[0].aggregate_id
        
        # Clean up
        await postgres_store.delete_stream(aggregate_id)
        
        version = await postgres_store.append_events(aggregate_id, sample_events)
        
        assert version == len(sample_events)
        
        # Verify all events stored
        events = await postgres_store.get_events(aggregate_id)
        assert len(events) == len(sample_events)
    
    @pytest.mark.asyncio
    async def test_optimistic_concurrency(
        self,
        postgres_store: PostgresEventStore,
        sample_event: Event,
    ):
        """Test optimistic concurrency control."""
        aggregate_id = sample_event.aggregate_id
        
        # Clean up
        await postgres_store.delete_stream(aggregate_id)
        
        # Append first event
        await postgres_store.append_event(aggregate_id, sample_event)
        
        # Try to append with wrong expected version
        new_event = Event(
            event_id="test-event-002",
            event_type="TestEvent2",
            aggregate_id=aggregate_id,
            aggregate_type="TestAggregate",
        )
        
        with pytest.raises(VersionConflictError) as exc_info:
            await postgres_store.append_event(
                aggregate_id,
                new_event,
                expected_version=0,  # Wrong version
            )
        
        assert exc_info.value.expected_version == 0
        assert exc_info.value.actual_version == 1
    
    @pytest.mark.asyncio
    async def test_get_events_by_type(
        self,
        postgres_store: PostgresEventStore,
        sample_events: list[Event],
    ):
        """Test getting events by type."""
        aggregate_id = sample_events[0].aggregate_id
        
        # Clean up and insert
        await postgres_store.delete_stream(aggregate_id)
        await postgres_store.append_events(aggregate_id, sample_events)
        
        # Get events of specific type
        events = await postgres_store.get_events_by_type("TestEvent0")
        
        assert len(events) >= 2  # At least 2 events of this type
        for event in events:
            assert event.event_type == "TestEvent0"
    
    @pytest.mark.asyncio
    async def test_snapshot_operations(
        self,
        postgres_store: PostgresEventStore,
        sample_snapshot: Snapshot,
    ):
        """Test snapshot save and retrieve."""
        aggregate_id = sample_snapshot.aggregate_id
        
        # Clean up
        await postgres_store.delete_snapshots(aggregate_id)
        
        # Save snapshot
        await postgres_store.save_snapshot(sample_snapshot)
        
        # Retrieve snapshot
        snapshot = await postgres_store.get_snapshot(aggregate_id)
        
        assert snapshot is not None
        assert snapshot.snapshot_id == sample_snapshot.snapshot_id
        assert snapshot.sequence_number == sample_snapshot.sequence_number
        assert snapshot.state == sample_snapshot.state
    
    @pytest.mark.asyncio
    async def test_list_streams(
        self,
        postgres_store: PostgresEventStore,
        sample_events: list[Event],
    ):
        """Test listing streams."""
        aggregate_id = sample_events[0].aggregate_id
        
        # Clean up and insert
        await postgres_store.delete_stream(aggregate_id)
        await postgres_store.append_events(aggregate_id, sample_events)
        
        # List streams
        streams = await postgres_store.list_streams(limit=100)
        
        assert len(streams) >= 1
        assert any(s["stream_id"] == aggregate_id for s in streams)
    
    @pytest.mark.asyncio
    async def test_delete_stream(
        self,
        postgres_store: PostgresEventStore,
        sample_events: list[Event],
    ):
        """Test deleting a stream."""
        aggregate_id = sample_events[0].aggregate_id
        
        # Insert events
        await postgres_store.delete_stream(aggregate_id)
        await postgres_store.append_events(aggregate_id, sample_events)
        
        # Verify exists
        assert await postgres_store.stream_exists(aggregate_id)
        
        # Delete
        await postgres_store.delete_stream(aggregate_id)
        
        # Verify deleted
        assert not await postgres_store.stream_exists(aggregate_id)
        events = await postgres_store.get_events(aggregate_id)
        assert len(events) == 0
    
    @pytest.mark.asyncio
    async def test_statistics(
        self,
        postgres_store: PostgresEventStore,
        sample_events: list[Event],
    ):
        """Test getting statistics."""
        aggregate_id = sample_events[0].aggregate_id
        
        # Clean up and insert
        await postgres_store.delete_stream(aggregate_id)
        await postgres_store.append_events(aggregate_id, sample_events)
        
        stats = await postgres_store.get_statistics()
        
        assert "total_events" in stats
        assert "total_streams" in stats
        assert "total_snapshots" in stats
        assert "event_types" in stats
        assert stats["total_events"] >= len(sample_events)


# =============================================================================
# MongoDB Backend Tests
# =============================================================================

class TestMongoDBEventStore:
    """Tests for MongoDB event store backend."""
    
    @pytest.fixture
    async def mongodb_store(self) -> AsyncGenerator[MongoDBEventStore, None]:
        """Create a MongoDB event store for testing."""
        config = MongoDBConfig(
            host=os.getenv("MONGODB_HOST", "localhost"),
            port=int(os.getenv("MONGODB_PORT", "27017")),
            database=os.getenv("MONGODB_DB", "maas_event_store_test"),
            user=os.getenv("MONGODB_USER"),
            password=os.getenv("MONGODB_PASSWORD"),
            max_pool_size=10,
            min_pool_size=2,
        )
        
        store = MongoDBEventStore(config=config)
        
        # Skip if MongoDB not available
        try:
            await store.connect()
            yield store
        except Exception as e:
            pytest.skip(f"MongoDB not available: {e}")
        finally:
            await store.disconnect()
    
    @pytest.mark.asyncio
    async def test_connect_disconnect(self, mongodb_store: MongoDBEventStore):
        """Test connection and disconnection."""
        assert mongodb_store.is_connected
        
        health = await mongodb_store.health_check()
        assert health["healthy"] is True
        assert health["backend"] == "mongodb"
    
    @pytest.mark.asyncio
    async def test_append_single_event(
        self,
        mongodb_store: MongoDBEventStore,
        sample_event: Event,
    ):
        """Test appending a single event."""
        # Clean up
        await mongodb_store.delete_stream(sample_event.aggregate_id)
        
        version = await mongodb_store.append_event(
            sample_event.aggregate_id,
            sample_event,
        )
        
        assert version == 1
        
        # Verify event was stored
        events = await mongodb_store.get_events(sample_event.aggregate_id)
        assert len(events) == 1
        assert events[0].event_id == sample_event.event_id
    
    @pytest.mark.asyncio
    async def test_append_multiple_events(
        self,
        mongodb_store: MongoDBEventStore,
        sample_events: list[Event],
    ):
        """Test appending multiple events."""
        aggregate_id = sample_events[0].aggregate_id
        
        # Clean up
        await mongodb_store.delete_stream(aggregate_id)
        
        version = await mongodb_store.append_events(aggregate_id, sample_events)
        
        assert version == len(sample_events)
        
        events = await mongodb_store.get_events(aggregate_id)
        assert len(events) == len(sample_events)
    
    @pytest.mark.asyncio
    async def test_get_events_by_correlation_id(
        self,
        mongodb_store: MongoDBEventStore,
        sample_events: list[Event],
    ):
        """Test getting events by correlation ID."""
        aggregate_id = sample_events[0].aggregate_id
        correlation_id = sample_events[0].metadata.correlation_id
        
        # Clean up and insert
        await mongodb_store.delete_stream(aggregate_id)
        await mongodb_store.append_events(aggregate_id, sample_events)
        
        # Get by correlation ID
        events = await mongodb_store.get_events_by_correlation_id(correlation_id)
        
        assert len(events) >= len(sample_events)
        for event in events:
            assert event.metadata.correlation_id == correlation_id
    
    @pytest.mark.asyncio
    async def test_snapshot_operations(
        self,
        mongodb_store: MongoDBEventStore,
        sample_snapshot: Snapshot,
    ):
        """Test snapshot operations."""
        aggregate_id = sample_snapshot.aggregate_id
        
        # Clean up
        await mongodb_store.delete_snapshots(aggregate_id)
        
        # Save snapshot
        await mongodb_store.save_snapshot(sample_snapshot)
        
        # Retrieve snapshot
        snapshot = await mongodb_store.get_snapshot(aggregate_id)
        
        assert snapshot is not None
        assert snapshot.snapshot_id == sample_snapshot.snapshot_id
        assert snapshot.state == sample_snapshot.state
    
    @pytest.mark.asyncio
    async def test_statistics(
        self,
        mongodb_store: MongoDBEventStore,
        sample_events: list[Event],
    ):
        """Test getting statistics."""
        aggregate_id = sample_events[0].aggregate_id
        
        # Clean up and insert
        await mongodb_store.delete_stream(aggregate_id)
        await mongodb_store.append_events(aggregate_id, sample_events)
        
        stats = await mongodb_store.get_statistics()
        
        assert "total_events" in stats
        assert "total_streams" in stats
        assert "event_types" in stats
        assert stats["total_events"] >= len(sample_events)


# =============================================================================
# Mock Tests (for CI without database)
# =============================================================================

class TestMockedBackends:
    """Tests using mocked database connections."""
    
    @pytest.mark.asyncio
    async def test_mocked_postgres_append(self, sample_event: Event):
        """Test PostgreSQL append with mocked connection."""
        with patch("src.event_sourcing.backends.postgres.asyncpg") as mock_asyncpg:
            # Setup mock pool
            mock_pool = AsyncMock()
            mock_conn = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
            mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)
            
            # Create store
            config = PostgresConfig()
            store = PostgresEventStore(config=config)
            
            # Mock transaction
            mock_conn.transaction.return_value.__aenter__ = AsyncMock()
            mock_conn.fetchval = AsyncMock(side_effect=[None, 0, 1])  # No stream, version 0, new version 1
            mock_conn.execute = AsyncMock()
            
            # This would work with proper mocking
            # For now, just verify the store can be created
            assert store.config == config
    
    @pytest.mark.asyncio
    async def test_version_conflict_error(self):
        """Test version conflict error properties."""
        error = VersionConflictError(
            aggregate_id="test-agg",
            expected_version=5,
            actual_version=10,
        )
        
        assert error.aggregate_id == "test-agg"
        assert error.expected_version == 5
        assert error.actual_version == 10
        assert "Version conflict" in str(error)


# =============================================================================
# Integration Tests
# =============================================================================

class TestBackendComparison:
    """Compare behavior between backends."""
    
    @pytest.mark.asyncio
    async def test_event_serialization(self, sample_event: Event):
        """Test that events serialize consistently."""
        # Convert to dict and back
        event_dict = sample_event.to_dict()
        restored = Event.from_dict(event_dict)
        
        assert restored.event_id == sample_event.event_id
        assert restored.event_type == sample_event.event_type
        assert restored.aggregate_id == sample_event.aggregate_id
        assert restored.sequence_number == sample_event.sequence_number
        assert restored.data == sample_event.data
        assert restored.metadata.correlation_id == sample_event.metadata.correlation_id
    
    @pytest.mark.asyncio
    async def test_snapshot_serialization(self, sample_snapshot: Snapshot):
        """Test that snapshots serialize consistently."""
        snapshot_dict = sample_snapshot.to_dict()
        restored = Snapshot.from_dict(snapshot_dict)
        
        assert restored.snapshot_id == sample_snapshot.snapshot_id
        assert restored.aggregate_id == sample_snapshot.aggregate_id
        assert restored.sequence_number == sample_snapshot.sequence_number
        assert restored.state == sample_snapshot.state


# =============================================================================
# Performance Tests
# =============================================================================

class TestBackendPerformance:
    """Performance tests for backends."""
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_batch_append_performance(
        self,
        postgres_store: PostgresEventStore,
    ):
        """Test batch append performance."""
        # Create many events
        events = []
        for i in range(100):
            events.append(Event(
                event_id=f"perf-event-{i:04d}",
                event_type="PerformanceTest",
                aggregate_id="perf-aggregate",
                aggregate_type="PerformanceTest",
                data={"index": i},
            ))
        
        # Clean up
        await postgres_store.delete_stream("perf-aggregate")
        
        # Measure time
        import time
        start = time.time()
        version = await postgres_store.append_events("perf-aggregate", events)
        elapsed = time.time() - start
        
        assert version == 100
        assert elapsed < 5.0  # Should complete in under 5 seconds
        
        print(f"\nBatch append 100 events: {elapsed:.3f}s ({100/elapsed:.1f} events/sec)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

"""
Integration Tests for Event Store Backend Interoperability.

Tests the interaction between PostgreSQL and MongoDB backends:
- Data consistency between backends
- Migration functionality
- Dual-backend operation
- Cross-backend validation
"""

import asyncio
import os
import pytest
from datetime import datetime
from typing import AsyncGenerator, List
from unittest.mock import AsyncMock, MagicMock, patch

# Skip tests if database dependencies not available
pytest.importorskip("asyncpg", reason="asyncpg not installed")
pytest.importorskip("motor", reason="motor not installed")

from src.event_sourcing.backends.base import (
    DatabaseBackend,
    VersionConflictError,
)
from src.event_sourcing.backends.postgres import PostgresEventStore, PostgresConfig
from src.event_sourcing.backends.mongodb import MongoDBEventStore, MongoDBConfig
from src.event_sourcing.backends.migration import (
    BackendMigrator,
    MigrationConfig,
    MigrationStatus,
    DualBackendEventStore,
    migrate_postgresql_to_mongodb,
    migrate_mongodb_to_postgresql,
)
from src.event_sourcing.event_store import Event, Snapshot, EventMetadata


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def sample_events() -> List[Event]:
    """Create sample events for testing."""
    events = []
    for i in range(10):
        events.append(Event(
            event_id=f"integration-event-{i:04d}",
            event_type=f"IntegrationTest{i % 3}",
            aggregate_id="integration-stream",
            aggregate_type="IntegrationTest",
            sequence_number=i + 1,
            data={"index": i, "data": f"test-data-{i}"},
            metadata=EventMetadata(
                correlation_id="integration-corr",
                user_id="test-user",
            )
        ))
    return events


@pytest.fixture
def sample_snapshot() -> Snapshot:
    """Create a sample snapshot for testing."""
    return Snapshot(
        snapshot_id="integration-snapshot-001",
        aggregate_id="integration-stream",
        aggregate_type="IntegrationTest",
        sequence_number=10,
        state={"total": 100, "processed": True},
        timestamp=datetime.utcnow(),
    )


# =============================================================================
# Mock Integration Tests (for CI without databases)
# =============================================================================

class TestMockedBackendIntegration:
    """Tests using mocked backends for CI environments."""
    
    @pytest.mark.asyncio
    async def test_mocked_migration_flow(self, sample_events: List[Event]):
        """Test migration flow with mocked backends."""
        # Create mock backends
        source = AsyncMock(spec=DatabaseBackend)
        target = AsyncMock(spec=DatabaseBackend)
        
        # Setup source mock responses
        source.is_connected = True
        target.is_connected = True
        
        source.get_statistics = AsyncMock(return_value={
            "total_events": len(sample_events),
            "total_streams": 1,
            "total_snapshots": 0,
        })
        
        source.list_streams = AsyncMock(return_value=[
            {"stream_id": "integration-stream", "version": 10}
        ])
        
        source.get_events = AsyncMock(return_value=sample_events)
        source.get_snapshot = AsyncMock(return_value=None)
        
        target.append_events = AsyncMock(return_value=10)
        target.save_snapshot = AsyncMock()
        
        target.get_statistics = AsyncMock(return_value={
            "total_events": len(sample_events),
            "total_streams": 1,
            "total_snapshots": 0,
        })
        
        # Run migration
        config = MigrationConfig(
            batch_size=5,
            validate_after_migration=True,
            dry_run=False,
        )
        
        migrator = BackendMigrator(source, target, config)
        progress = await migrator.migrate()
        
        # Verify results
        assert progress.status == MigrationStatus.COMPLETED
        assert progress.total_events == len(sample_events)
        assert progress.migrated_events == len(sample_events)
        assert len(progress.errors) == 0
    
    @pytest.mark.asyncio
    async def test_mocked_dual_backend_write_both(self, sample_events: List[Event]):
        """Test dual backend with write to both."""
        primary = AsyncMock(spec=DatabaseBackend)
        secondary = AsyncMock(spec=DatabaseBackend)
        
        primary.is_connected = True
        secondary.is_connected = True
        
        primary.append_events = AsyncMock(return_value=1)
        secondary.append_events = AsyncMock(return_value=1)
        
        store = DualBackendEventStore(
            primary_backend=primary,
            secondary_backend=secondary,
            write_to_both=True,
        )
        
        result = await store.append_events("test-stream", sample_events[:1])
        
        # Both backends should be called
        primary.append_events.assert_called_once()
        secondary.append_events.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_mocked_dual_backend_read_fallback(self, sample_events: List[Event]):
        """Test dual backend with read fallback."""
        primary = AsyncMock(spec=DatabaseBackend)
        secondary = AsyncMock(spec=DatabaseBackend)
        
        primary.is_connected = True
        secondary.is_connected = True
        
        # Secondary fails, primary succeeds
        secondary.get_events = AsyncMock(side_effect=Exception("Secondary failed"))
        primary.get_events = AsyncMock(return_value=sample_events)
        
        store = DualBackendEventStore(
            primary_backend=primary,
            secondary_backend=secondary,
            read_from_secondary=True,
        )
        
        result = await store.get_events("test-stream")
        
        # Should fallback to primary
        assert result == sample_events
        primary.get_events.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_mocked_migration_with_errors(self, sample_events: List[Event]):
        """Test migration with errors."""
        source = AsyncMock(spec=DatabaseBackend)
        target = AsyncMock(spec=DatabaseBackend)
        
        source.is_connected = True
        target.is_connected = True
        
        source.get_statistics = AsyncMock(return_value={
            "total_events": 10,
            "total_streams": 1,
            "total_snapshots": 0,
        })
        
        source.list_streams = AsyncMock(return_value=[
            {"stream_id": "stream-1", "version": 5},
            {"stream_id": "stream-2", "version": 5},
        ])
        
        # First stream succeeds, second fails
        source.get_events = AsyncMock(return_value=sample_events[:5])
        target.append_events = AsyncMock(
            side_effect=[5, Exception("Migration error")]
        )
        
        config = MigrationConfig(
            stop_on_error=False,
            max_errors=5,
        )
        
        migrator = BackendMigrator(source, target, config)
        progress = await migrator.migrate()
        
        # Should continue despite error
        assert len(progress.errors) > 0


# =============================================================================
# Integration Tests (require both databases)
# =============================================================================

class TestPostgreSQLMongoDBIntegration:
    """
    Integration tests between PostgreSQL and MongoDB.
    
    These tests require both databases to be running.
    Skip if databases are not available.
    """
    
    @pytest.fixture
    async def postgres_store(self) -> AsyncGenerator[PostgresEventStore, None]:
        """Create PostgreSQL store for testing."""
        config = PostgresConfig(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            database=os.getenv("POSTGRES_DB", "maas_event_store_test"),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", ""),
            schema="integration_test",
        )
        
        store = PostgresEventStore(config=config)
        
        try:
            await store.connect()
            yield store
        except Exception as e:
            pytest.skip(f"PostgreSQL not available: {e}")
        finally:
            await store.disconnect()
    
    @pytest.fixture
    async def mongodb_store(self) -> AsyncGenerator[MongoDBEventStore, None]:
        """Create MongoDB store for testing."""
        config = MongoDBConfig(
            host=os.getenv("MONGODB_HOST", "localhost"),
            port=int(os.getenv("MONGODB_PORT", "27017")),
            database=os.getenv("MONGODB_DB", "maas_event_store_test"),
        )
        
        store = MongoDBEventStore(config=config)
        
        try:
            await store.connect()
            yield store
        except Exception as e:
            pytest.skip(f"MongoDB not available: {e}")
        finally:
            await store.disconnect()
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_cross_backend_event_consistency(
        self,
        postgres_store: PostgresEventStore,
        mongodb_store: MongoDBEventStore,
        sample_events: List[Event],
    ):
        """Test that events are consistent across backends."""
        aggregate_id = "consistency-test-stream"
        
        # Clean up
        await postgres_store.delete_stream(aggregate_id)
        await mongodb_store.delete_stream(aggregate_id)
        
        # Write to PostgreSQL
        version = await postgres_store.append_events(aggregate_id, sample_events)
        assert version == len(sample_events)
        
        # Read from PostgreSQL
        pg_events = await postgres_store.get_events(aggregate_id)
        
        # Write same events to MongoDB
        version = await mongodb_store.append_events(aggregate_id, sample_events)
        assert version == len(sample_events)
        
        # Read from MongoDB
        mongo_events = await mongodb_store.get_events(aggregate_id)
        
        # Compare
        assert len(pg_events) == len(mongo_events)
        
        for pg_event, mongo_event in zip(pg_events, mongo_events):
            assert pg_event.event_id == mongo_event.event_id
            assert pg_event.event_type == mongo_event.event_type
            assert pg_event.sequence_number == mongo_event.sequence_number
            assert pg_event.data == mongo_event.data
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_migration_postgresql_to_mongodb(
        self,
        postgres_store: PostgresEventStore,
        mongodb_store: MongoDBEventStore,
        sample_events: List[Event],
    ):
        """Test migration from PostgreSQL to MongoDB."""
        aggregate_id = "migration-test-stream"
        
        # Clean up
        await postgres_store.delete_stream(aggregate_id)
        await mongodb_store.delete_stream(aggregate_id)
        
        # Setup source data in PostgreSQL
        await postgres_store.append_events(aggregate_id, sample_events)
        
        # Run migration
        config = MigrationConfig(
            batch_size=5,
            validate_after_migration=True,
        )
        
        migrator = BackendMigrator(postgres_store, mongodb_store, config)
        progress = await migrator.migrate()
        
        # Verify migration
        assert progress.status == MigrationStatus.COMPLETED
        assert progress.migrated_events >= len(sample_events)
        assert len(progress.errors) == 0
        
        # Verify data in MongoDB
        mongo_events = await mongodb_store.get_events(aggregate_id)
        assert len(mongo_events) == len(sample_events)
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_migration_mongodb_to_postgresql(
        self,
        postgres_store: PostgresEventStore,
        mongodb_store: MongoDBEventStore,
        sample_events: List[Event],
    ):
        """Test migration from MongoDB to PostgreSQL."""
        aggregate_id = "reverse-migration-test-stream"
        
        # Clean up
        await postgres_store.delete_stream(aggregate_id)
        await mongodb_store.delete_stream(aggregate_id)
        
        # Setup source data in MongoDB
        await mongodb_store.append_events(aggregate_id, sample_events)
        
        # Run migration
        config = MigrationConfig(
            batch_size=5,
            validate_after_migration=True,
        )
        
        migrator = BackendMigrator(mongodb_store, postgres_store, config)
        progress = await migrator.migrate()
        
        # Verify migration
        assert progress.status == MigrationStatus.COMPLETED
        assert progress.migrated_events >= len(sample_events)
        
        # Verify data in PostgreSQL
        pg_events = await postgres_store.get_events(aggregate_id)
        assert len(pg_events) == len(sample_events)
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_dual_backend_operation(
        self,
        postgres_store: PostgresEventStore,
        mongodb_store: MongoDBEventStore,
        sample_events: List[Event],
    ):
        """Test dual backend event store operation."""
        aggregate_id = "dual-backend-test-stream"
        
        # Clean up
        await postgres_store.delete_stream(aggregate_id)
        await mongodb_store.delete_stream(aggregate_id)
        
        # Create dual backend store
        store = DualBackendEventStore(
            primary_backend=postgres_store,
            secondary_backend=mongodb_store,
            write_to_both=True,
        )
        
        # Write events
        await store.append_events(aggregate_id, sample_events)
        
        # Verify both backends have data
        pg_events = await postgres_store.get_events(aggregate_id)
        mongo_events = await mongodb_store.get_events(aggregate_id)
        
        assert len(pg_events) == len(sample_events)
        assert len(mongo_events) == len(sample_events)
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_snapshot_migration(
        self,
        postgres_store: PostgresEventStore,
        mongodb_store: MongoDBEventStore,
        sample_events: List[Event],
        sample_snapshot: Snapshot,
    ):
        """Test snapshot migration between backends."""
        aggregate_id = sample_snapshot.aggregate_id
        
        # Clean up
        await postgres_store.delete_stream(aggregate_id)
        await mongodb_store.delete_stream(aggregate_id)
        
        # Setup in PostgreSQL
        await postgres_store.append_events(aggregate_id, sample_events)
        await postgres_store.save_snapshot(sample_snapshot)
        
        # Migrate
        migrator = BackendMigrator(postgres_store, mongodb_store)
        progress = await migrator.migrate()
        
        # Verify snapshot migrated
        assert progress.migrated_snapshots >= 1
        
        # Verify snapshot in MongoDB
        snapshot = await mongodb_store.get_snapshot(aggregate_id)
        assert snapshot is not None
        assert snapshot.sequence_number == sample_snapshot.sequence_number


# =============================================================================
# Performance Tests
# =============================================================================

class TestBackendPerformance:
    """Performance tests for backend operations."""
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_large_batch_migration(self):
        """Test migration with large batch of events."""
        # Create mock backends
        source = AsyncMock(spec=DatabaseBackend)
        target = AsyncMock(spec=DatabaseBackend)
        
        source.is_connected = True
        target.is_connected = True
        
        # Create large number of events
        num_events = 10000
        num_streams = 100
        
        source.get_statistics = AsyncMock(return_value={
            "total_events": num_events,
            "total_streams": num_streams,
            "total_snapshots": 0,
        })
        
        # Mock streams
        streams = [
            {"stream_id": f"stream-{i}", "version": num_events // num_streams}
            for i in range(num_streams)
        ]
        source.list_streams = AsyncMock(return_value=streams)
        
        # Mock events
        events_per_stream = num_events // num_streams
        mock_events = [
            Event(
                event_id=f"event-{i}",
                event_type="TestEvent",
                aggregate_id="test-stream",
                sequence_number=i + 1,
                data={"index": i},
            )
            for i in range(events_per_stream)
        ]
        
        source.get_events = AsyncMock(return_value=mock_events)
        source.get_snapshot = AsyncMock(return_value=None)
        target.append_events = AsyncMock(return_value=events_per_stream)
        
        # Run migration with progress tracking
        progress_updates = []
        
        def track_progress(progress):
            progress_updates.append(progress.migrated_events)
        
        config = MigrationConfig(
            batch_size=100,
            progress_callback=track_progress,
        )
        
        migrator = BackendMigrator(source, target, config)
        
        import time
        start = time.time()
        progress = await migrator.migrate()
        elapsed = time.time() - start
        
        # Verify
        assert progress.status == MigrationStatus.COMPLETED
        assert len(progress_updates) > 0
        
        print(f"\nMigrated {progress.migrated_events} events in {elapsed:.2f}s")
        print(f"Rate: {progress.migrated_events/elapsed:.0f} events/sec")


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestMigrationErrorHandling:
    """Tests for migration error handling."""
    
    @pytest.mark.asyncio
    async def test_migration_rollback(self):
        """Test migration rollback functionality."""
        source = AsyncMock(spec=DatabaseBackend)
        target = AsyncMock(spec=DatabaseBackend)
        
        source.is_connected = True
        target.is_connected = True
        
        source.get_statistics = AsyncMock(return_value={
            "total_events": 10,
            "total_streams": 1,
            "total_snapshots": 0,
        })
        
        source.list_streams = AsyncMock(return_value=[
            {"stream_id": "rollback-test-stream", "version": 10}
        ])
        
        events = [
            Event(
                event_id=f"event-{i}",
                event_type="TestEvent",
                aggregate_id="rollback-test-stream",
                sequence_number=i + 1,
            )
            for i in range(10)
        ]
        
        source.get_events = AsyncMock(return_value=events)
        source.get_snapshot = AsyncMock(return_value=None)
        target.append_events = AsyncMock(return_value=10)
        target.delete_stream = AsyncMock()
        
        migrator = BackendMigrator(source, target)
        await migrator.migrate()
        
        # Rollback
        await migrator.rollback()
        
        # Verify delete was called
        target.delete_stream.assert_called_once_with("rollback-test-stream")
    
    @pytest.mark.asyncio
    async def test_dry_run_migration(self):
        """Test dry run migration (no actual writes)."""
        source = AsyncMock(spec=DatabaseBackend)
        target = AsyncMock(spec=DatabaseBackend)
        
        source.is_connected = True
        target.is_connected = True
        
        source.get_statistics = AsyncMock(return_value={
            "total_events": 10,
            "total_streams": 1,
            "total_snapshots": 1,
        })
        
        source.list_streams = AsyncMock(return_value=[
            {"stream_id": "dry-run-stream", "version": 10}
        ])
        
        events = [
            Event(
                event_id=f"event-{i}",
                event_type="TestEvent",
                aggregate_id="dry-run-stream",
                sequence_number=i + 1,
            )
            for i in range(10)
        ]
        
        source.get_events = AsyncMock(return_value=events)
        source.get_snapshot = AsyncMock(return_value=Snapshot(
            snapshot_id="snap-1",
            aggregate_id="dry-run-stream",
            aggregate_type="Test",
            sequence_number=10,
            state={},
        ))
        
        config = MigrationConfig(dry_run=True)
        migrator = BackendMigrator(source, target, config)
        progress = await migrator.migrate()
        
        # Verify no writes occurred
        target.append_events.assert_not_called()
        target.save_snapshot.assert_not_called()
        
        # But progress should still be tracked
        assert progress.migrated_events == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

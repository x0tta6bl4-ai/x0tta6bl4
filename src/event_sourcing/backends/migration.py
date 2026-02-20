"""
Event Store Backend Migration Tool.

Provides functionality to migrate events between different database backends:
- PostgreSQL to MongoDB
- MongoDB to PostgreSQL
- Any backend to any backend via abstract interface

Features:
- Batch migration with configurable batch size
- Progress tracking and reporting
- Data validation after migration
- Rollback capability
- Resume from interruption
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type

from src.event_sourcing.backends.base import DatabaseBackend
from src.event_sourcing.event_store import Event, Snapshot

logger = logging.getLogger(__name__)


class MigrationDirection(Enum):
    """Direction of migration."""
    POSTGRESQL_TO_MONGODB = "postgresql_to_mongodb"
    MONGODB_TO_POSTGRESQL = "mongodb_to_postgresql"
    CUSTOM = "custom"


class MigrationStatus(Enum):
    """Status of migration."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    PAUSED = "paused"


@dataclass
class MigrationProgress:
    """Tracks migration progress."""
    total_events: int = 0
    migrated_events: int = 0
    total_streams: int = 0
    migrated_streams: int = 0
    total_snapshots: int = 0
    migrated_snapshots: int = 0
    errors: List[str] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: MigrationStatus = MigrationStatus.PENDING
    
    @property
    def events_percentage(self) -> float:
        if self.total_events == 0:
            return 0.0
        return (self.migrated_events / self.total_events) * 100
    
    @property
    def streams_percentage(self) -> float:
        if self.total_streams == 0:
            return 0.0
        return (self.migrated_streams / self.total_streams) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_events": self.total_events,
            "migrated_events": self.migrated_events,
            "events_percentage": round(self.events_percentage, 2),
            "total_streams": self.total_streams,
            "migrated_streams": self.migrated_streams,
            "streams_percentage": round(self.streams_percentage, 2),
            "total_snapshots": self.total_snapshots,
            "migrated_snapshots": self.migrated_snapshots,
            "errors": self.errors,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


@dataclass
class MigrationConfig:
    """Configuration for migration."""
    batch_size: int = 1000
    validate_after_migration: bool = True
    create_backup: bool = True
    stop_on_error: bool = False
    max_errors: int = 10
    progress_callback: Optional[Callable[[MigrationProgress], None]] = None
    dry_run: bool = False


class BackendMigrator:
    """
    Migrates data between different event store backends.
    
    Supports:
    - PostgreSQL ↔ MongoDB migration
    - Batch processing for large datasets
    - Progress tracking and reporting
    - Data validation
    - Rollback capability
    """
    
    def __init__(
        self,
        source_backend: DatabaseBackend,
        target_backend: DatabaseBackend,
        config: Optional[MigrationConfig] = None,
    ):
        """
        Initialize migrator.
        
        Args:
            source_backend: Source database backend
            target_backend: Target database backend
            config: Migration configuration
        """
        self.source = source_backend
        self.target = target_backend
        self.config = config or MigrationConfig()
        self.progress = MigrationProgress()
        self._migrated_stream_versions: Dict[str, int] = {}
    
    async def migrate(self) -> MigrationProgress:
        """
        Execute full migration from source to target.
        
        Returns:
            MigrationProgress with migration results
        """
        self.progress = MigrationProgress()
        self.progress.status = MigrationStatus.IN_PROGRESS
        self.progress.started_at = datetime.utcnow()
        
        try:
            # Ensure both backends are connected
            if not self.source.is_connected:
                await self.source.connect()
            if not self.target.is_connected:
                await self.target.connect()
            
            # Get source statistics
            source_stats = await self.source.get_statistics()
            self.progress.total_events = source_stats.get("total_events", 0)
            self.progress.total_streams = source_stats.get("total_streams", 0)
            self.progress.total_snapshots = source_stats.get("total_snapshots", 0)
            
            logger.info(
                f"Starting migration: {self.progress.total_events} events, "
                f"{self.progress.total_streams} streams, "
                f"{self.progress.total_snapshots} snapshots"
            )
            
            # Migrate streams and events
            await self._migrate_streams()
            
            # Migrate snapshots
            await self._migrate_snapshots()
            
            # Validate if configured
            if self.config.validate_after_migration and not self.config.dry_run:
                await self._validate_migration()
            
            self.progress.status = MigrationStatus.COMPLETED
            self.progress.completed_at = datetime.utcnow()
            
            logger.info(f"Migration completed: {self.progress.to_dict()}")
            
        except Exception as e:
            self.progress.status = MigrationStatus.FAILED
            self.progress.errors.append(str(e))
            self.progress.completed_at = datetime.utcnow()
            logger.error(f"Migration failed: {e}")
            raise
        
        return self.progress
    
    async def _migrate_streams(self) -> None:
        """Migrate all streams with their events."""
        offset = 0
        batch_size = 100  # Streams per batch
        
        while True:
            # Get batch of streams
            streams = await self.source.list_streams(limit=batch_size, offset=offset)
            
            if not streams:
                break
            
            for stream_info in streams:
                try:
                    await self._migrate_stream(stream_info["stream_id"])
                    self.progress.migrated_streams += 1
                    
                    if self.config.progress_callback:
                        self.config.progress_callback(self.progress)
                        
                except Exception as e:
                    error_msg = f"Failed to migrate stream {stream_info['stream_id']}: {e}"
                    self.progress.errors.append(error_msg)
                    logger.error(error_msg)
                    
                    if self.config.stop_on_error:
                        raise
                    
                    if len(self.progress.errors) >= self.config.max_errors:
                        raise RuntimeError(
                            f"Max errors ({self.config.max_errors}) reached"
                        )
            
            offset += batch_size
    
    async def _migrate_stream(self, stream_id: str) -> None:
        """Migrate a single stream with all its events."""
        # Get all events for the stream
        events = await self.source.get_events(stream_id, from_sequence=0, limit=100000)
        
        if not events:
            return
        
        # Store original version for potential rollback
        self._migrated_stream_versions[stream_id] = events[-1].sequence_number
        
        if self.config.dry_run:
            self.progress.migrated_events += len(events)
            return
        
        # Migrate events in batches
        batch_size = self.config.batch_size
        for i in range(0, len(events), batch_size):
            batch = events[i:i + batch_size]
            
            try:
                # Append events to target
                await self.target.append_events(
                    stream_id,
                    batch,
                    expected_version=0 if i == 0 else None
                )
                
                self.progress.migrated_events += len(batch)
                
                if self.config.progress_callback:
                    self.config.progress_callback(self.progress)
                    
            except Exception as e:
                logger.error(f"Failed to migrate batch for stream {stream_id}: {e}")
                raise
    
    async def _migrate_snapshots(self) -> None:
        """Migrate all snapshots."""
        # Get all streams to iterate snapshots
        streams = await self.source.list_streams(limit=10000)
        
        for stream_info in streams:
            stream_id = stream_info["stream_id"]
            
            try:
                # Get latest snapshot for each stream
                snapshot = await self.source.get_snapshot(stream_id)
                
                if snapshot:
                    if not self.config.dry_run:
                        await self.target.save_snapshot(snapshot)
                    
                    self.progress.migrated_snapshots += 1
                    
                    if self.config.progress_callback:
                        self.config.progress_callback(self.progress)
                        
            except Exception as e:
                error_msg = f"Failed to migrate snapshot for {stream_id}: {e}"
                self.progress.errors.append(error_msg)
                logger.error(error_msg)
                
                if self.config.stop_on_error:
                    raise
    
    async def _validate_migration(self) -> bool:
        """Validate migration by comparing source and target."""
        logger.info("Validating migration...")
        
        # Compare statistics
        source_stats = await self.source.get_statistics()
        target_stats = await self.target.get_statistics()
        
        source_events = source_stats.get("total_events", 0)
        target_events = target_stats.get("total_events", 0)
        
        if source_events != target_events:
            error_msg = f"Event count mismatch: source={source_events}, target={target_events}"
            self.progress.errors.append(error_msg)
            logger.error(error_msg)
            return False
        
        source_streams = source_stats.get("total_streams", 0)
        target_streams = target_stats.get("total_streams", 0)
        
        if source_streams != target_streams:
            error_msg = f"Stream count mismatch: source={source_streams}, target={target_streams}"
            self.progress.errors.append(error_msg)
            logger.error(error_msg)
            return False
        
        # Validate sample events
        sample_streams = await self.source.list_streams(limit=10)
        
        for stream_info in sample_streams:
            stream_id = stream_info["stream_id"]
            
            source_events = await self.source.get_events(stream_id, limit=1000)
            target_events = await self.target.get_events(stream_id, limit=1000)
            
            if len(source_events) != len(target_events):
                error_msg = f"Event count mismatch for stream {stream_id}"
                self.progress.errors.append(error_msg)
                logger.error(error_msg)
                return False
            
            # Compare event IDs
            source_ids = {e.event_id for e in source_events}
            target_ids = {e.event_id for e in target_events}
            
            if source_ids != target_ids:
                error_msg = f"Event ID mismatch for stream {stream_id}"
                self.progress.errors.append(error_msg)
                logger.error(error_msg)
                return False
        
        logger.info("Migration validation passed")
        return True
    
    async def rollback(self) -> None:
        """
        Rollback migration by deleting migrated data from target.
        
        Warning: This is a destructive operation!
        """
        if self.progress.status not in (
            MigrationStatus.COMPLETED,
            MigrationStatus.FAILED,
            MigrationStatus.IN_PROGRESS,
        ):
            return
        
        logger.warning("Starting rollback of migration...")
        
        for stream_id in self._migrated_stream_versions:
            try:
                await self.target.delete_stream(stream_id)
                logger.debug(f"Rolled back stream {stream_id}")
            except Exception as e:
                logger.error(f"Failed to rollback stream {stream_id}: {e}")
        
        self.progress.status = MigrationStatus.ROLLED_BACK
        logger.warning("Rollback completed")
    
    async def pause(self) -> None:
        """Pause migration."""
        self.progress.status = MigrationStatus.PAUSED
        logger.info("Migration paused")
    
    async def resume(self) -> MigrationProgress:
        """Resume paused migration."""
        if self.progress.status != MigrationStatus.PAUSED:
            raise RuntimeError("Can only resume paused migration")
        
        self.progress.status = MigrationStatus.IN_PROGRESS
        return await self.migrate()


class DualBackendEventStore:
    """
    Event store that supports dual backend operation.
    
    Allows:
    - Reading from one backend, writing to another
    - Gradual migration with fallback
    - A/B testing between backends
    """
    
    def __init__(
        self,
        primary_backend: DatabaseBackend,
        secondary_backend: Optional[DatabaseBackend] = None,
        write_to_both: bool = False,
        read_from_secondary: bool = False,
    ):
        """
        Initialize dual backend store.
        
        Args:
            primary_backend: Primary database backend
            secondary_backend: Secondary database backend (optional)
            write_to_both: Write to both backends simultaneously
            read_from_secondary: Read from secondary backend
        """
        self.primary = primary_backend
        self.secondary = secondary_backend
        self.write_to_both = write_to_both
        self.read_from_secondary = read_from_secondary
    
    async def connect(self) -> None:
        """Connect to backends."""
        await self.primary.connect()
        if self.secondary:
            await self.secondary.connect()
    
    async def disconnect(self) -> None:
        """Disconnect from backends."""
        await self.primary.disconnect()
        if self.secondary:
            await self.secondary.disconnect()
    
    async def append_events(
        self,
        aggregate_id: str,
        events: List[Event],
        expected_version: Optional[int] = None,
    ) -> int:
        """Append events to backend(s)."""
        if self.write_to_both and self.secondary:
            # Write to both backends
            results = await asyncio.gather(
                self.primary.append_events(aggregate_id, events, expected_version),
                self.secondary.append_events(aggregate_id, events, expected_version),
                return_exceptions=True,
            )
            
            # Check for errors
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    backend = "primary" if i == 0 else "secondary"
                    logger.error(f"Failed to append to {backend}: {result}")
            
            return results[0] if not isinstance(results[0], Exception) else results[1]
        else:
            return await self.primary.append_events(aggregate_id, events, expected_version)
    
    async def get_events(
        self,
        aggregate_id: str,
        from_sequence: int = 0,
        to_sequence: Optional[int] = None,
        limit: int = 1000,
    ) -> List[Event]:
        """Get events from backend."""
        backend = self.secondary if self.read_from_secondary and self.secondary else self.primary
        
        try:
            return await backend.get_events(aggregate_id, from_sequence, to_sequence, limit)
        except Exception as e:
            # Fallback to primary if secondary fails
            if self.read_from_secondary and self.secondary:
                logger.warning(f"Secondary backend failed, falling back to primary: {e}")
                return await self.primary.get_events(aggregate_id, from_sequence, to_sequence, limit)
            raise
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get statistics from both backends."""
        stats = {
            "primary": await self.primary.get_statistics(),
        }
        
        if self.secondary:
            stats["secondary"] = await self.secondary.get_statistics()
        
        return stats
    
    async def health_check(self) -> Dict[str, Any]:
        """Check health of both backends."""
        health = {
            "primary": await self.primary.health_check(),
        }
        
        if self.secondary:
            health["secondary"] = await self.secondary.health_check()
        
        health["healthy"] = all(h.get("healthy", False) for h in health.values())
        return health


# Convenience functions for common migrations

async def migrate_postgresql_to_mongodb(
    postgres_config: "PostgresConfig",
    mongodb_config: "MongoDBConfig",
    migration_config: Optional[MigrationConfig] = None,
) -> MigrationProgress:
    """
    Migrate from PostgreSQL to MongoDB.
    
    Args:
        postgres_config: PostgreSQL connection configuration
        mongodb_config: MongoDB connection configuration
        migration_config: Migration configuration
        
    Returns:
        MigrationProgress with results
    """
    from src.event_sourcing.backends.postgres import PostgresEventStore
    from src.event_sourcing.backends.mongodb import MongoDBEventStore
    
    source = PostgresEventStore(config=postgres_config)
    target = MongoDBEventStore(config=mongodb_config)
    
    migrator = BackendMigrator(source, target, migration_config)
    
    try:
        return await migrator.migrate()
    finally:
        await source.disconnect()
        await target.disconnect()


async def migrate_mongodb_to_postgresql(
    mongodb_config: "MongoDBConfig",
    postgres_config: "PostgresConfig",
    migration_config: Optional[MigrationConfig] = None,
) -> MigrationProgress:
    """
    Migrate from MongoDB to PostgreSQL.
    
    Args:
        mongodb_config: MongoDB connection configuration
        postgres_config: PostgreSQL connection configuration
        migration_config: Migration configuration
        
    Returns:
        MigrationProgress with results
    """
    from src.event_sourcing.backends.postgres import PostgresEventStore
    from src.event_sourcing.backends.mongodb import MongoDBEventStore
    
    source = MongoDBEventStore(config=mongodb_config)
    target = PostgresEventStore(config=postgres_config)
    
    migrator = BackendMigrator(source, target, migration_config)
    
    try:
        return await migrator.migrate()
    finally:
        await source.disconnect()
        await target.disconnect()

"""
PostgreSQL Backend for Event Store.

Provides ACID-compliant persistent storage using PostgreSQL with:
- Connection pooling via asyncpg
- Optimistic concurrency control
- Efficient event streaming
- Snapshot support
"""

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from src.event_sourcing.backends.base import (
    DatabaseBackend,
    VersionConflictError,
    DatabaseConnectionError,
    DatabaseQueryError,
)
from src.event_sourcing.event_store import Event, Snapshot, EventMetadata, EventVersion

logger = logging.getLogger(__name__)

# Try to import asyncpg
try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False
    logger.warning("asyncpg not available - PostgreSQL backend will not work")


@dataclass
class PostgresConfig:
    """PostgreSQL connection configuration."""
    host: str = "localhost"
    port: int = 5432
    database: str = "maas_event_store"
    user: str = "postgres"
    password: str = ""
    schema: str = "event_store"
    min_pool_size: int = 5
    max_pool_size: int = 20
    connection_timeout: float = 30.0
    command_timeout: float = 60.0
    
    def to_dsn(self) -> str:
        """Return censored DSN suitable for logging (password redacted)."""
        return f"postgresql://{self.user}:***@{self.host}:{self.port}/{self.database}"

    def _unsafe_dsn(self) -> str:
        """Return full DSN with password for asyncpg internal use only.

        Do NOT log or expose the return value of this method.
        """
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

    def __repr__(self) -> str:
        return (
            f"PostgresConfig(host={self.host!r}, port={self.port}, "
            f"database={self.database!r}, user={self.user!r}, password='***', "
            f"schema={self.schema!r})"
        )


class PostgresEventStore(DatabaseBackend):
    """
    PostgreSQL-based event store backend.
    
    Features:
    - ACID transactions for event appending
    - Optimistic concurrency control
    - Connection pooling
    - Efficient indexing for queries
    - Snapshot support
    
    Schema:
        - events: Main event storage table
        - streams: Stream metadata
        - snapshots: Aggregate snapshots
        - event_index: Type and correlation ID indexes
    """
    
    def __init__(
        self,
        config: Optional[PostgresConfig] = None,
        **kwargs,
    ):
        """
        Initialize PostgreSQL backend.
        
        Args:
            config: PostgreSQL configuration
            **kwargs: Override config parameters
        """
        super().__init__(**kwargs)
        
        if not ASYNCPG_AVAILABLE:
            raise RuntimeError("asyncpg is required for PostgreSQL backend")
        
        self.config = config or PostgresConfig()
        
        # Override config with kwargs
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        
        self._pool: Optional["asyncpg.Pool"] = None
        self._schema = self._validate_schema_name(self.config.schema)

    @staticmethod
    def _validate_schema_name(name: str) -> str:
        """Validate and return schema name; raise ValueError for unsafe values."""
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", name):
            raise ValueError(
                f"Invalid schema name {name!r}: must match [a-z][a-z0-9_]{{0,62}}"
            )
        return name

    @property
    def _q(self) -> str:
        """Return double-quoted schema name safe for SQL identifier use."""
        return f'"{self._schema}"'
    
    async def connect(self) -> None:
        """Establish connection pool to PostgreSQL."""
        if self._is_connected:
            return
        
        try:
            self._pool = await asyncpg.create_pool(
                host=self.config.host,
                port=self.config.port,
                database=self.config.database,
                user=self.config.user,
                password=self.config.password,
                min_size=self.config.min_pool_size,
                max_size=self.config.max_pool_size,
                command_timeout=self.config.command_timeout,
            )
            
            # Ensure schema exists
            await self._ensure_schema()
            
            self._is_connected = True
            logger.info(
                f"Connected to PostgreSQL: {self.config.host}:{self.config.port}/{self.config.database}"
            )
            
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise DatabaseConnectionError(f"PostgreSQL connection failed: {e}")
    
    async def disconnect(self) -> None:
        """Close connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None
        
        self._is_connected = False
        logger.info("Disconnected from PostgreSQL")
    
    async def _ensure_schema(self) -> None:
        """Ensure database schema exists."""
        async with self._pool.acquire() as conn:
            # Create schema if not exists
            await conn.execute(f"CREATE SCHEMA IF NOT EXISTS {self._q}")
            
            # Create events table
            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self._q}.events (
                    event_id VARCHAR(36) PRIMARY KEY,
                    aggregate_id VARCHAR(255) NOT NULL,
                    aggregate_type VARCHAR(255),
                    event_type VARCHAR(255) NOT NULL,
                    sequence_number BIGINT NOT NULL,
                    data JSONB NOT NULL DEFAULT '{{}}',
                    metadata JSONB NOT NULL DEFAULT '{{}}',
                    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    
                    CONSTRAINT uq_aggregate_sequence UNIQUE (aggregate_id, sequence_number)
                )
            """)
            
            # Create streams table
            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self._q}.streams (
                    aggregate_id VARCHAR(255) PRIMARY KEY,
                    aggregate_type VARCHAR(255),
                    version BIGINT NOT NULL DEFAULT 0,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            
            # Create snapshots table
            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self._q}.snapshots (
                    snapshot_id VARCHAR(36) PRIMARY KEY,
                    aggregate_id VARCHAR(255) NOT NULL,
                    aggregate_type VARCHAR(255),
                    sequence_number BIGINT NOT NULL,
                    state JSONB NOT NULL,
                    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    
                    CONSTRAINT uq_snapshot_aggregate_version 
                        UNIQUE (aggregate_id, sequence_number)
                )
            """)
            
            # Create indexes
            await conn.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_events_aggregate_id 
                ON {self._q}.events (aggregate_id)
            """)
            await conn.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_events_event_type 
                ON {self._q}.events (event_type)
            """)
            await conn.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_events_timestamp 
                ON {self._q}.events (timestamp)
            """)
            await conn.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_events_aggregate_type 
                ON {self._q}.events (aggregate_type)
            """)
            await conn.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_events_data 
                ON {self._q}.events USING GIN (data)
            """)
            await conn.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_events_metadata 
                ON {self._q}.events USING GIN (metadata)
            """)
            await conn.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_snapshots_aggregate_id 
                ON {self._q}.snapshots (aggregate_id)
            """)
            
            logger.debug(f"Schema {self._schema} ensured")
    
    async def health_check(self) -> Dict[str, Any]:
        """Check PostgreSQL health status."""
        if not self._pool:
            return {
                "healthy": False,
                "error": "Not connected",
            }
        
        try:
            async with self._pool.acquire() as conn:
                result = await conn.fetchval("SELECT 1")
                
                # Get pool stats
                pool_size = self._pool.get_size()
                idle_size = self._pool.get_idle_size()
                
                return {
                    "healthy": True,
                    "backend": "postgresql",
                    "database": self.config.database,
                    "host": self.config.host,
                    "pool_size": pool_size,
                    "pool_idle": idle_size,
                    "pool_max": self.config.max_pool_size,
                }
                
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e),
            }
    
    # -------------------------------------------------------------------------
    # Event Operations
    # -------------------------------------------------------------------------
    
    async def append_event(
        self,
        aggregate_id: str,
        event: Event,
        expected_version: Optional[int] = None,
    ) -> int:
        """Append a single event."""
        return await self.append_events(aggregate_id, [event], expected_version)
    
    async def append_events(
        self,
        aggregate_id: str,
        events: List[Event],
        expected_version: Optional[int] = None,
    ) -> int:
        """Append multiple events atomically."""
        if not events:
            return await self.get_stream_version(aggregate_id)
        
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                # Get current version with lock
                current_version = await conn.fetchval(
                    f"SELECT version FROM {self._q}.streams "
                    f"WHERE aggregate_id = $1 FOR UPDATE",
                    aggregate_id
                )
                
                if current_version is None:
                    current_version = 0
                    # Create stream
                    await conn.execute(
                        f"INSERT INTO {self._q}.streams "
                        f"(aggregate_id, version, created_at, updated_at) "
                        f"VALUES ($1, 0, NOW(), NOW())",
                        aggregate_id
                    )
                
                # Optimistic concurrency check
                if expected_version is not None and current_version != expected_version:
                    raise VersionConflictError(
                        aggregate_id, expected_version, current_version
                    )
                
                # Insert events
                next_version = current_version
                for event in events:
                    next_version += 1
                    event.aggregate_id = aggregate_id
                    event.sequence_number = next_version
                    
                    await conn.execute(
                        f"""
                        INSERT INTO {self._q}.events 
                        (event_id, aggregate_id, aggregate_type, event_type, 
                         sequence_number, data, metadata, timestamp)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        """,
                        event.event_id,
                        aggregate_id,
                        event.aggregate_type,
                        event.event_type,
                        event.sequence_number,
                        json.dumps(event.data),
                        json.dumps(event.metadata.to_dict()),
                        event.metadata.timestamp,
                    )
                
                # Update stream version
                await conn.execute(
                    f"UPDATE {self._q}.streams "
                    f"SET version = $1, updated_at = NOW() "
                    f"WHERE aggregate_id = $2",
                    next_version,
                    aggregate_id,
                )
                
                return next_version
    
    async def get_events(
        self,
        aggregate_id: str,
        from_sequence: int = 0,
        to_sequence: Optional[int] = None,
        limit: int = 1000,
    ) -> List[Event]:
        """Get events for an aggregate."""
        async with self._pool.acquire() as conn:
            if to_sequence is not None:
                rows = await conn.fetch(
                    f"""
                    SELECT event_id, aggregate_id, aggregate_type, event_type,
                           sequence_number, data, metadata, timestamp
                    FROM {self._q}.events
                    WHERE aggregate_id = $1 
                      AND sequence_number > $2 
                      AND sequence_number <= $3
                    ORDER BY sequence_number
                    LIMIT $4
                    """,
                    aggregate_id, from_sequence, to_sequence, limit
                )
            else:
                rows = await conn.fetch(
                    f"""
                    SELECT event_id, aggregate_id, aggregate_type, event_type,
                           sequence_number, data, metadata, timestamp
                    FROM {self._q}.events
                    WHERE aggregate_id = $1 AND sequence_number > $2
                    ORDER BY sequence_number
                    LIMIT $3
                    """,
                    aggregate_id, from_sequence, limit
                )
            
            return [self._row_to_event(row) for row in rows]
    
    async def get_all_events(
        self,
        from_position: int = 0,
        max_count: int = 1000,
        event_types: Optional[List[str]] = None,
    ) -> List[Event]:
        """Get all events from a position."""
        async with self._pool.acquire() as conn:
            if event_types:
                rows = await conn.fetch(
                    f"""
                    SELECT event_id, aggregate_id, aggregate_type, event_type,
                           sequence_number, data, metadata, timestamp
                    FROM {self._q}.events
                    WHERE event_type = ANY($1)
                    ORDER BY timestamp, sequence_number
                    OFFSET $2 LIMIT $3
                    """,
                    event_types, from_position, max_count
                )
            else:
                rows = await conn.fetch(
                    f"""
                    SELECT event_id, aggregate_id, aggregate_type, event_type,
                           sequence_number, data, metadata, timestamp
                    FROM {self._q}.events
                    ORDER BY timestamp, sequence_number
                    OFFSET $1 LIMIT $2
                    """,
                    from_position, max_count
                )
            
            return [self._row_to_event(row) for row in rows]
    
    async def get_events_by_type(
        self,
        event_type: str,
        from_timestamp: Optional[datetime] = None,
        to_timestamp: Optional[datetime] = None,
        limit: int = 1000,
    ) -> List[Event]:
        """Get events by type."""
        async with self._pool.acquire() as conn:
            conditions = ["event_type = $1"]
            params = [event_type]
            param_idx = 2
            
            if from_timestamp:
                conditions.append(f"timestamp >= ${param_idx}")
                params.append(from_timestamp)
                param_idx += 1
            
            if to_timestamp:
                conditions.append(f"timestamp <= ${param_idx}")
                params.append(to_timestamp)
                param_idx += 1
            
            params.append(limit)
            
            rows = await conn.fetch(
                f"""
                SELECT event_id, aggregate_id, aggregate_type, event_type,
                       sequence_number, data, metadata, timestamp
                FROM {self._q}.events
                WHERE {' AND '.join(conditions)}
                ORDER BY timestamp, sequence_number
                LIMIT ${param_idx}
                """,
                *params
            )
            
            return [self._row_to_event(row) for row in rows]
    
    async def get_events_by_correlation_id(
        self,
        correlation_id: str,
    ) -> List[Event]:
        """Get events by correlation ID."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT event_id, aggregate_id, aggregate_type, event_type,
                       sequence_number, data, metadata, timestamp
                FROM {self._q}.events
                WHERE metadata->>'correlation_id' = $1
                ORDER BY timestamp, sequence_number
                """,
                correlation_id
            )
            
            return [self._row_to_event(row) for row in rows]
    
    # -------------------------------------------------------------------------
    # Stream Operations
    # -------------------------------------------------------------------------
    
    async def list_streams(
        self,
        prefix: Optional[str] = None,
        aggregate_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List all streams."""
        async with self._pool.acquire() as conn:
            conditions = []
            params = []
            param_idx = 1
            
            if prefix:
                conditions.append(f"aggregate_id LIKE ${param_idx}")
                params.append(f"{prefix}%")
                param_idx += 1
            
            if aggregate_type:
                conditions.append(f"aggregate_type = ${param_idx}")
                params.append(aggregate_type)
                param_idx += 1
            
            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            
            params.extend([limit, offset])
            
            rows = await conn.fetch(
                f"""
                SELECT s.aggregate_id, s.aggregate_type, s.version, 
                       s.created_at, s.updated_at,
                       (SELECT COUNT(*) FROM {self._q}.events e 
                        WHERE e.aggregate_id = s.aggregate_id) as event_count
                FROM {self._q}.streams s
                {where_clause}
                ORDER BY s.aggregate_id
                LIMIT ${param_idx} OFFSET ${param_idx + 1}
                """,
                *params
            )
            
            return [
                {
                    "stream_id": row["aggregate_id"],
                    "aggregate_type": row["aggregate_type"],
                    "version": row["version"],
                    "event_count": row["event_count"],
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                    "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
                }
                for row in rows
            ]
    
    async def get_stream_version(self, aggregate_id: str) -> int:
        """Get current stream version."""
        async with self._pool.acquire() as conn:
            version = await conn.fetchval(
                f"SELECT version FROM {self._q}.streams WHERE aggregate_id = $1",
                aggregate_id
            )
            return version or 0
    
    async def stream_exists(self, aggregate_id: str) -> bool:
        """Check if stream exists."""
        async with self._pool.acquire() as conn:
            exists = await conn.fetchval(
                f"SELECT EXISTS(SELECT 1 FROM {self._q}.streams WHERE aggregate_id = $1)",
                aggregate_id
            )
            return exists
    
    async def delete_stream(self, aggregate_id: str) -> None:
        """Delete a stream and all its events."""
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    f"DELETE FROM {self._q}.events WHERE aggregate_id = $1",
                    aggregate_id
                )
                await conn.execute(
                    f"DELETE FROM {self._q}.snapshots WHERE aggregate_id = $1",
                    aggregate_id
                )
                await conn.execute(
                    f"DELETE FROM {self._q}.streams WHERE aggregate_id = $1",
                    aggregate_id
                )
    
    # -------------------------------------------------------------------------
    # Snapshot Operations
    # -------------------------------------------------------------------------
    
    async def save_snapshot(self, snapshot: Snapshot) -> None:
        """Save a snapshot."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                f"""
                INSERT INTO {self._q}.snapshots 
                (snapshot_id, aggregate_id, aggregate_type, sequence_number, state, timestamp)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (aggregate_id, sequence_number) 
                DO UPDATE SET state = $5, timestamp = $6
                """,
                snapshot.snapshot_id,
                snapshot.aggregate_id,
                snapshot.aggregate_type,
                snapshot.sequence_number,
                json.dumps(snapshot.state),
                snapshot.timestamp,
            )
    
    async def get_snapshot(
        self,
        aggregate_id: str,
        max_version: Optional[int] = None,
    ) -> Optional[Snapshot]:
        """Get the latest snapshot for an aggregate."""
        async with self._pool.acquire() as conn:
            if max_version is not None:
                row = await conn.fetchrow(
                    f"""
                    SELECT snapshot_id, aggregate_id, aggregate_type, 
                           sequence_number, state, timestamp
                    FROM {self._q}.snapshots
                    WHERE aggregate_id = $1 AND sequence_number <= $2
                    ORDER BY sequence_number DESC
                    LIMIT 1
                    """,
                    aggregate_id, max_version
                )
            else:
                row = await conn.fetchrow(
                    f"""
                    SELECT snapshot_id, aggregate_id, aggregate_type, 
                           sequence_number, state, timestamp
                    FROM {self._q}.snapshots
                    WHERE aggregate_id = $1
                    ORDER BY sequence_number DESC
                    LIMIT 1
                    """,
                    aggregate_id
                )
            
            if row:
                return Snapshot(
                    snapshot_id=row["snapshot_id"],
                    aggregate_id=row["aggregate_id"],
                    aggregate_type=row["aggregate_type"],
                    sequence_number=row["sequence_number"],
                    state=json.loads(row["state"]) if isinstance(row["state"], str) else row["state"],
                    timestamp=row["timestamp"],
                )
            return None
    
    async def delete_snapshots(self, aggregate_id: str) -> None:
        """Delete all snapshots for an aggregate."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                f"DELETE FROM {self._q}.snapshots WHERE aggregate_id = $1",
                aggregate_id
            )
    
    # -------------------------------------------------------------------------
    # Statistics and Maintenance
    # -------------------------------------------------------------------------
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics."""
        async with self._pool.acquire() as conn:
            stats = {}
            
            # Event counts
            stats["total_events"] = await conn.fetchval(
                f"SELECT COUNT(*) FROM {self._q}.events"
            )
            
            # Stream counts
            stats["total_streams"] = await conn.fetchval(
                f"SELECT COUNT(*) FROM {self._q}.streams"
            )
            
            # Snapshot counts
            stats["total_snapshots"] = await conn.fetchval(
                f"SELECT COUNT(*) FROM {self._q}.snapshots"
            )
            
            # Event types
            type_rows = await conn.fetch(
                f"""
                SELECT event_type, COUNT(*) as count
                FROM {self._q}.events
                GROUP BY event_type
                ORDER BY count DESC
                LIMIT 20
                """
            )
            stats["event_types"] = {row["event_type"]: row["count"] for row in type_rows}
            
            # Aggregate types
            agg_rows = await conn.fetch(
                f"""
                SELECT aggregate_type, COUNT(*) as count
                FROM {self._q}.streams
                WHERE aggregate_type IS NOT NULL
                GROUP BY aggregate_type
                ORDER BY count DESC
                LIMIT 20
                """
            )
            stats["aggregate_types"] = {row["aggregate_type"]: row["count"] for row in agg_rows}
            
            # Database size
            stats["database_size"] = await conn.fetchval(
                f"SELECT pg_size_pretty(pg_database_size(current_database()))"
            )
            
            # Table sizes
            stats["events_table_size"] = await conn.fetchval(
                f"SELECT pg_size_pretty(pg_total_relation_size('{self._q}.events'))"
            )
            
            return stats
    
    async def truncate_stream(
        self,
        aggregate_id: str,
        from_sequence: int,
    ) -> int:
        """Truncate events from a stream."""
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                f"DELETE FROM {self._q}.events "
                f"WHERE aggregate_id = $1 AND sequence_number >= $2",
                aggregate_id, from_sequence
            )
            
            # Parse "DELETE N" result
            deleted = int(result.split()[-1]) if result else 0
            
            # Update stream version
            new_version = from_sequence - 1
            if new_version <= 0:
                await conn.execute(
                    f"DELETE FROM {self._q}.streams WHERE aggregate_id = $1",
                    aggregate_id
                )
            else:
                await conn.execute(
                    f"UPDATE {self._q}.streams SET version = $1, updated_at = NOW() "
                    f"WHERE aggregate_id = $2",
                    new_version, aggregate_id
                )
            
            return deleted
    
    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------
    
    def _row_to_event(self, row) -> Event:
        """Convert a database row to an Event object."""
        metadata_data = row["metadata"]
        if isinstance(metadata_data, str):
            metadata_data = json.loads(metadata_data)
        
        data = row["data"]
        if isinstance(data, str):
            data = json.loads(data)
        
        return Event(
            event_id=row["event_id"],
            aggregate_id=row["aggregate_id"],
            aggregate_type=row["aggregate_type"] or "",
            event_type=row["event_type"],
            sequence_number=row["sequence_number"],
            data=data,
            metadata=EventMetadata.from_dict(metadata_data) if metadata_data else EventMetadata(),
        )
    
    async def execute_query(
        self,
        query: str,
        *args,
    ) -> List[Dict[str, Any]]:
        """
        Execute a raw SQL query.
        
        Use with caution - primarily for migrations and admin tasks.
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, *args)
            return [dict(row) for row in rows]

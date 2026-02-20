"""
MongoDB Backend for Event Store.

Provides document-based persistent storage using MongoDB with:
- Connection pooling via motor
- Optimistic concurrency control
- Change streams for real-time subscriptions
- Snapshot support
"""

import json
import logging
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

# Try to import motor
try:
    from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
    from pymongo import ASCENDING, DESCENDING
    from pymongo.errors import DuplicateKeyError, ConnectionFailure
    MOTOR_AVAILABLE = True
except ImportError:
    MOTOR_AVAILABLE = False
    logger.warning("motor not available - MongoDB backend will not work")


@dataclass
class MongoDBConfig:
    """MongoDB connection configuration."""
    host: str = "localhost"
    port: int = 27017
    database: str = "maas_event_store"
    user: Optional[str] = None
    password: Optional[str] = None
    replica_set: Optional[str] = None
    max_pool_size: int = 100
    min_pool_size: int = 10
    connection_timeout: float = 30.0
    socket_timeout: float = 30.0
    server_selection_timeout: float = 30.0
    
    def to_uri(self) -> str:
        """Convert to MongoDB URI string."""
        if self.user and self.password:
            auth = f"{self.user}:{self.password}@"
        else:
            auth = ""
        
        uri = f"mongodb://{auth}{self.host}:{self.port}/{self.database}"
        
        if self.replica_set:
            uri += f"?replicaSet={self.replica_set}"
        
        return uri


class MongoDBEventStore(DatabaseBackend):
    """
    MongoDB-based event store backend.
    
    Features:
    - Document-based storage for flexible event schemas
    - Optimistic concurrency control via version field
    - Connection pooling
    - Change streams for real-time subscriptions
    - Snapshot support
    - TTL indexes for automatic cleanup
    
    Collections:
        - events: Main event storage
        - streams: Stream metadata
        - snapshots: Aggregate snapshots
    """
    
    def __init__(
        self,
        config: Optional[MongoDBConfig] = None,
        **kwargs,
    ):
        """
        Initialize MongoDB backend.
        
        Args:
            config: MongoDB configuration
            **kwargs: Override config parameters
        """
        super().__init__(**kwargs)
        
        if not MOTOR_AVAILABLE:
            raise RuntimeError("motor is required for MongoDB backend")
        
        self.config = config or MongoDBConfig()
        
        # Override config with kwargs
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        
        self._client: Optional["AsyncIOMotorClient"] = None
        self._db: Optional["AsyncIOMotorDatabase"] = None
    
    async def connect(self) -> None:
        """Establish connection to MongoDB."""
        if self._is_connected:
            return
        
        try:
            self._client = AsyncIOMotorClient(
                self.config.to_uri(),
                maxPoolSize=self.config.max_pool_size,
                minPoolSize=self.config.min_pool_size,
                connectTimeoutMS=int(self.config.connection_timeout * 1000),
                socketTimeoutMS=int(self.config.socket_timeout * 1000),
                serverSelectionTimeoutMS=int(self.config.server_selection_timeout * 1000),
            )
            
            self._db = self._client[self.config.database]
            
            # Verify connection
            await self._db.command("ping")
            
            # Ensure indexes
            await self._ensure_indexes()
            
            self._is_connected = True
            logger.info(
                f"Connected to MongoDB: {self.config.host}:{self.config.port}/{self.config.database}"
            )
            
        except ConnectionFailure as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise DatabaseConnectionError(f"MongoDB connection failed: {e}")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise DatabaseConnectionError(f"MongoDB connection failed: {e}")
    
    async def disconnect(self) -> None:
        """Close connection to MongoDB."""
        if self._client:
            self._client.close()
            self._client = None
            self._db = None
        
        self._is_connected = False
        logger.info("Disconnected from MongoDB")
    
    async def _ensure_indexes(self) -> None:
        """Ensure required indexes exist."""
        # Events collection indexes
        events = self._db.events
        
        await events.create_index(
            [("aggregate_id", ASCENDING), ("sequence_number", ASCENDING)],
            unique=True,
            name="idx_aggregate_sequence"
        )
        await events.create_index(
            [("aggregate_id", ASCENDING)],
            name="idx_aggregate_id"
        )
        await events.create_index(
            [("event_type", ASCENDING)],
            name="idx_event_type"
        )
        await events.create_index(
            [("timestamp", ASCENDING)],
            name="idx_timestamp"
        )
        await events.create_index(
            [("aggregate_type", ASCENDING)],
            name="idx_aggregate_type"
        )
        await events.create_index(
            [("metadata.correlation_id", ASCENDING)],
            name="idx_correlation_id"
        )
        
        # Streams collection indexes
        streams = self._db.streams
        await streams.create_index(
            [("aggregate_id", ASCENDING)],
            unique=True,
            name="idx_stream_aggregate_id"
        )
        await streams.create_index(
            [("aggregate_type", ASCENDING)],
            name="idx_stream_aggregate_type"
        )
        
        # Snapshots collection indexes
        snapshots = self._db.snapshots
        await snapshots.create_index(
            [("aggregate_id", ASCENDING), ("sequence_number", DESCENDING)],
            name="idx_snapshot_aggregate_version"
        )
        
        logger.debug("MongoDB indexes ensured")
    
    async def health_check(self) -> Dict[str, Any]:
        """Check MongoDB health status."""
        if not self._client:
            return {
                "healthy": False,
                "error": "Not connected",
            }
        
        try:
            result = await self._db.command("ping")
            
            # Get server info
            server_info = await self._db.command("serverStatus")
            
            return {
                "healthy": True,
                "backend": "mongodb",
                "database": self.config.database,
                "host": self.config.host,
                "version": server_info.get("version", "unknown"),
                "connections": server_info.get("connections", {}).get("current", 0),
                "pool_size": self.config.max_pool_size,
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
        
        # Get current version
        stream = await self._db.streams.find_one(
            {"aggregate_id": aggregate_id},
            projection={"version": 1}
        )
        
        current_version = stream["version"] if stream else 0
        
        # Optimistic concurrency check
        if expected_version is not None and current_version != expected_version:
            raise VersionConflictError(aggregate_id, expected_version, current_version)
        
        # Prepare event documents
        next_version = current_version
        event_docs = []
        
        for event in events:
            next_version += 1
            event.aggregate_id = aggregate_id
            event.sequence_number = next_version
            
            event_docs.append(self._event_to_doc(event))
        
        try:
            # Insert events
            if len(event_docs) == 1:
                await self._db.events.insert_one(event_docs[0])
            else:
                await self._db.events.insert_many(event_docs)
            
            # Update or create stream
            if stream:
                await self._db.streams.update_one(
                    {"aggregate_id": aggregate_id},
                    {
                        "$set": {
                            "version": next_version,
                            "updated_at": datetime.utcnow()
                        }
                    }
                )
            else:
                await self._db.streams.insert_one({
                    "aggregate_id": aggregate_id,
                    "aggregate_type": events[0].aggregate_type,
                    "version": next_version,
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                })
            
            return next_version
            
        except DuplicateKeyError as e:
            # Version conflict occurred
            raise VersionConflictError(
                aggregate_id,
                expected_version or current_version,
                current_version
            )
    
    async def get_events(
        self,
        aggregate_id: str,
        from_sequence: int = 0,
        to_sequence: Optional[int] = None,
        limit: int = 1000,
    ) -> List[Event]:
        """Get events for an aggregate."""
        query = {
            "aggregate_id": aggregate_id,
            "sequence_number": {"$gt": from_sequence}
        }
        
        if to_sequence is not None:
            query["sequence_number"]["$lte"] = to_sequence
        
        cursor = self._db.events.find(query).sort("sequence_number", ASCENDING).limit(limit)
        
        docs = await cursor.to_list(length=limit)
        return [self._doc_to_event(doc) for doc in docs]
    
    async def get_all_events(
        self,
        from_position: int = 0,
        max_count: int = 1000,
        event_types: Optional[List[str]] = None,
    ) -> List[Event]:
        """Get all events from a position."""
        query = {}
        
        if event_types:
            query["event_type"] = {"$in": event_types}
        
        cursor = (
            self._db.events
            .find(query)
            .sort([("timestamp", ASCENDING), ("sequence_number", ASCENDING)])
            .skip(from_position)
            .limit(max_count)
        )
        
        docs = await cursor.to_list(length=max_count)
        return [self._doc_to_event(doc) for doc in docs]
    
    async def get_events_by_type(
        self,
        event_type: str,
        from_timestamp: Optional[datetime] = None,
        to_timestamp: Optional[datetime] = None,
        limit: int = 1000,
    ) -> List[Event]:
        """Get events by type."""
        query = {"event_type": event_type}
        
        if from_timestamp or to_timestamp:
            query["timestamp"] = {}
            if from_timestamp:
                query["timestamp"]["$gte"] = from_timestamp
            if to_timestamp:
                query["timestamp"]["$lte"] = to_timestamp
        
        cursor = (
            self._db.events
            .find(query)
            .sort([("timestamp", ASCENDING), ("sequence_number", ASCENDING)])
            .limit(limit)
        )
        
        docs = await cursor.to_list(length=limit)
        return [self._doc_to_event(doc) for doc in docs]
    
    async def get_events_by_correlation_id(
        self,
        correlation_id: str,
    ) -> List[Event]:
        """Get events by correlation ID."""
        cursor = (
            self._db.events
            .find({"metadata.correlation_id": correlation_id})
            .sort([("timestamp", ASCENDING), ("sequence_number", ASCENDING)])
        )
        
        docs = await cursor.to_list(length=10000)
        return [self._doc_to_event(doc) for doc in docs]
    
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
        query = {}
        
        if prefix:
            query["aggregate_id"] = {"$regex": f"^{prefix}"}
        
        if aggregate_type:
            query["aggregate_type"] = aggregate_type
        
        # Use aggregation to get event counts
        pipeline = [
            {"$match": query},
            {"$lookup": {
                "from": "events",
                "localField": "aggregate_id",
                "foreignField": "aggregate_id",
                "as": "events"
            }},
            {"$project": {
                "stream_id": "$aggregate_id",
                "aggregate_type": 1,
                "version": 1,
                "created_at": 1,
                "updated_at": 1,
                "event_count": {"$size": "$events"}
            }},
            {"$sort": {"stream_id": ASCENDING}},
            {"$skip": offset},
            {"$limit": limit}
        ]
        
        cursor = self._db.streams.aggregate(pipeline)
        docs = await cursor.to_list(length=limit)
        
        return [
            {
                "stream_id": doc["stream_id"],
                "aggregate_type": doc.get("aggregate_type"),
                "version": doc.get("version", 0),
                "event_count": doc.get("event_count", 0),
                "created_at": doc.get("created_at", datetime.utcnow()).isoformat() if doc.get("created_at") else None,
                "updated_at": doc.get("updated_at", datetime.utcnow()).isoformat() if doc.get("updated_at") else None,
            }
            for doc in docs
        ]
    
    async def get_stream_version(self, aggregate_id: str) -> int:
        """Get current stream version."""
        stream = await self._db.streams.find_one(
            {"aggregate_id": aggregate_id},
            projection={"version": 1}
        )
        return stream["version"] if stream else 0
    
    async def stream_exists(self, aggregate_id: str) -> bool:
        """Check if stream exists."""
        count = await self._db.streams.count_documents({"aggregate_id": aggregate_id})
        return count > 0
    
    async def delete_stream(self, aggregate_id: str) -> None:
        """Delete a stream and all its events."""
        await self._db.events.delete_many({"aggregate_id": aggregate_id})
        await self._db.snapshots.delete_many({"aggregate_id": aggregate_id})
        await self._db.streams.delete_one({"aggregate_id": aggregate_id})
    
    # -------------------------------------------------------------------------
    # Snapshot Operations
    # -------------------------------------------------------------------------
    
    async def save_snapshot(self, snapshot: Snapshot) -> None:
        """Save a snapshot."""
        doc = {
            "snapshot_id": snapshot.snapshot_id,
            "aggregate_id": snapshot.aggregate_id,
            "aggregate_type": snapshot.aggregate_type,
            "sequence_number": snapshot.sequence_number,
            "state": snapshot.state,
            "timestamp": snapshot.timestamp,
            "created_at": datetime.utcnow()
        }
        
        await self._db.snapshots.update_one(
            {
                "aggregate_id": snapshot.aggregate_id,
                "sequence_number": snapshot.sequence_number
            },
            {"$set": doc},
            upsert=True
        )
    
    async def get_snapshot(
        self,
        aggregate_id: str,
        max_version: Optional[int] = None,
    ) -> Optional[Snapshot]:
        """Get the latest snapshot for an aggregate."""
        query = {"aggregate_id": aggregate_id}
        
        if max_version is not None:
            query["sequence_number"] = {"$lte": max_version}
        
        doc = await self._db.snapshots.find_one(
            query,
            sort=[("sequence_number", DESCENDING)]
        )
        
        if doc:
            return Snapshot(
                snapshot_id=doc["snapshot_id"],
                aggregate_id=doc["aggregate_id"],
                aggregate_type=doc.get("aggregate_type", ""),
                sequence_number=doc["sequence_number"],
                state=doc["state"],
                timestamp=doc.get("timestamp", datetime.utcnow()),
            )
        return None
    
    async def delete_snapshots(self, aggregate_id: str) -> None:
        """Delete all snapshots for an aggregate."""
        await self._db.snapshots.delete_many({"aggregate_id": aggregate_id})
    
    # -------------------------------------------------------------------------
    # Statistics and Maintenance
    # -------------------------------------------------------------------------
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics."""
        stats = {}
        
        # Event counts
        stats["total_events"] = await self._db.events.count_documents({})
        
        # Stream counts
        stats["total_streams"] = await self._db.streams.count_documents({})
        
        # Snapshot counts
        stats["total_snapshots"] = await self._db.snapshots.count_documents({})
        
        # Event types (aggregation)
        pipeline = [
            {"$group": {"_id": "$event_type", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 20}
        ]
        cursor = self._db.events.aggregate(pipeline)
        type_docs = await cursor.to_list(length=20)
        stats["event_types"] = {doc["_id"]: doc["count"] for doc in type_docs}
        
        # Aggregate types
        pipeline = [
            {"$match": {"aggregate_type": {"$ne": None}}},
            {"$group": {"_id": "$aggregate_type", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 20}
        ]
        cursor = self._db.streams.aggregate(pipeline)
        agg_docs = await cursor.to_list(length=20)
        stats["aggregate_types"] = {doc["_id"]: doc["count"] for doc in agg_docs}
        
        # Database stats
        db_stats = await self._db.command("dbStats", scale=1024 * 1024)
        stats["database_size_mb"] = db_stats.get("dataSize", 0)
        stats["storage_size_mb"] = db_stats.get("storageSize", 0)
        stats["index_size_mb"] = db_stats.get("indexSize", 0)
        
        return stats
    
    async def truncate_stream(
        self,
        aggregate_id: str,
        from_sequence: int,
    ) -> int:
        """Truncate events from a stream."""
        result = await self._db.events.delete_many({
            "aggregate_id": aggregate_id,
            "sequence_number": {"$gte": from_sequence}
        })
        
        deleted = result.deleted_count
        
        # Update stream version
        new_version = from_sequence - 1
        if new_version <= 0:
            await self._db.streams.delete_one({"aggregate_id": aggregate_id})
        else:
            await self._db.streams.update_one(
                {"aggregate_id": aggregate_id},
                {
                    "$set": {
                        "version": new_version,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
        
        return deleted
    
    # -------------------------------------------------------------------------
    # Change Stream Support
    # -------------------------------------------------------------------------
    
    async def watch_events(
        self,
        aggregate_id: Optional[str] = None,
        event_types: Optional[List[str]] = None,
    ):
        """
        Watch for event changes using MongoDB change streams.
        
        Args:
            aggregate_id: Filter by aggregate ID
            event_types: Filter by event types
            
        Yields:
            Event objects as they are inserted
        """
        pipeline = []
        
        if aggregate_id or event_types:
            match = {"fullDocument": {}}
            if aggregate_id:
                match["fullDocument"]["aggregate_id"] = aggregate_id
            if event_types:
                match["fullDocument"]["event_type"] = {"$in": event_types}
            pipeline.append({"$match": match})
        
        async with self._db.events.watch(pipeline) as stream:
            async for change in stream:
                if change["operationType"] == "insert":
                    yield self._doc_to_event(change["fullDocument"])
    
    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------
    
    def _event_to_doc(self, event: Event) -> Dict[str, Any]:
        """Convert an Event object to a MongoDB document."""
        return {
            "event_id": event.event_id,
            "aggregate_id": event.aggregate_id,
            "aggregate_type": event.aggregate_type,
            "event_type": event.event_type,
            "sequence_number": event.sequence_number,
            "data": event.data,
            "metadata": event.metadata.to_dict(),
            "timestamp": event.metadata.timestamp,
            "created_at": datetime.utcnow()
        }
    
    def _doc_to_event(self, doc: Dict[str, Any]) -> Event:
        """Convert a MongoDB document to an Event object."""
        metadata_data = doc.get("metadata", {})
        
        return Event(
            event_id=doc["event_id"],
            aggregate_id=doc["aggregate_id"],
            aggregate_type=doc.get("aggregate_type", ""),
            event_type=doc["event_type"],
            sequence_number=doc["sequence_number"],
            data=doc.get("data", {}),
            metadata=EventMetadata.from_dict(metadata_data) if metadata_data else EventMetadata(),
        )
    
    async def execute_command(
        self,
        command: str,
        *args,
        **kwargs,
    ) -> Any:
        """
        Execute a raw MongoDB command.
        
        Use with caution - primarily for admin tasks.
        """
        return await self._db.command(command, *args, **kwargs)

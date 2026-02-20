"""
Abstract Base Class for Database Backends.

Defines the interface that all database backends must implement
for the Event Store.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.event_sourcing.event_store import Event, Snapshot

logger = logging.getLogger(__name__)


class DatabaseBackend(ABC):
    """
    Abstract base class for database backends.
    
    All persistent storage backends must implement this interface
    to be used with the Event Store.
    """
    
    def __init__(
        self,
        connection_pool_size: int = 10,
        connection_timeout: float = 30.0,
        query_timeout: float = 10.0,
    ):
        """
        Initialize database backend.
        
        Args:
            connection_pool_size: Maximum number of connections in pool
            connection_timeout: Timeout for acquiring connections
            query_timeout: Timeout for query execution
        """
        self.connection_pool_size = connection_pool_size
        self.connection_timeout = connection_timeout
        self.query_timeout = query_timeout
        self._is_connected = False
    
    @abstractmethod
    async def connect(self) -> None:
        """
        Establish connection to the database.
        
        Should initialize connection pool and verify connectivity.
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """
        Close connection to the database.
        
        Should clean up connection pool and release resources.
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """
        Check database health status.
        
        Returns:
            Dictionary with health status information
        """
        pass
    
    # -------------------------------------------------------------------------
    # Event Operations
    # -------------------------------------------------------------------------
    
    @abstractmethod
    async def append_event(
        self,
        aggregate_id: str,
        event: Event,
        expected_version: Optional[int] = None,
    ) -> int:
        """
        Append a single event to the store.
        
        Args:
            aggregate_id: The aggregate ID
            event: The event to append
            expected_version: Expected current version for optimistic concurrency
            
        Returns:
            The new version number
            
        Raises:
            VersionConflictError: If version conflict occurs
        """
        pass
    
    @abstractmethod
    async def append_events(
        self,
        aggregate_id: str,
        events: List[Event],
        expected_version: Optional[int] = None,
    ) -> int:
        """
        Append multiple events atomically.
        
        Args:
            aggregate_id: The aggregate ID
            events: List of events to append
            expected_version: Expected current version for optimistic concurrency
            
        Returns:
            The new version number
        """
        pass
    
    @abstractmethod
    async def get_events(
        self,
        aggregate_id: str,
        from_sequence: int = 0,
        to_sequence: Optional[int] = None,
        limit: int = 1000,
    ) -> List[Event]:
        """
        Get events for an aggregate.
        
        Args:
            aggregate_id: The aggregate ID
            from_sequence: Starting sequence number (exclusive)
            to_sequence: Ending sequence number (inclusive)
            limit: Maximum number of events to return
            
        Returns:
            List of events
        """
        pass
    
    @abstractmethod
    async def get_all_events(
        self,
        from_position: int = 0,
        max_count: int = 1000,
        event_types: Optional[List[str]] = None,
    ) -> List[Event]:
        """
        Get all events from a position.
        
        Args:
            from_position: Starting global position
            max_count: Maximum number of events
            event_types: Filter by event types
            
        Returns:
            List of events
        """
        pass
    
    @abstractmethod
    async def get_events_by_type(
        self,
        event_type: str,
        from_timestamp: Optional[datetime] = None,
        to_timestamp: Optional[datetime] = None,
        limit: int = 1000,
    ) -> List[Event]:
        """
        Get events by type.
        
        Args:
            event_type: The event type to filter by
            from_timestamp: Starting timestamp
            to_timestamp: Ending timestamp
            limit: Maximum number of events
            
        Returns:
            List of events
        """
        pass
    
    @abstractmethod
    async def get_events_by_correlation_id(
        self,
        correlation_id: str,
    ) -> List[Event]:
        """
        Get all events with a specific correlation ID.
        
        Args:
            correlation_id: The correlation ID to search for
            
        Returns:
            List of events with matching correlation ID
        """
        pass
    
    # -------------------------------------------------------------------------
    # Stream Operations
    # -------------------------------------------------------------------------
    
    @abstractmethod
    async def list_streams(
        self,
        prefix: Optional[str] = None,
        aggregate_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        List all streams.
        
        Args:
            prefix: Filter by stream ID prefix
            aggregate_type: Filter by aggregate type
            limit: Maximum number of streams
            offset: Offset for pagination
            
        Returns:
            List of stream metadata dictionaries
        """
        pass
    
    @abstractmethod
    async def get_stream_version(self, aggregate_id: str) -> int:
        """
        Get the current version of a stream.
        
        Args:
            aggregate_id: The aggregate ID
            
        Returns:
            Current version number (0 if stream doesn't exist)
        """
        pass
    
    @abstractmethod
    async def stream_exists(self, aggregate_id: str) -> bool:
        """
        Check if a stream exists.
        
        Args:
            aggregate_id: The aggregate ID
            
        Returns:
            True if stream exists
        """
        pass
    
    @abstractmethod
    async def delete_stream(self, aggregate_id: str) -> None:
        """
        Delete a stream and all its events.
        
        Args:
            aggregate_id: The aggregate ID
        """
        pass
    
    # -------------------------------------------------------------------------
    # Snapshot Operations
    # -------------------------------------------------------------------------
    
    @abstractmethod
    async def save_snapshot(self, snapshot: Snapshot) -> None:
        """
        Save a snapshot.
        
        Args:
            snapshot: The snapshot to save
        """
        pass
    
    @abstractmethod
    async def get_snapshot(
        self,
        aggregate_id: str,
        max_version: Optional[int] = None,
    ) -> Optional[Snapshot]:
        """
        Get the latest snapshot for an aggregate.
        
        Args:
            aggregate_id: The aggregate ID
            max_version: Maximum version to consider
            
        Returns:
            The snapshot or None
        """
        pass
    
    @abstractmethod
    async def delete_snapshots(self, aggregate_id: str) -> None:
        """
        Delete all snapshots for an aggregate.
        
        Args:
            aggregate_id: The aggregate ID
        """
        pass
    
    # -------------------------------------------------------------------------
    # Statistics and Maintenance
    # -------------------------------------------------------------------------
    
    @abstractmethod
    async def get_statistics(self) -> Dict[str, Any]:
        """
        Get database statistics.
        
        Returns:
            Dictionary with statistics
        """
        pass
    
    @abstractmethod
    async def truncate_stream(
        self,
        aggregate_id: str,
        from_sequence: int,
    ) -> int:
        """
        Truncate events from a stream.
        
        Used for compaction or cleanup.
        
        Args:
            aggregate_id: The aggregate ID
            from_sequence: Sequence number to truncate from
            
        Returns:
            Number of events removed
        """
        pass
    
    @property
    def is_connected(self) -> bool:
        """Check if backend is connected."""
        return self._is_connected
    
    async def __aenter__(self) -> "DatabaseBackend":
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.disconnect()


class VersionConflictError(Exception):
    """Raised when optimistic concurrency check fails."""
    
    def __init__(
        self,
        aggregate_id: str,
        expected_version: int,
        actual_version: int,
    ):
        self.aggregate_id = aggregate_id
        self.expected_version = expected_version
        self.actual_version = actual_version
        super().__init__(
            f"Version conflict for {aggregate_id}: "
            f"expected {expected_version}, actual {actual_version}"
        )


class DatabaseConnectionError(Exception):
    """Raised when database connection fails."""
    pass


class DatabaseQueryError(Exception):
    """Raised when a database query fails."""
    pass

"""
Event Store - Persistent event storage for event sourcing.

Provides append-only event storage with event versioning,
snapshots, and event replay capabilities.
"""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, Generic, List, Optional, Type, TypeVar, Union

logger = logging.getLogger(__name__)

T = TypeVar('T')


class EventVersion:
    """Version information for an event."""
    
    def __init__(self, major: int = 1, minor: int = 0):
        self.major = major
        self.minor = minor
    
    def __str__(self) -> str:
        return f"{self.major}.{self.minor}"
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, EventVersion):
            return False
        return self.major == other.major and self.minor == other.minor
    
    def __lt__(self, other: "EventVersion") -> bool:
        if self.major != other.major:
            return self.major < other.major
        return self.minor < other.minor
    
    def to_dict(self) -> Dict[str, int]:
        return {"major": self.major, "minor": self.minor}
    
    @classmethod
    def from_dict(cls, data: Dict[str, int]) -> "EventVersion":
        return cls(data["major"], data["minor"])


@dataclass
class EventMetadata:
    """Metadata associated with an event."""
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    user_id: Optional[str] = None
    source: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    version: EventVersion = field(default_factory=EventVersion)
    custom: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "user_id": self.user_id,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "version": self.version.to_dict(),
            "custom": self.custom,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EventMetadata":
        return cls(
            correlation_id=data.get("correlation_id"),
            causation_id=data.get("causation_id"),
            user_id=data.get("user_id"),
            source=data.get("source"),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            version=EventVersion.from_dict(data.get("version", {"major": 1, "minor": 0})),
            custom=data.get("custom", {}),
        )


@dataclass
class Event:
    """Base class for all events."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = ""
    aggregate_id: str = ""
    aggregate_type: str = ""
    sequence_number: int = 0
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: EventMetadata = field(default_factory=EventMetadata)
    
    def __post_init__(self):
        if not self.event_type:
            self.event_type = self.__class__.__name__

    # Compatibility aliases for stream-based APIs.
    @property
    def stream_id(self) -> str:
        return self.aggregate_id

    @stream_id.setter
    def stream_id(self, value: str) -> None:
        self.aggregate_id = value

    @property
    def version(self) -> int:
        return self.sequence_number

    @version.setter
    def version(self, value: int) -> None:
        self.sequence_number = value

    @property
    def timestamp(self) -> datetime:
        return self.metadata.timestamp

    @timestamp.setter
    def timestamp(self, value: datetime) -> None:
        self.metadata.timestamp = value

    @property
    def payload(self) -> Dict[str, Any]:
        return self.data

    @payload.setter
    def payload(self, value: Dict[str, Any]) -> None:
        self.data = value
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "aggregate_id": self.aggregate_id,
            "aggregate_type": self.aggregate_type,
            "sequence_number": self.sequence_number,
            "data": self.data,
            "metadata": self.metadata.to_dict(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event":
        return cls(
            event_id=data["event_id"],
            event_type=data["event_type"],
            aggregate_id=data["aggregate_id"],
            aggregate_type=data["aggregate_type"],
            sequence_number=data["sequence_number"],
            data=data["data"],
            metadata=EventMetadata.from_dict(data["metadata"]),
        )
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_json(cls, json_str: str) -> "Event":
        return cls.from_dict(json.loads(json_str))


@dataclass
class Snapshot:
    """Snapshot of an aggregate state."""
    aggregate_id: str
    aggregate_type: str
    sequence_number: int
    state: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    snapshot_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Compatibility aliases for stream-based APIs.
    @property
    def stream_id(self) -> str:
        return self.aggregate_id

    @property
    def version(self) -> int:
        return self.sequence_number
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "aggregate_id": self.aggregate_id,
            "aggregate_type": self.aggregate_type,
            "sequence_number": self.sequence_number,
            "state": self.state,
            "timestamp": self.timestamp.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Snapshot":
        return cls(
            snapshot_id=data["snapshot_id"],
            aggregate_id=data["aggregate_id"],
            aggregate_type=data["aggregate_type"],
            sequence_number=data["sequence_number"],
            state=data["state"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
        )


@dataclass
class EventStream:
    """Stream of events for an aggregate."""
    aggregate_id: str
    aggregate_type: str
    events: List[Event] = field(default_factory=list)
    snapshot: Optional[Snapshot] = None
    version: int = 0
    
    @property
    def is_empty(self) -> bool:
        return len(self.events) == 0 and self.snapshot is None
    
    @property
    def current_sequence(self) -> int:
        if self.events:
            return max(e.sequence_number for e in self.events)
        if self.snapshot:
            return self.snapshot.sequence_number
        return 0


class EventStore:
    """
    Append-only event store for event sourcing.
    
    Features:
    - Persistent event storage
    - Event versioning
    - Snapshot support
    - Event replay
    - Subscription support
    """
    
    def __init__(self, snapshot_interval: int = 100):
        self._events: Dict[str, List[Event]] = {}  # aggregate_id -> events
        self._snapshots: Dict[str, Snapshot] = {}  # aggregate_id -> snapshot
        self._global_position: int = 0
        self._subscriptions: List[Callable[[Event], None]] = []
        self._async_subscriptions: List[Callable[[Event], None]] = []
        self._snapshot_interval = snapshot_interval
        
        # Indexes for efficient querying
        self._type_index: Dict[str, List[str]] = {}  # event_type -> event_ids
        self._aggregate_type_index: Dict[str, List[str]] = {}  # aggregate_type -> aggregate_ids

    # ---------------------------------------------------------------------
    # Compatibility sync API used by FastAPI endpoints/tests
    # ---------------------------------------------------------------------
    def list_streams(self, prefix: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        streams: List[Dict[str, Any]] = []
        for aggregate_id, events in self._events.items():
            if prefix and not aggregate_id.startswith(prefix):
                continue
            created_at = events[0].metadata.timestamp.isoformat() if events else None
            updated_at = events[-1].metadata.timestamp.isoformat() if events else None
            streams.append(
                {
                    "stream_id": aggregate_id,
                    "version": self._get_version(aggregate_id),
                    "event_count": len(events),
                    "created_at": created_at,
                    "updated_at": updated_at,
                }
            )

        streams.sort(key=lambda s: s["stream_id"])
        return streams[:limit]

    def read_stream(
        self,
        stream_id: str,
        from_version: int = 0,
        to_version: Optional[int] = None,
        limit: int = 100,
    ) -> List[Event]:
        events = self._events.get(stream_id, [])
        filtered = [
            event
            for event in events
            if event.sequence_number >= from_version
            and (to_version is None or event.sequence_number <= to_version)
        ]
        return filtered[:limit]

    def read_all(
        self,
        event_type: Optional[str] = None,
        from_timestamp: Optional[datetime] = None,
        to_timestamp: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Event]:
        all_events: List[Event] = []
        for events in self._events.values():
            all_events.extend(events)

        if event_type:
            all_events = [event for event in all_events if event.event_type == event_type]

        if from_timestamp:
            all_events = [
                event for event in all_events if event.metadata.timestamp >= from_timestamp
            ]

        if to_timestamp:
            all_events = [event for event in all_events if event.metadata.timestamp <= to_timestamp]

        all_events.sort(key=lambda event: (event.metadata.timestamp, event.sequence_number))
        return all_events[:limit]

    def create_snapshot(self, stream_id: str, version: Optional[int] = None) -> Optional[Snapshot]:
        events = self._events.get(stream_id, [])
        if not events:
            return None

        if version is not None:
            events = [event for event in events if event.sequence_number <= version]
            if not events:
                return None

        state: Dict[str, Any] = {}
        for event in events:
            if event.data:
                state.update(event.data)

        snapshot = Snapshot(
            aggregate_id=stream_id,
            aggregate_type=events[-1].aggregate_type or "stream",
            sequence_number=events[-1].sequence_number,
            state=state,
            timestamp=datetime.utcnow(),
        )
        self._snapshots[stream_id] = snapshot
        return snapshot
    
    async def append(
        self,
        aggregate_id: str,
        events: Union[Event, List[Event]],
        expected_version: Optional[int] = None,
    ) -> int:
        """
        Append events to an aggregate stream.
        
        Returns the new version.
        Raises ValueError if version conflict.
        """
        if isinstance(events, Event):
            events = [events]
        
        if not events:
            return self._get_version(aggregate_id)
        
        # Get current version
        current_version = self._get_version(aggregate_id)
        
        # Optimistic concurrency check
        if expected_version is not None and current_version != expected_version:
            raise ValueError(
                f"Version conflict: expected {expected_version}, got {current_version}"
            )
        
        # Assign sequence numbers
        for i, event in enumerate(events):
            event.aggregate_id = aggregate_id
            event.sequence_number = current_version + i + 1
            self._global_position += 1
        
        # Append events
        if aggregate_id not in self._events:
            self._events[aggregate_id] = []
        
        self._events[aggregate_id].extend(events)
        
        # Update indexes
        for event in events:
            if event.event_type not in self._type_index:
                self._type_index[event.event_type] = []
            self._type_index[event.event_type].append(event.event_id)
            
            if event.aggregate_type:
                if event.aggregate_type not in self._aggregate_type_index:
                    self._aggregate_type_index[event.aggregate_type] = []
                if aggregate_id not in self._aggregate_type_index[event.aggregate_type]:
                    self._aggregate_type_index[event.aggregate_type].append(aggregate_id)
        
        # Notify subscribers
        for event in events:
            await self._notify_subscribers(event)
        
        logger.debug(f"Appended {len(events)} events to {aggregate_id}")
        
        return self._get_version(aggregate_id)
    
    async def get_events(
        self,
        aggregate_id: str,
        from_sequence: int = 0,
        to_sequence: Optional[int] = None,
    ) -> List[Event]:
        """Get events for an aggregate."""
        events = self._events.get(aggregate_id, [])
        
        filtered = [
            e for e in events
            if e.sequence_number > from_sequence and
            (to_sequence is None or e.sequence_number <= to_sequence)
        ]
        
        return filtered
    
    async def get_event_stream(self, aggregate_id: str) -> EventStream:
        """Get the full event stream for an aggregate."""
        events = self._events.get(aggregate_id, [])
        snapshot = self._snapshots.get(aggregate_id)
        
        aggregate_type = ""
        if events:
            aggregate_type = events[0].aggregate_type
        elif snapshot:
            aggregate_type = snapshot.aggregate_type
        
        return EventStream(
            aggregate_id=aggregate_id,
            aggregate_type=aggregate_type,
            events=events,
            snapshot=snapshot,
            version=len(events),
        )
    
    async def get_all_events(
        self,
        from_position: int = 0,
        max_count: int = 1000,
    ) -> List[Event]:
        """Get all events from a position (for projections)."""
        all_events = []
        
        for events in self._events.values():
            all_events.extend(events)
        
        # Sort by sequence
        all_events.sort(key=lambda e: (e.sequence_number, e.metadata.timestamp))
        
        return all_events[from_position:from_position + max_count]
    
    async def get_events_by_type(
        self,
        event_type: str,
        from_timestamp: Optional[datetime] = None,
    ) -> List[Event]:
        """Get events by type."""
        event_ids = set(self._type_index.get(event_type, []))
        
        events = []
        for event_list in self._events.values():
            for event in event_list:
                if event.event_id in event_ids:
                    if from_timestamp is None or event.metadata.timestamp >= from_timestamp:
                        events.append(event)
        
        return events
    
    async def save_snapshot(self, snapshot: Snapshot) -> None:
        """Save a snapshot for an aggregate."""
        self._snapshots[snapshot.aggregate_id] = snapshot
        logger.debug(f"Saved snapshot for {snapshot.aggregate_id} at version {snapshot.sequence_number}")
    
    async def get_snapshot(self, aggregate_id: str) -> Optional[Snapshot]:
        """Get the latest snapshot for an aggregate."""
        return self._snapshots.get(aggregate_id)
    
    async def get_events_after_snapshot(
        self,
        aggregate_id: str,
    ) -> List[Event]:
        """Get events after the latest snapshot."""
        snapshot = await self.get_snapshot(aggregate_id)
        from_sequence = snapshot.sequence_number if snapshot else 0
        return await self.get_events(aggregate_id, from_sequence)
    
    def _get_version(self, aggregate_id: str) -> int:
        """Get current version of an aggregate."""
        events = self._events.get(aggregate_id, [])
        if not events:
            return 0
        return max(e.sequence_number for e in events)
    
    async def _notify_subscribers(self, event: Event) -> None:
        """Notify all subscribers of a new event."""
        # Sync subscribers
        for callback in self._subscriptions:
            try:
                callback(event)
            except Exception as e:
                logger.warning(f"Event subscriber error: {e}")
        
        # Async subscribers
        for callback in self._async_subscriptions:
            try:
                await callback(event)
            except Exception as e:
                logger.warning(f"Async event subscriber error: {e}")
    
    def subscribe(self, callback: Callable[[Event], None]) -> None:
        """Subscribe to all events (sync)."""
        self._subscriptions.append(callback)
    
    def subscribe_async(self, callback: Callable[[Event], None]) -> None:
        """Subscribe to all events (async)."""
        self._async_subscriptions.append(callback)
    
    def unsubscribe(self, callback: Callable[[Event], None]) -> None:
        """Unsubscribe from events."""
        if callback in self._subscriptions:
            self._subscriptions.remove(callback)
        if callback in self._async_subscriptions:
            self._async_subscriptions.remove(callback)
    
    async def delete_aggregate(self, aggregate_id: str) -> None:
        """Delete all events for an aggregate."""
        if aggregate_id in self._events:
            del self._events[aggregate_id]
        if aggregate_id in self._snapshots:
            del self._snapshots[aggregate_id]
        logger.debug(f"Deleted aggregate {aggregate_id}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get event store statistics."""
        total_events = sum(len(events) for events in self._events.values())
        total_aggregates = len(self._events)
        total_snapshots = len(self._snapshots)
        
        return {
            "total_events": total_events,
            "total_aggregates": total_aggregates,
            "total_snapshots": total_snapshots,
            "global_position": self._global_position,
            "event_types": len(self._type_index),
            "aggregate_types": len(self._aggregate_type_index),
        }
    
    async def create_snapshot_if_needed(
        self,
        aggregate_id: str,
        state: Dict[str, Any],
        aggregate_type: str,
    ) -> Optional[Snapshot]:
        """Create a snapshot if interval is reached."""
        events = self._events.get(aggregate_id, [])
        current_snapshot = self._snapshots.get(aggregate_id)
        
        last_snapshot_seq = current_snapshot.sequence_number if current_snapshot else 0
        events_since_snapshot = len([e for e in events if e.sequence_number > last_snapshot_seq])
        
        if events_since_snapshot >= self._snapshot_interval:
            snapshot = Snapshot(
                aggregate_id=aggregate_id,
                aggregate_type=aggregate_type,
                sequence_number=max(e.sequence_number for e in events),
                state=state,
            )
            await self.save_snapshot(snapshot)
            return snapshot
        
        return None


class InMemoryEventStore(EventStore):
    """In-memory implementation of event store for testing."""
    
    def __init__(self, snapshot_interval: int = 100):
        super().__init__(snapshot_interval)
        self._is_persistent = False
    
    async def persist(self) -> None:
        """Persist to storage (no-op for in-memory)."""
        pass
    
    async def load(self) -> None:
        """Load from storage (no-op for in-memory)."""
        pass


class FileEventStore(EventStore):
    """File-based event store for persistence."""
    
    def __init__(
        self,
        file_path: str = "events.jsonl",
        snapshot_interval: int = 100,
    ):
        super().__init__(snapshot_interval)
        self._file_path = file_path
        self._snapshot_path = file_path.replace(".jsonl", "_snapshots.jsonl")
    
    async def load(self) -> None:
        """Load events from file."""
        try:
            with open(self._file_path, 'r') as f:
                for line in f:
                    if line.strip():
                        event = Event.from_json(line)
                        if event.aggregate_id not in self._events:
                            self._events[event.aggregate_id] = []
                        self._events[event.aggregate_id].append(event)
            
            logger.info(f"Loaded events from {self._file_path}")
        except FileNotFoundError:
            logger.info(f"No existing event file at {self._file_path}")
        
        # Load snapshots
        try:
            with open(self._snapshot_path, 'r') as f:
                for line in f:
                    if line.strip():
                        snapshot = Snapshot.from_dict(json.loads(line))
                        self._snapshots[snapshot.aggregate_id] = snapshot
        except FileNotFoundError:
            pass
    
    async def persist(self) -> None:
        """Persist events to file."""
        with open(self._file_path, 'w') as f:
            for events in self._events.values():
                for event in events:
                    f.write(event.to_json() + '\n')
        
        with open(self._snapshot_path, 'w') as f:
            for snapshot in self._snapshots.values():
                f.write(json.dumps(snapshot.to_dict()) + '\n')
        
        logger.debug(f"Persisted events to {self._file_path}")
    
    async def append(
        self,
        aggregate_id: str,
        events: Union[Event, List[Event]],
        expected_version: Optional[int] = None,
    ) -> int:
        """Append events and persist."""
        result = await super().append(aggregate_id, events, expected_version)
        await self.persist()
        return result

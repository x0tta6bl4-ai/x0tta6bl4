"""
Aggregate - Domain-driven design aggregate implementation.

Provides aggregate root, entity, and repository patterns for
event-sourced domain models.
"""

import logging
import uuid
from abc import ABC
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, Generic, List, Optional, Type, TypeVar

from .event_store import Event, EventStore, Snapshot

logger = logging.getLogger(__name__)

TAggregate = TypeVar('TAggregate', bound='Aggregate')


@dataclass
class AggregateState:
    """Base state for aggregates."""
    version: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    is_deleted: bool = False


class Aggregate(ABC):
    """
    Base class for event-sourced aggregates.
    
    Aggregates are clusters of domain objects that can be treated
    as a single unit. They are the primary building blocks of
    domain-driven design.
    """
    
    def __init__(self, aggregate_id: str = ""):
        self._id = aggregate_id or str(uuid.uuid4())
        self._version = 0
        self._uncommitted_events: List[Event] = []
        self._state = AggregateState()
        self._event_handlers: Dict[str, Callable] = {}
        
        # Register event handlers from decorated methods
        self._register_event_handlers()
    
    @property
    def id(self) -> str:
        """Aggregate ID."""
        return self._id
    
    @property
    def version(self) -> int:
        """Current version of the aggregate."""
        return self._version
    
    @property
    def state(self) -> AggregateState:
        """Current state of the aggregate."""
        return self._state
    
    @property
    def uncommitted_events(self) -> List[Event]:
        """Events that have not been persisted."""
        return self._uncommitted_events.copy()
    
    @property
    def has_uncommitted_events(self) -> bool:
        """Check if there are uncommitted events."""
        return len(self._uncommitted_events) > 0
    
    @property
    def is_deleted(self) -> bool:
        """Check if aggregate is deleted."""
        return self._state.is_deleted
    
    def _register_event_handlers(self) -> None:
        """Register event handlers from decorated methods."""
        for attr_name in dir(self):
            attr = getattr(self, attr_name)
            if hasattr(attr, '_event_type'):
                event_type = attr._event_type
                self._event_handlers[event_type] = attr
    
    def apply_event(self, event: Event) -> None:
        """Apply an event to update state."""
        handler = self._event_handlers.get(event.event_type)
        if handler:
            handler(event)
        
        self._version = event.sequence_number
        self._state.version = self._version
        self._state.updated_at = datetime.utcnow()
    
    def raise_event(
        self,
        event_type: str,
        data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Event:
        """Create and apply a new event."""
        event = Event(
            event_type=event_type,
            aggregate_id=self._id,
            aggregate_type=self.__class__.__name__,
            sequence_number=self._version + 1,
            data=data,
        )
        
        if metadata:
            event.metadata.custom = metadata
        
        self.apply_event(event)
        self._uncommitted_events.append(event)
        
        return event
    
    def mark_events_committed(self) -> None:
        """Mark all events as committed."""
        self._uncommitted_events.clear()
    
    def load_from_history(self, events: List[Event]) -> None:
        """Load aggregate state from event history."""
        for event in events:
            self.apply_event(event)
    
    def load_from_snapshot(self, snapshot: Snapshot) -> None:
        """Load aggregate state from snapshot."""
        self._id = snapshot.aggregate_id
        self._version = snapshot.sequence_number
        self._state.version = snapshot.sequence_number
        self._restore_state(snapshot.state)
    
    def _restore_state(self, state: Dict[str, Any]) -> None:
        """Restore state from snapshot data. Override in subclasses."""
        if "is_deleted" in state:
            self._state.is_deleted = state["is_deleted"]
    
    def get_snapshot_state(self) -> Dict[str, Any]:
        """Get state for snapshot. Override in subclasses."""
        return {
            "is_deleted": self._state.is_deleted,
            "version": self._version,
        }
    
    def delete(self, reason: Optional[str] = None) -> None:
        """Mark aggregate as deleted."""
        self.raise_event(
            "AggregateDeleted",
            {"reason": reason}
        )
        self._state.is_deleted = True


def event_handler(event_type: str):
    """Decorator to mark a method as an event handler."""
    def decorator(method):
        method._event_type = event_type
        return method
    return decorator


class AggregateRoot(Aggregate):
    """
    Base class for aggregate roots.
    
    Aggregate roots are the only entry point to the aggregate.
    They enforce invariants and encapsulate all changes.
    """
    
    def __init__(self, aggregate_id: str = ""):
        super().__init__(aggregate_id)
        self._child_entities: Dict[str, Any] = {}
    
    def add_child(self, entity_id: str, entity: Any) -> None:
        """Add a child entity."""
        self._child_entities[entity_id] = entity
    
    def remove_child(self, entity_id: str) -> None:
        """Remove a child entity."""
        self._child_entities.pop(entity_id, None)
    
    def get_child(self, entity_id: str) -> Optional[Any]:
        """Get a child entity."""
        return self._child_entities.get(entity_id)
    
    def get_children(self) -> Dict[str, Any]:
        """Get all child entities."""
        return self._child_entities.copy()


class Repository(Generic[TAggregate]):
    """
    Repository for aggregate persistence.
    
    Provides CRUD operations for aggregates using event sourcing.
    """
    
    def __init__(
        self,
        event_store: EventStore,
        aggregate_type: Type[TAggregate],
    ):
        self._event_store = event_store
        self._aggregate_type = aggregate_type
    
    async def get_by_id(
        self,
        aggregate_id: str,
        use_snapshot: bool = True,
    ) -> Optional[TAggregate]:
        """Get an aggregate by ID."""
        # Try to load from snapshot first
        snapshot = None
        if use_snapshot:
            snapshot = await self._event_store.get_snapshot(aggregate_id)
        
        # Create aggregate instance
        aggregate = self._aggregate_type(aggregate_id)
        
        # Load from snapshot if available
        if snapshot:
            aggregate.load_from_snapshot(snapshot)
        
        # Get events after snapshot
        events = await self._event_store.get_events(
            aggregate_id,
            from_sequence=aggregate.version
        )
        
        if not events and not snapshot:
            return None
        
        # Apply events
        aggregate.load_from_history(events)
        
        return aggregate
    
    async def save(
        self,
        aggregate: TAggregate,
        expected_version: Optional[int] = None,
    ) -> int:
        """Save an aggregate."""
        if not aggregate.has_uncommitted_events:
            return aggregate.version
        
        # Append events
        new_version = await self._event_store.append(
            aggregate.id,
            aggregate.uncommitted_events,
            expected_version,
        )
        
        # Mark events as committed
        aggregate.mark_events_committed()
        
        # Create snapshot if needed
        await self._event_store.create_snapshot_if_needed(
            aggregate.id,
            aggregate.get_snapshot_state(),
            aggregate.__class__.__name__,
        )
        
        return new_version
    
    async def delete(self, aggregate_id: str) -> None:
        """Delete an aggregate."""
        await self._event_store.delete_aggregate(aggregate_id)
    
    async def exists(self, aggregate_id: str) -> bool:
        """Check if an aggregate exists."""
        events = await self._event_store.get_events(aggregate_id)
        return len(events) > 0


class InMemoryRepository(Repository[TAggregate]):
    """In-memory repository for testing."""
    
    def __init__(self, aggregate_type: Type[TAggregate]):
        from .event_store import InMemoryEventStore
        super().__init__(InMemoryEventStore(), aggregate_type)
        self._aggregates: Dict[str, TAggregate] = {}
    
    async def get_by_id(
        self,
        aggregate_id: str,
        use_snapshot: bool = True,
    ) -> Optional[TAggregate]:
        """Get from memory cache or event store."""
        if aggregate_id in self._aggregates:
            return self._aggregates[aggregate_id]
        
        aggregate = await super().get_by_id(aggregate_id, use_snapshot)
        if aggregate:
            self._aggregates[aggregate_id] = aggregate
        
        return aggregate
    
    async def save(
        self,
        aggregate: TAggregate,
        expected_version: Optional[int] = None,
    ) -> int:
        """Save to memory cache and event store."""
        version = await super().save(aggregate, expected_version)
        self._aggregates[aggregate.id] = aggregate
        return version
    
    async def delete(self, aggregate_id: str) -> None:
        """Delete from memory cache and event store."""
        self._aggregates.pop(aggregate_id, None)
        await super().delete(aggregate_id)


# Example aggregate implementation
class UserAggregate(AggregateRoot):
    """Example user aggregate."""
    
    def __init__(
        self,
        user_id: str = "",
        email: str = "",
        name: str = "",
    ):
        super().__init__(user_id)
        self._email = email
        self._name = name
        self._is_active = True
    
    @property
    def email(self) -> str:
        return self._email
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def is_active(self) -> bool:
        return self._is_active
    
    @classmethod
    def create(cls, user_id: str, email: str, name: str) -> "UserAggregate":
        """Factory method to create a new user."""
        user = cls(user_id)
        user.raise_event(
            "UserCreated",
            {"email": email, "name": name}
        )
        return user
    
    def update_email(self, new_email: str) -> None:
        """Update user email."""
        if self._is_active:
            self.raise_event(
                "UserEmailUpdated",
                {"old_email": self._email, "new_email": new_email}
            )
    
    def update_name(self, new_name: str) -> None:
        """Update user name."""
        if self._is_active:
            self.raise_event(
                "UserNameUpdated",
                {"old_name": self._name, "new_name": new_name}
            )
    
    def deactivate(self) -> None:
        """Deactivate user."""
        if self._is_active:
            self.raise_event("UserDeactivated", {})
    
    def activate(self) -> None:
        """Activate user."""
        if not self._is_active:
            self.raise_event("UserActivated", {})
    
    @event_handler("UserCreated")
    def _on_user_created(self, event: Event) -> None:
        self._email = event.data["email"]
        self._name = event.data["name"]
        self._is_active = True
    
    @event_handler("UserEmailUpdated")
    def _on_email_updated(self, event: Event) -> None:
        self._email = event.data["new_email"]
    
    @event_handler("UserNameUpdated")
    def _on_name_updated(self, event: Event) -> None:
        self._name = event.data["new_name"]
    
    @event_handler("UserDeactivated")
    def _on_deactivated(self, event: Event) -> None:
        self._is_active = False
    
    @event_handler("UserActivated")
    def _on_activated(self, event: Event) -> None:
        self._is_active = True
    
    @event_handler("AggregateDeleted")
    def _on_deleted(self, event: Event) -> None:
        self._is_active = False
        self._state.is_deleted = True
    
    def get_snapshot_state(self) -> Dict[str, Any]:
        return {
            **super().get_snapshot_state(),
            "email": self._email,
            "name": self._name,
            "is_active": self._is_active,
        }
    
    def _restore_state(self, state: Dict[str, Any]) -> None:
        super()._restore_state(state)
        self._email = state.get("email", "")
        self._name = state.get("name", "")
        self._is_active = state.get("is_active", True)

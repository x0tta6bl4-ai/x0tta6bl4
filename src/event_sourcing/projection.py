"""
Projection - Read model projections for CQRS.

Provides projection infrastructure for building read models
from event streams.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Type

from .event_store import Event, EventStore

logger = logging.getLogger(__name__)


@dataclass
class ProjectionState:
    """State of a projection."""
    projection_name: str
    last_processed_position: int = 0
    last_processed_timestamp: Optional[datetime] = None
    is_running: bool = False
    events_processed: int = 0
    errors: int = 0
    last_error: Optional[str] = None


class ProjectionStatus(Enum):
    """Projection runtime status."""

    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


class Projection(ABC):
    """
    Abstract base class for projections.
    
    Projections build read models from event streams.
    They are eventually consistent and can be rebuilt from history.
    """
    
    def __init__(self, name: str, event_store: EventStore):
        self.name = name
        self._event_store = event_store
        self._state = ProjectionState(projection_name=name)
        self._handlers: Dict[str, Callable] = {}
        self._running = False
        self._paused = False
        self._subscribed = False
        self._started_at: Optional[datetime] = None
        
        # Register handlers from decorated methods
        self._register_handlers()
    
    @property
    def state(self) -> ProjectionState:
        return self._state

    @property
    def status(self) -> ProjectionStatus:
        if self._state.last_error:
            return ProjectionStatus.ERROR
        if self._paused:
            return ProjectionStatus.PAUSED
        if self._running:
            return ProjectionStatus.RUNNING
        return ProjectionStatus.STOPPED

    @property
    def position(self) -> int:
        return self._state.last_processed_position

    @property
    def events_processed(self) -> int:
        return self._state.events_processed

    @property
    def last_event_timestamp(self) -> Optional[datetime]:
        return self._state.last_processed_timestamp

    @property
    def started_at(self) -> Optional[datetime]:
        return self._started_at
    
    def _register_handlers(self) -> None:
        """Register event handlers from decorated methods."""
        for attr_name in dir(self):
            attr = getattr(self, attr_name)
            if hasattr(attr, '_handles_event'):
                event_type = attr._handles_event
                self._handlers[event_type] = attr
    
    @staticmethod
    def handles(event_type: str):
        """Decorator to mark a method as handling an event type."""
        def decorator(method):
            method._handles_event = event_type
            return method
        return decorator
    
    async def process_event(self, event: Event) -> bool:
        """Process a single event."""
        handler = self._handlers.get(event.event_type)
        
        if handler:
            try:
                await handler(event) if asyncio.iscoroutinefunction(handler) else handler(event)
                self._state.events_processed += 1
                self._state.last_processed_timestamp = datetime.utcnow()
                return True
            except Exception as e:
                self._state.errors += 1
                self._state.last_error = str(e)
                logger.error(f"Projection {self.name} error processing {event.event_type}: {e}")
                return False
        else:
            # No handler for this event type
            return True
    
    async def catch_up(self, from_position: int = 0) -> int:
        """
        Catch up projection from a position.
        
        Returns number of events processed.
        """
        events = await self._event_store.get_all_events(from_position)
        processed = 0
        
        for event in events:
            success = await self.process_event(event)
            if success:
                processed += 1
                self._state.last_processed_position = event.sequence_number
        
        return processed
    
    async def start(self) -> None:
        """Start the projection."""
        self._running = True
        self._paused = False
        self._state.is_running = True
        self._started_at = self._started_at or datetime.utcnow()
        
        # Subscribe to new events
        self._event_store.subscribe_async(self._on_new_event)
        self._subscribed = True
        
        logger.info(f"Projection {self.name} started")
    
    async def stop(self) -> None:
        """Stop the projection."""
        self._running = False
        self._paused = False
        self._state.is_running = False
        
        if self._subscribed:
            self._event_store.unsubscribe(self._on_new_event)
            self._subscribed = False
        
        logger.info(f"Projection {self.name} stopped")
    
    async def _on_new_event(self, event: Event) -> None:
        """Handle new event from subscription."""
        if self._running and not self._paused:
            await self.process_event(event)

    def pause(self) -> None:
        """Pause projection event processing without unsubscribing."""
        self._paused = True
        self._state.is_running = False

    def resume(self) -> None:
        """Resume projection event processing."""
        self._paused = False
        if self._subscribed:
            self._running = True
            self._state.is_running = True
    
    async def reset(self) -> None:
        """Reset projection state."""
        self._state = ProjectionState(projection_name=self.name)
        await self.on_reset()
        logger.info(f"Projection {self.name} reset")
    
    @abstractmethod
    async def on_reset(self) -> None:
        """Called when projection is reset. Override to clear read model."""
        pass
    
    def get_state_dict(self) -> Dict[str, Any]:
        """Get projection state as dictionary."""
        return {
            "name": self.name,
            "last_processed_position": self._state.last_processed_position,
            "last_processed_timestamp": (
                self._state.last_processed_timestamp.isoformat()
                if self._state.last_processed_timestamp else None
            ),
            "is_running": self._state.is_running,
            "events_processed": self._state.events_processed,
            "errors": self._state.errors,
            "last_error": self._state.last_error,
        }


class InMemoryProjection(Projection):
    """Simple in-memory projection for testing."""
    
    def __init__(self, name: str, event_store: EventStore):
        super().__init__(name, event_store)
        self._data: Dict[str, Any] = {}
    
    @property
    def data(self) -> Dict[str, Any]:
        return self._data
    
    async def on_reset(self) -> None:
        self._data.clear()


class ProjectionManager:
    """
    Manager for multiple projections.
    
    Features:
    - Projection lifecycle management
    - Coordinated catch-up
    - Health monitoring
    """
    
    def __init__(self, event_store: Optional[EventStore] = None):
        self._event_store = event_store or EventStore()
        self._projections: Dict[str, Projection] = {}
        self._running = False

    @staticmethod
    def _schedule_or_run(coro: Any) -> None:
        """Run coroutine now (sync context) or schedule it (async context)."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(coro)
        except RuntimeError:
            asyncio.run(coro)
    
    def register(self, projection: Projection) -> None:
        """Register a projection."""
        self._projections[projection.name] = projection
        logger.info(f"Registered projection: {projection.name}")
    
    def unregister(self, name: str) -> None:
        """Unregister a projection."""
        projection = self._projections.pop(name, None)
        if projection and projection.state.is_running:
            asyncio.create_task(projection.stop())
    
    def get_projection(self, name: str) -> Optional[Projection]:
        """Get a projection by name."""
        return self._projections.get(name)
    
    def get_all_projections(self) -> List[Projection]:
        """Get all registered projections."""
        return list(self._projections.values())

    def list_projections(self) -> List[Projection]:
        """Compatibility alias for API/tests."""
        return self.get_all_projections()
    
    async def start_all(self) -> None:
        """Start all projections."""
        self._running = True
        
        for projection in self._projections.values():
            await projection.start()
        
        logger.info(f"Started {len(self._projections)} projections")
    
    async def stop_all(self) -> None:
        """Stop all projections."""
        self._running = False
        
        for projection in self._projections.values():
            await projection.stop()
        
        logger.info("Stopped all projections")
    
    async def catch_up_all(self, from_position: int = 0) -> Dict[str, int]:
        """Catch up all projections."""
        results = {}
        
        for name, projection in self._projections.items():
            processed = await projection.catch_up(from_position)
            results[name] = processed
        
        return results
    
    async def reset_all(self) -> None:
        """Reset all projections."""
        for projection in self._projections.values():
            await projection.reset()
        
        logger.info("Reset all projections")
    
    async def rebuild_projection(self, name: str) -> int:
        """Rebuild a specific projection from scratch."""
        projection = self._projections.get(name)
        if not projection:
            raise ValueError(f"Projection not found: {name}")
        
        was_running = projection.state.is_running
        if was_running:
            await projection.stop()
        
        await projection.reset()
        processed = await projection.catch_up()
        
        if was_running:
            await projection.start()
        
        logger.info(f"Rebuilt projection {name}, processed {processed} events")
        return processed

    def get_projection_status(self, name: str) -> Optional[Dict[str, Any]]:
        """Return projection status dictionary for API consumers."""
        projection = self._projections.get(name)
        if not projection:
            return None

        return {
            "name": projection.name,
            "status": projection.status.value,
            "position": projection.position,
            "events_processed": projection.events_processed,
            "last_event_timestamp": projection.last_event_timestamp,
            "lag": 0,
            "error": projection.state.last_error,
            "started_at": projection.started_at,
        }

    def reset_projection(self, name: str) -> None:
        """Reset projection asynchronously."""
        projection = self._projections.get(name)
        if not projection:
            raise ValueError(f"Projection not found: {name}")
        self._schedule_or_run(projection.reset())

    def pause_projection(self, name: str) -> None:
        """Pause projection processing."""
        projection = self._projections.get(name)
        if not projection:
            raise ValueError(f"Projection not found: {name}")
        projection.pause()

    def resume_projection(self, name: str) -> None:
        """Resume projection processing."""
        projection = self._projections.get(name)
        if not projection:
            raise ValueError(f"Projection not found: {name}")
        projection.resume()
    
    def get_status(self) -> Dict[str, Any]:
        """Get status of all projections."""
        return {
            "total_projections": len(self._projections),
            "running_projections": sum(
                1 for p in self._projections.values()
                if p.state.is_running
            ),
            "projections": {
                name: projection.get_state_dict()
                for name, projection in self._projections.items()
            },
        }
    
    def get_lagging_projections(self, max_lag: int = 100) -> List[str]:
        """Get projections that are lagging behind."""
        if not self._projections:
            return []
        
        max_position = max(
            p.state.last_processed_position
            for p in self._projections.values()
        )
        
        return [
            name for name, projection in self._projections.items()
            if max_position - projection.state.last_processed_position > max_lag
        ]


# Example projections
class UserSummaryProjection(InMemoryProjection):
    """Example projection for user summaries."""
    
    def __init__(self, event_store: EventStore):
        super().__init__("user_summary", event_store)
        self._user_count = 0
        self._active_users: Set[str] = set()
    
    @property
    def user_count(self) -> int:
        return self._user_count
    
    @property
    def active_users(self) -> Set[str]:
        return self._active_users
    
    @Projection.handles("UserCreated")
    def on_user_created(self, event: Event) -> None:
        user_id = event.aggregate_id
        self._data[user_id] = {
            "email": event.data.get("email"),
            "name": event.data.get("name"),
            "is_active": True,
            "created_at": event.metadata.timestamp.isoformat(),
        }
        self._user_count += 1
        self._active_users.add(user_id)
    
    @Projection.handles("UserDeactivated")
    def on_user_deactivated(self, event: Event) -> None:
        user_id = event.aggregate_id
        if user_id in self._data:
            self._data[user_id]["is_active"] = False
            self._active_users.discard(user_id)
    
    @Projection.handles("UserActivated")
    def on_user_activated(self, event: Event) -> None:
        user_id = event.aggregate_id
        if user_id in self._data:
            self._data[user_id]["is_active"] = True
            self._active_users.add(user_id)
    
    @Projection.handles("UserEmailUpdated")
    def on_email_updated(self, event: Event) -> None:
        user_id = event.aggregate_id
        if user_id in self._data:
            self._data[user_id]["email"] = event.data.get("new_email")
    
    @Projection.handles("UserNameUpdated")
    def on_name_updated(self, event: Event) -> None:
        user_id = event.aggregate_id
        if user_id in self._data:
            self._data[user_id]["name"] = event.data.get("new_name")
    
    async def on_reset(self) -> None:
        await super().on_reset()
        self._user_count = 0
        self._active_users.clear()


class EventStatisticsProjection(InMemoryProjection):
    """Projection for event statistics."""
    
    def __init__(self, event_store: EventStore):
        super().__init__("event_statistics", event_store)
        self._event_counts: Dict[str, int] = {}
        self._aggregate_counts: Dict[str, int] = {}
        self._hourly_counts: Dict[str, int] = {}
    
    @property
    def event_counts(self) -> Dict[str, int]:
        return self._event_counts
    
    @property
    def aggregate_counts(self) -> Dict[str, int]:
        return self._aggregate_counts
    
    def _process_any_event(self, event: Event) -> None:
        # Count by event type
        self._event_counts[event.event_type] = (
            self._event_counts.get(event.event_type, 0) + 1
        )
        
        # Count by aggregate type
        if event.aggregate_type:
            self._aggregate_counts[event.aggregate_type] = (
                self._aggregate_counts.get(event.aggregate_type, 0) + 1
            )
        
        # Count by hour
        hour_key = event.metadata.timestamp.strftime("%Y-%m-%d %H:00")
        self._hourly_counts[hour_key] = self._hourly_counts.get(hour_key, 0) + 1
    
    async def process_event(self, event: Event) -> bool:
        self._process_any_event(event)
        return await super().process_event(event)
    
    async def on_reset(self) -> None:
        await super().on_reset()
        self._event_counts.clear()
        self._aggregate_counts.clear()
        self._hourly_counts.clear()
    
    def get_summary(self) -> Dict[str, Any]:
        return {
            "total_events": sum(self._event_counts.values()),
            "event_types": len(self._event_counts),
            "aggregate_types": len(self._aggregate_counts),
            "top_event_types": sorted(
                self._event_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10],
            "top_aggregate_types": sorted(
                self._aggregate_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10],
        }

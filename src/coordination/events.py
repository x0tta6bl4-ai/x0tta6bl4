"""
Event Bus for Agent Communication

Provides a publish-subscribe event system for inter-agent communication.
"""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set
import logging
from collections import defaultdict
import uuid

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Types of coordination events."""
    # Agent lifecycle
    AGENT_REGISTERED = "agent.registered"
    AGENT_UNREGISTERED = "agent.unregistered"
    AGENT_HEARTBEAT = "agent.heartbeat"
    AGENT_STATUS_CHANGED = "agent.status_changed"
    
    # Task events
    TASK_CREATED = "task.created"
    TASK_ASSIGNED = "task.assigned"
    TASK_STARTED = "task.started"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    TASK_BLOCKED = "task.blocked"
    
    # Lock events
    LOCK_ACQUIRED = "lock.acquired"
    LOCK_RELEASED = "lock.released"
    LOCK_EXPIRED = "lock.expired"
    LOCK_CONFLICT = "lock.conflict"
    
    # File events
    FILE_MODIFIED = "file.modified"
    FILE_CREATED = "file.created"
    FILE_DELETED = "file.deleted"
    
    # Pipeline events
    PIPELINE_STAGE_START = "pipeline.stage_start"
    PIPELINE_STAGE_END = "pipeline.stage_end"
    PIPELINE_HANDOFF = "pipeline.handoff"
    
    # Conflict events
    CONFLICT_DETECTED = "conflict.detected"
    CONFLICT_RESOLVED = "conflict.resolved"
    
    # System events
    SYSTEM_ALERT = "system.alert"
    SYSTEM_SHUTDOWN = "system.shutdown"
    COORDINATION_REQUEST = "coordination.request"


@dataclass
class Event:
    """A coordination event."""
    event_type: EventType
    source_agent: str
    data: Dict[str, Any]
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    target_agents: Optional[Set[str]] = None  # None = broadcast
    priority: int = 0  # Higher = more important
    requires_ack: bool = False
    acked_by: Set[str] = field(default_factory=set)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "source_agent": self.source_agent,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "target_agents": list(self.target_agents) if self.target_agents else None,
            "priority": self.priority,
            "requires_ack": self.requires_ack,
            "acked_by": list(self.acked_by),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event":
        """Create from dictionary."""
        return cls(
            event_id=data["event_id"],
            event_type=EventType(data["event_type"]),
            source_agent=data["source_agent"],
            data=data["data"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            target_agents=set(data["target_agents"]) if data.get("target_agents") else None,
            priority=data.get("priority", 0),
            requires_ack=data.get("requires_ack", False),
            acked_by=set(data.get("acked_by", [])),
        )
    
    def ack(self, agent_id: str) -> None:
        """Acknowledge the event."""
        self.acked_by.add(agent_id)
    
    def is_fully_acked(self, expected_agents: Set[str]) -> bool:
        """Check if all expected agents have acknowledged."""
        return expected_agents.issubset(self.acked_by)


# Type alias for event handlers
EventHandler = Callable[[Event], None]
AsyncEventHandler = Callable[[Event], Any]  # Can be coroutine


class EventBus:
    """
    Publish-subscribe event bus for agent communication.
    
    Features:
    - Synchronous and asynchronous handlers
    - Event persistence for replay
    - Targeted and broadcast events
    - Event acknowledgment tracking
    """
    
    EVENT_LOG = ".agent_coordination/events.log"
    MAX_EVENT_HISTORY = 1000
    
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.event_log_path = self.project_root / self.EVENT_LOG
        
        # Ensure directory exists
        self.event_log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Subscribers: event_type -> list of handlers
        self._sync_subscribers: Dict[EventType, List[EventHandler]] = defaultdict(list)
        self._async_subscribers: Dict[EventType, List[AsyncEventHandler]] = defaultdict(list)
        
        # Event history for replay
        self._event_history: List[Event] = []
        
        # Pending events waiting for ack
        self._pending_acks: Dict[str, Event] = {}
        
        # Load event history
        self._load_event_history()
    
    def _load_event_history(self) -> None:
        """Load event history from disk."""
        if self.event_log_path.exists():
            try:
                with open(self.event_log_path, "r") as f:
                    for line in f:
                        if line.strip():
                            data = json.loads(line)
                            event = Event.from_dict(data)
                            self._event_history.append(event)
                
                # Trim to max size
                if len(self._event_history) > self.MAX_EVENT_HISTORY:
                    self._event_history = self._event_history[-self.MAX_EVENT_HISTORY:]
                
                logger.info(f"Loaded {len(self._event_history)} events from history")
            except Exception as e:
                logger.error(f"Failed to load event history: {e}")
    
    def _append_event(self, event: Event) -> None:
        """Append event to log file."""
        try:
            with open(self.event_log_path, "a") as f:
                f.write(json.dumps(event.to_dict()) + "\n")
        except Exception as e:
            logger.error(f"Failed to append event: {e}")
    
    def subscribe(
        self,
        event_type: EventType,
        handler: EventHandler,
        is_async: bool = False
    ) -> None:
        """Subscribe to an event type."""
        if is_async:
            self._async_subscribers[event_type].append(handler)
        else:
            self._sync_subscribers[event_type].append(handler)
        logger.debug(f"Subscribed to {event_type.value}")
    
    def unsubscribe(
        self,
        event_type: EventType,
        handler: EventHandler,
        is_async: bool = False
    ) -> None:
        """Unsubscribe from an event type."""
        if is_async:
            if handler in self._async_subscribers[event_type]:
                self._async_subscribers[event_type].remove(handler)
        else:
            if handler in self._sync_subscribers[event_type]:
                self._sync_subscribers[event_type].remove(handler)
    
    def publish(
        self,
        event_type: EventType,
        source_agent: str,
        data: Dict[str, Any],
        target_agents: Optional[Set[str]] = None,
        priority: int = 0,
        requires_ack: bool = False
    ) -> Event:
        """Publish an event."""
        event = Event(
            event_type=event_type,
            source_agent=source_agent,
            data=data,
            target_agents=target_agents,
            priority=priority,
            requires_ack=requires_ack,
        )
        
        # Add to history
        self._event_history.append(event)
        if len(self._event_history) > self.MAX_EVENT_HISTORY:
            self._event_history = self._event_history[-self.MAX_EVENT_HISTORY:]
        
        # Persist
        self._append_event(event)
        
        # Track if ack required
        if requires_ack and target_agents:
            self._pending_acks[event.event_id] = event
        
        # Deliver to sync subscribers
        for handler in self._sync_subscribers[event_type]:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Error in event handler: {e}")
        
        # Deliver to async subscribers (if in async context)
        for handler in self._async_subscribers[event_type]:
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    # Schedule for execution
                    asyncio.create_task(result)
            except Exception as e:
                logger.error(f"Error in async event handler: {e}")
        
        logger.debug(f"Published {event_type.value} from {source_agent}")
        return event
    
    def ack_event(self, event_id: str, agent_id: str) -> bool:
        """Acknowledge an event."""
        if event_id in self._pending_acks:
            self._pending_acks[event_id].ack(agent_id)
            return True
        return False
    
    def get_pending_acks(self, agent_id: str) -> List[Event]:
        """Get events pending acknowledgment from an agent."""
        return [
            event for event in self._pending_acks.values()
            if event.target_agents and agent_id in event.target_agents and agent_id not in event.acked_by
        ]
    
    def get_event_history(
        self,
        event_type: Optional[EventType] = None,
        source_agent: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Event]:
        """Get filtered event history."""
        events = self._event_history
        
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        
        if source_agent:
            events = [e for e in events if e.source_agent == source_agent]
        
        if since:
            events = [e for e in events if e.timestamp >= since]
        
        return events[-limit:]
    
    def replay_events(
        self,
        agent_id: str,
        since: Optional[datetime] = None
    ) -> List[Event]:
        """Replay events for an agent that may have missed them."""
        events = self._event_history
        
        if since:
            events = [e for e in events if e.timestamp >= since]
        
        # Filter to events relevant to this agent
        relevant = []
        for event in events:
            if event.target_agents is None:  # Broadcast
                relevant.append(event)
            elif agent_id in event.target_agents:
                relevant.append(event)
        
        return relevant


# Convenience functions for common events
def emit_task_created(
    bus: EventBus,
    source_agent: str,
    task_id: str,
    task_type: str,
    target_files: List[str],
    assigned_to: Optional[str] = None
) -> Event:
    """Emit a task created event."""
    return bus.publish(
        EventType.TASK_CREATED,
        source_agent,
        {
            "task_id": task_id,
            "task_type": task_type,
            "target_files": target_files,
            "assigned_to": assigned_to,
        },
        target_agents={assigned_to} if assigned_to else None,
    )


def emit_lock_acquired(
    bus: EventBus,
    source_agent: str,
    path: str,
    lock_type: str = "exclusive"
) -> Event:
    """Emit a lock acquired event."""
    return bus.publish(
        EventType.LOCK_ACQUIRED,
        source_agent,
        {
            "path": path,
            "lock_type": lock_type,
        }
    )


def emit_pipeline_handoff(
    bus: EventBus,
    source_agent: str,
    target_agent: str,
    stage: str,
    artifacts: List[str]
) -> Event:
    """Emit a pipeline handoff event."""
    return bus.publish(
        EventType.PIPELINE_HANDOFF,
        source_agent,
        {
            "stage": stage,
            "artifacts": artifacts,
        },
        target_agents={target_agent},
        requires_ack=True,
    )


def emit_conflict_detected(
    bus: EventBus,
    source_agent: str,
    conflict_type: str,
    path: str,
    conflicting_agents: List[str]
) -> Event:
    """Emit a conflict detected event."""
    return bus.publish(
        EventType.CONFLICT_DETECTED,
        source_agent,
        {
            "conflict_type": conflict_type,
            "path": path,
            "conflicting_agents": conflicting_agents,
        },
        target_agents=set(conflicting_agents),
        priority=10,  # High priority
        requires_ack=True,
    )


# Singleton instance
_event_bus: Optional[EventBus] = None


def get_event_bus(project_root: str = ".") -> EventBus:
    """Get or create the event bus singleton."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus(project_root)
    return _event_bus

"""
Event Sourcing & CQRS Module - Event-driven architecture for MaaS.

Provides event sourcing, CQRS pattern implementation, and event store
for building scalable, event-driven distributed systems.
"""

from .event_store import EventStore, Event, EventVersion
from .command_bus import CommandBus, Command, CommandHandler
from .query_bus import QueryBus, Query, QueryHandler
from .aggregate import Aggregate, AggregateRoot, Repository
from .projection import Projection, ProjectionManager, ProjectionStatus

__all__ = [
    "EventStore",
    "Event",
    "EventVersion",
    "CommandBus",
    "Command",
    "CommandHandler",
    "QueryBus",
    "Query",
    "QueryHandler",
    "Aggregate",
    "AggregateRoot",
    "Repository",
    "Projection",
    "ProjectionManager",
    "ProjectionStatus",
]

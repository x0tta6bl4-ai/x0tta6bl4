"""
Database Backends for Event Store.

Provides persistent storage backends for event sourcing:
- PostgreSQL: ACID-compliant relational storage
- MongoDB: Document-based storage for flexibility
"""

from src.event_sourcing.backends.base import DatabaseBackend
from src.event_sourcing.backends.postgres import PostgresEventStore
from src.event_sourcing.backends.mongodb import MongoDBEventStore

__all__ = [
    "DatabaseBackend",
    "PostgresEventStore",
    "MongoDBEventStore",
]

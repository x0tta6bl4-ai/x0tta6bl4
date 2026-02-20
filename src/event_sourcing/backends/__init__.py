"""
Database Backends for Event Store.

Provides persistent storage backends for event sourcing:
- PostgreSQL: ACID-compliant relational storage
- MongoDB: Document-based storage for flexibility
- Migration: Tools for migrating between backends
"""

from src.event_sourcing.backends.base import (
    DatabaseBackend,
    VersionConflictError,
    DatabaseConnectionError,
    DatabaseQueryError,
)
from src.event_sourcing.backends.postgres import PostgresEventStore, PostgresConfig
from src.event_sourcing.backends.mongodb import MongoDBEventStore, MongoDBConfig
from src.event_sourcing.backends.migration import (
    BackendMigrator,
    MigrationConfig,
    MigrationProgress,
    MigrationStatus,
    DualBackendEventStore,
    migrate_postgresql_to_mongodb,
    migrate_mongodb_to_postgresql,
)

__all__ = [
    # Base classes and errors
    "DatabaseBackend",
    "VersionConflictError",
    "DatabaseConnectionError",
    "DatabaseQueryError",
    # PostgreSQL
    "PostgresEventStore",
    "PostgresConfig",
    # MongoDB
    "MongoDBEventStore",
    "MongoDBConfig",
    # Migration
    "BackendMigrator",
    "MigrationConfig",
    "MigrationProgress",
    "MigrationStatus",
    "DualBackendEventStore",
    "migrate_postgresql_to_mongodb",
    "migrate_mongodb_to_postgresql",
]

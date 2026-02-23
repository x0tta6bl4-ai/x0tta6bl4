"""
Event Store Database Migrations.
Compatible with both PostgreSQL and SQLite.

Revision ID: v001
Revises: 0005
Create Date: 2026-02-20

SQLite Notes:
- UUID generation: Application must provide UUID v4 for id field
- Foreign Keys: Enabled via PRAGMA foreign_keys = ON
- JSON: Stored as TEXT (app-level validation required)
"""
from alembic import op
import uuid

revision = 'v001'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'
    
    if is_sqlite:
        # Enable Foreign Keys for SQLite (required for FK constraints to work)
        op.execute("PRAGMA foreign_keys = ON;")
        schema_prefix = "es_"
        ts_type = "DATETIME"
        now_func = "CURRENT_TIMESTAMP"
        
        # SQLite: VARCHAR(36) for UUID, TEXT for JSON
        # FK constraints enabled via PRAGMA above
        streams_sql = f"""
CREATE TABLE IF NOT EXISTS {schema_prefix}streams (
    aggregate_id VARCHAR(255) PRIMARY KEY,
    aggregate_type VARCHAR(255),
    version BIGINT NOT NULL DEFAULT 0,
    created_at {ts_type} NOT NULL DEFAULT {now_func},
    updated_at {ts_type} NOT NULL DEFAULT {now_func}
);
"""
        events_sql = f"""
CREATE TABLE IF NOT EXISTS {schema_prefix}events (
    id VARCHAR(36) PRIMARY KEY,
    aggregate_id VARCHAR(255) NOT NULL REFERENCES {schema_prefix}streams(aggregate_id),
    version BIGINT NOT NULL,
    event_type VARCHAR(255) NOT NULL,
    payload TEXT NOT NULL,
    metadata TEXT,
    created_at {ts_type} NOT NULL DEFAULT {now_func},
    UNIQUE (aggregate_id, version)
);
"""
        snapshots_sql = f"""
CREATE TABLE IF NOT EXISTS {schema_prefix}snapshots (
    aggregate_id VARCHAR(255) PRIMARY KEY REFERENCES {schema_prefix}streams(aggregate_id),
    version BIGINT NOT NULL,
    payload TEXT NOT NULL,
    updated_at {ts_type} NOT NULL DEFAULT {now_func}
);
"""
    else:
        # PostgreSQL: Create schema and use native types
        op.execute("CREATE SCHEMA IF NOT EXISTS event_store;")
        schema_prefix = "event_store."
        ts_type = "TIMESTAMPTZ"
        now_func = "NOW()"
        
        streams_sql = f"""
CREATE TABLE IF NOT EXISTS {schema_prefix}streams (
    aggregate_id VARCHAR(255) PRIMARY KEY,
    aggregate_type VARCHAR(255),
    version BIGINT NOT NULL DEFAULT 0,
    created_at {ts_type} NOT NULL DEFAULT {now_func},
    updated_at {ts_type} NOT NULL DEFAULT {now_func}
);
"""
        events_sql = f"""
CREATE TABLE IF NOT EXISTS {schema_prefix}events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aggregate_id VARCHAR(255) NOT NULL REFERENCES {schema_prefix}streams(aggregate_id),
    version BIGINT NOT NULL,
    event_type VARCHAR(255) NOT NULL,
    payload JSONB NOT NULL,
    metadata JSONB,
    created_at {ts_type} NOT NULL DEFAULT {now_func},
    UNIQUE (aggregate_id, version)
);
"""
        snapshots_sql = f"""
CREATE TABLE IF NOT EXISTS {schema_prefix}snapshots (
    aggregate_id VARCHAR(255) PRIMARY KEY REFERENCES {schema_prefix}streams(aggregate_id),
    version BIGINT NOT NULL,
    payload JSONB NOT NULL,
    updated_at {ts_type} NOT NULL DEFAULT {now_func}
);
"""

    # Create tables in correct order: streams first (referenced by events/snapshots)
    op.execute(streams_sql)
    op.execute(events_sql)
    op.execute(snapshots_sql)


def downgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'
    prefix = "es_" if is_sqlite else "event_store."
    
    # Drop in reverse order: snapshots/events first, then streams
    op.execute(f"DROP TABLE IF EXISTS {prefix}snapshots;")
    op.execute(f"DROP TABLE IF EXISTS {prefix}events;")
    op.execute(f"DROP TABLE IF EXISTS {prefix}streams;")
    
    if not is_sqlite:
        op.execute("DROP SCHEMA IF EXISTS event_store CASCADE;")

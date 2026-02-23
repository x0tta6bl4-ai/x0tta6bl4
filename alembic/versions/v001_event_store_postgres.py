"""
Event Store Database Migrations.

Alembic migration scripts for PostgreSQL event store schema.

Revision ID: v001
Revises: 0005
Create Date: 2026-02-20

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'v001'
down_revision = '0005'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # SQL commands wrapped in Python strings
    op.execute("CREATE SCHEMA IF NOT EXISTS event_store;")
    op.execute("""
CREATE TABLE IF NOT EXISTS event_store.streams (
    aggregate_id VARCHAR(255) PRIMARY KEY,
    aggregate_type VARCHAR(255),
    version BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
""")
    op.execute("""
CREATE TABLE IF NOT EXISTS event_store.events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aggregate_id VARCHAR(255) NOT NULL REFERENCES event_store.streams(aggregate_id),
    version BIGINT NOT NULL,
    event_type VARCHAR(255) NOT NULL,
    payload JSONB NOT NULL,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (aggregate_id, version)
);
""")
    op.execute("""
CREATE TABLE IF NOT EXISTS event_store.snapshots (
    aggregate_id VARCHAR(255) PRIMARY KEY REFERENCES event_store.streams(aggregate_id),
    version BIGINT NOT NULL,
    payload JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
""")

def downgrade() -> None:
    op.execute("DROP SCHEMA IF EXISTS event_store CASCADE;")

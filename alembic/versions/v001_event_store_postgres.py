"""
Event Store Database Migrations.

Alembic migration scripts for PostgreSQL event store schema.
"""

-- Migration: V001 - Initial Event Store Schema
-- Created: 2026-02-20
-- Description: Creates the initial schema for event sourcing with PostgreSQL

-- ============================================================================
-- SCHEMA
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS event_store;

-- ============================================================================
-- TABLES
-- ============================================================================

-- Streams table: Metadata for each event stream
CREATE TABLE IF NOT EXISTS event_store.streams (
    aggregate_id VARCHAR(255) PRIMARY KEY,
    aggregate_type VARCHAR(255),
    version BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE event_store.streams IS 'Event stream metadata';
COMMENT ON COLUMN event_store.streams.aggregate_id IS 'Unique identifier for the aggregate';
COMMENT ON COLUMN event_store.streams.aggregate_type IS 'Type of the aggregate (e.g., Order, User)';
COMMENT ON COLUMN event_store.streams.version IS 'Current version of the stream';

-- Events table: Main event storage
CREATE TABLE IF NOT EXISTS event_store.events (
    id BIGSERIAL,
    event_id VARCHAR(36) PRIMARY KEY,
    aggregate_id VARCHAR(255) NOT NULL,
    aggregate_type VARCHAR(255),
    event_type VARCHAR(255) NOT NULL,
    sequence_number BIGINT NOT NULL,
    data JSONB NOT NULL DEFAULT '{}',
    metadata JSONB NOT NULL DEFAULT '{}',
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT uq_aggregate_sequence UNIQUE (aggregate_id, sequence_number),
    CONSTRAINT fk_events_stream FOREIGN KEY (aggregate_id) 
        REFERENCES event_store.streams(aggregate_id) 
        ON DELETE CASCADE
);

COMMENT ON TABLE event_store.events IS 'Append-only event log';
COMMENT ON COLUMN event_store.events.event_id IS 'Unique event identifier (UUID)';
COMMENT ON COLUMN event_store.events.aggregate_id IS 'ID of the aggregate this event belongs to';
COMMENT ON COLUMN event_store.events.event_type IS 'Type of event (e.g., OrderCreated, PaymentProcessed)';
COMMENT ON COLUMN event_store.events.sequence_number IS 'Sequential version number within the stream';
COMMENT ON COLUMN event_store.events.data IS 'Event payload as JSON';
COMMENT ON COLUMN event_store.events.metadata IS 'Event metadata (correlation_id, causation_id, etc.)';

-- Snapshots table: Aggregate state snapshots
CREATE TABLE IF NOT EXISTS event_store.snapshots (
    snapshot_id VARCHAR(36) PRIMARY KEY,
    aggregate_id VARCHAR(255) NOT NULL,
    aggregate_type VARCHAR(255),
    sequence_number BIGINT NOT NULL,
    state JSONB NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT uq_snapshot_aggregate_version UNIQUE (aggregate_id, sequence_number)
);

COMMENT ON TABLE event_store.snapshots IS 'Aggregate state snapshots for optimization';
COMMENT ON COLUMN event_store.snapshots.sequence_number IS 'Version of the aggregate at snapshot time';
COMMENT ON COLUMN event_store.snapshots.state IS 'Serialized aggregate state';

-- Projections table: Read model projections
CREATE TABLE IF NOT EXISTS event_store.projections (
    projection_name VARCHAR(255) PRIMARY KEY,
    last_processed_position BIGINT NOT NULL DEFAULT 0,
    last_processed_timestamp TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE event_store.projections IS 'Tracks projection processing progress';

-- Subscriptions table: Event subscriptions
CREATE TABLE IF NOT EXISTS event_store.subscriptions (
    subscription_id VARCHAR(36) PRIMARY KEY,
    subscription_name VARCHAR(255) NOT NULL,
    subscriber_id VARCHAR(255) NOT NULL,
    event_types TEXT[],
    filter_expression TEXT,
    last_processed_position BIGINT NOT NULL DEFAULT 0,
    last_processed_timestamp TIMESTAMPTZ,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT uq_subscription_name UNIQUE (subscription_name)
);

COMMENT ON TABLE event_store.subscriptions IS 'Event subscription tracking';

-- ============================================================================
-- INDEXES
-- ============================================================================

-- Primary lookup indexes
CREATE INDEX IF NOT EXISTS idx_events_aggregate_id 
    ON event_store.events (aggregate_id);
    
CREATE INDEX IF NOT EXISTS idx_events_event_type 
    ON event_store.events (event_type);
    
CREATE INDEX IF NOT EXISTS idx_events_timestamp 
    ON event_store.events (timestamp);
    
CREATE INDEX IF NOT EXISTS idx_events_aggregate_type 
    ON event_store.events (aggregate_type);

-- GIN indexes for JSONB queries
CREATE INDEX IF NOT EXISTS idx_events_data 
    ON event_store.events USING GIN (data);
    
CREATE INDEX IF NOT EXISTS idx_events_metadata 
    ON event_store.events USING GIN (metadata);

-- Composite indexes for common queries
CREATE INDEX IF NOT EXISTS idx_events_type_timestamp 
    ON event_store.events (event_type, timestamp);
    
CREATE INDEX IF NOT EXISTS idx_events_aggregate_timestamp 
    ON event_store.events (aggregate_id, timestamp);

-- Snapshot indexes
CREATE INDEX IF NOT EXISTS idx_snapshots_aggregate_id 
    ON event_store.snapshots (aggregate_id);
    
CREATE INDEX IF NOT EXISTS idx_snapshots_aggregate_version 
    ON event_store.snapshots (aggregate_id, sequence_number DESC);

-- Stream indexes
CREATE INDEX IF NOT EXISTS idx_streams_aggregate_type 
    ON event_store.streams (aggregate_type);
    
CREATE INDEX IF NOT EXISTS idx_streams_updated_at 
    ON event_store.streams (updated_at);

-- Subscription indexes
CREATE INDEX IF NOT EXISTS idx_subscriptions_subscriber 
    ON event_store.subscriptions (subscriber_id);
    
CREATE INDEX IF NOT EXISTS idx_subscriptions_status 
    ON event_store.subscriptions (status);

-- ============================================================================
-- FUNCTIONS
-- ============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION event_store.update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for updated_at
DROP TRIGGER IF EXISTS tr_streams_updated_at ON event_store.streams;
CREATE TRIGGER tr_streams_updated_at
    BEFORE UPDATE ON event_store.streams
    FOR EACH ROW
    EXECUTE FUNCTION event_store.update_updated_at();

DROP TRIGGER IF EXISTS tr_subscriptions_updated_at ON event_store.subscriptions;
CREATE TRIGGER tr_subscriptions_updated_at
    BEFORE UPDATE ON event_store.subscriptions
    FOR EACH ROW
    EXECUTE FUNCTION event_store.update_updated_at();

-- Function to append events atomically
CREATE OR REPLACE FUNCTION event_store.append_event(
    p_aggregate_id VARCHAR(255),
    p_aggregate_type VARCHAR(255),
    p_event_id VARCHAR(36),
    p_event_type VARCHAR(255),
    p_sequence_number BIGINT,
    p_data JSONB,
    p_metadata JSONB,
    p_expected_version BIGINT DEFAULT NULL
)
RETURNS BIGINT AS $$
DECLARE
    v_current_version BIGINT;
    v_new_version BIGINT;
BEGIN
    -- Get current version
    SELECT version INTO v_current_version
    FROM event_store.streams
    WHERE aggregate_id = p_aggregate_id
    FOR UPDATE;
    
    IF v_current_version IS NULL THEN
        v_current_version := 0;
        
        -- Create stream
        INSERT INTO event_store.streams (aggregate_id, aggregate_type, version)
        VALUES (p_aggregate_id, p_aggregate_type, 0);
    END IF;
    
    -- Optimistic concurrency check
    IF p_expected_version IS NOT NULL AND v_current_version != p_expected_version THEN
        RAISE EXCEPTION 'Version conflict: expected %, got %', p_expected_version, v_current_version;
    END IF;
    
    -- Insert event
    INSERT INTO event_store.events (
        event_id, aggregate_id, aggregate_type, event_type,
        sequence_number, data, metadata
    ) VALUES (
        p_event_id, p_aggregate_id, p_aggregate_type, p_event_type,
        p_sequence_number, p_data, p_metadata
    );
    
    -- Update stream version
    v_new_version := p_sequence_number;
    
    UPDATE event_store.streams
    SET version = v_new_version, updated_at = NOW()
    WHERE aggregate_id = p_aggregate_id;
    
    RETURN v_new_version;
END;
$$ LANGUAGE plpgsql;

-- Function to get events for replay
CREATE OR REPLACE FUNCTION event_store.get_events_for_replay(
    p_from_timestamp TIMESTAMPTZ DEFAULT NULL,
    p_to_timestamp TIMESTAMPTZ DEFAULT NULL,
    p_event_types TEXT[] DEFAULT NULL,
    p_limit INTEGER DEFAULT 1000
)
RETURNS TABLE (
    event_id VARCHAR(36),
    aggregate_id VARCHAR(255),
    event_type VARCHAR(255),
    sequence_number BIGINT,
    data JSONB,
    metadata JSONB,
    timestamp TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        e.event_id,
        e.aggregate_id,
        e.event_type,
        e.sequence_number,
        e.data,
        e.metadata,
        e.timestamp
    FROM event_store.events e
    WHERE 
        (p_from_timestamp IS NULL OR e.timestamp >= p_from_timestamp)
        AND (p_to_timestamp IS NULL OR e.timestamp <= p_to_timestamp)
        AND (p_event_types IS NULL OR e.event_type = ANY(p_event_types))
    ORDER BY e.timestamp, e.sequence_number
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- VIEWS
-- ============================================================================

-- View for event statistics
CREATE OR REPLACE VIEW event_store.event_statistics AS
SELECT 
    COUNT(*) AS total_events,
    COUNT(DISTINCT aggregate_id) AS total_streams,
    COUNT(DISTINCT event_type) AS event_type_count,
    MIN(timestamp) AS first_event,
    MAX(timestamp) AS last_event
FROM event_store.events;

-- View for stream statistics
CREATE OR REPLACE VIEW event_store.stream_statistics AS
SELECT 
    s.aggregate_id,
    s.aggregate_type,
    s.version,
    COUNT(e.event_id) AS event_count,
    MIN(e.timestamp) AS first_event,
    MAX(e.timestamp) AS last_event
FROM event_store.streams s
LEFT JOIN event_store.events e ON s.aggregate_id = e.aggregate_id
GROUP BY s.aggregate_id, s.aggregate_type, s.version;

-- ============================================================================
-- GRANTS (adjust as needed for your environment)
-- ============================================================================

-- GRANT USAGE ON SCHEMA event_store TO maas_user;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA event_store TO maas_user;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA event_store TO maas_user;
-- GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA event_store TO maas_user;

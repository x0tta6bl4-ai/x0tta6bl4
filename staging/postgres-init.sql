-- PostgreSQL initialization script for x0tta6bl4
-- Runs once on container startup

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "hstore";

-- Create application user if not exists
DO
$$
BEGIN
    CREATE ROLE x0tta6bl4_app WITH LOGIN PASSWORD 'apppassword';
EXCEPTION WHEN duplicate_object THEN
    RAISE NOTICE 'x0tta6bl4_app user already exists, skipping creation';
END
$$;

-- Grant privileges
GRANT CONNECT ON DATABASE x0tta6bl4 TO x0tta6bl4_app;
GRANT USAGE ON SCHEMA public TO x0tta6bl4_app;
GRANT CREATE ON SCHEMA public TO x0tta6bl4_app;

-- Set default privileges for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO x0tta6bl4_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE ON SEQUENCES TO x0tta6bl4_app;

-- Create read-only role
DO
$$
BEGIN
    CREATE ROLE x0tta6bl4_readonly WITH NOLOGIN;
EXCEPTION WHEN duplicate_object THEN
    RAISE NOTICE 'x0tta6bl4_readonly role already exists, skipping creation';
END
$$;

-- Create replicator role
DO
$$
BEGIN
    CREATE ROLE replicator WITH REPLICATION LOGIN PASSWORD 'replicatorpassword';
EXCEPTION WHEN duplicate_object THEN
    RAISE NOTICE 'replicator role already exists, skipping creation';
END
$$;

-- Create monitoring role
DO
$$
BEGIN
    CREATE ROLE x0tta6bl4_monitor WITH LOGIN PASSWORD 'monitorpassword';
EXCEPTION WHEN duplicate_object THEN
    RAISE NOTICE 'x0tta6bl4_monitor role already exists, skipping creation';
END
$$;

-- Grant monitoring privileges
GRANT CONNECT ON DATABASE x0tta6bl4 TO x0tta6bl4_monitor;
GRANT pg_monitor TO x0tta6bl4_monitor;

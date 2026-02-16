# PostgreSQL Setup & Management Guide

## Overview

This guide covers production-grade PostgreSQL setup for x0tta6bl4, including:
- Database initialization with schema creation
- User/role management with RBAC
- Connection pooling with pgBouncer
- Backup/restore procedures
- Streaming replication setup
- Performance monitoring
- Kubernetes deployment

## Quick Start

### Local Development

```bash
# Start PostgreSQL + pgBouncer stack
docker-compose -f staging/docker-compose.postgres.yml up -d

# Run full setup (create users, schema, etc.)
python scripts/database/postgres_setup.py setup

# Check health
bash scripts/database/postgres_health_check.sh
```

### Configuration

Set environment variables before running setup:

```bash
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_ADMIN_USER=postgres
export POSTGRES_ADMIN_PASSWORD=secure_password
export POSTGRES_APP_USER=x0tta6bl4_app
export POSTGRES_APP_PASSWORD=app_secure_password
export POSTGRES_DATABASE=x0tta6bl4
export POSTGRES_BACKUP_PATH=./backups/postgres
export POSTGRES_ENABLE_REPLICATION=false
export POSTGRES_ENABLE_PGBOUNCER=true
```

## Setup Components

### 1. Database Initialization

The setup script creates:
- **Database**: `x0tta6bl4` with UTF-8 encoding
- **Tables**:
  - `mesh_nodes` - Network topology information
  - `spiffe_identities` - SPIFFE certificate storage
  - `api_tokens` - API authentication tokens
  - `audit_log` - Security audit trail
  - `metrics` - Time-series metrics (hypertable if TimescaleDB available)

### 2. User Roles

Created users with proper permissions:

| User | Role | Purpose |
|------|------|---------|
| `x0tta6bl4_app` | Read/Write | Application user |
| `x0tta6bl4_readonly` | Read-only | Reporting/analytics |
| `x0tta6bl4_monitor` | Monitor | Prometheus exporter |
| `replicator` | Replication | Standby replica access |

### 3. Extensions

Enabled PostgreSQL extensions:
- `uuid-ossp` - UUID generation
- `pgcrypto` - Cryptographic functions
- `pg_trgm` - Full-text search optimization
- `hstore` - Key-value storage type
- `timescaledb` (optional) - Time-series database

## Backup & Restore

### Create Backup

```bash
# Manual backup
python scripts/database/postgres_setup.py backup

# Automated backup (cron)
0 2 * * * bash /path/to/scripts/database/postgres_backup.sh
```

Backups are:
- Compressed with gzip
- Named with timestamp
- Automatically cleaned after retention period

### Restore from Backup

```bash
python scripts/database/postgres_setup.py restore /path/to/backup_*.sql.gz
```

## Monitoring

### Real-time Status

```bash
# Full cluster status
bash scripts/database/postgres_monitor.sh

# Health check (for K8s liveness probes)
bash scripts/database/postgres_health_check.sh
```

### Metrics Exported

Via Prometheus exporter on port `9187`:
- Database size
- Connection count
- Replication lag
- Slow queries
- Index usage
- Transaction statistics

### Grafana Dashboard

Import dashboard: `infra/kubernetes/postgres-monitoring.json`

Monitored metrics:
- Database performance
- Connection pool health
- Disk usage
- Replication health

## Replication (HA Setup)

### Enable Replication

```bash
export POSTGRES_ENABLE_REPLICATION=true
python scripts/database/postgres_setup.py setup
```

Configuration applied:
- WAL level: `replica`
- Max WAL senders: 10
- Replication slots: 10
- Hot standby mode enabled

### Setup Standby Replica

```bash
# On standby server
pg_basebackup -h primary.host -D /var/lib/postgresql/data -U replicator

# Configure standby.signal
touch /var/lib/postgresql/data/standby.signal

# Start standby
sudo systemctl start postgresql
```

## pgBouncer Connection Pooling

### Architecture

```
Application → pgBouncer (port 6432) → PostgreSQL (port 5432)
```

### Configuration

Key settings in Docker Compose:
```yaml
POOL_MODE: transaction          # Per-transaction pooling
MAX_CLIENT_CONN: 1000           # Max client connections
DEFAULT_POOL_SIZE: 25           # Connections per pool
MAX_DB_CONNECTIONS: 100         # Total DB connections limit
```

### Health

Check pgBouncer status:
```sql
SHOW POOLS;
SHOW CLIENTS;
SHOW SERVERS;
```

## Kubernetes Deployment

### Prerequisites

```bash
# Install fast-ssd storage class
kubectl create -f infra/kubernetes/storage-classes.yaml

# Create secrets
kubectl create secret generic postgres-credentials \
  --from-literal=POSTGRES_PASSWORD=secure \
  --from-literal=POSTGRES_APP_PASSWORD=app_secure \
  -n x0tta6bl4-db
```

### Deploy

```bash
# Apply StatefulSet
kubectl apply -f infra/kubernetes/postgres-statefulset.yaml

# Verify
kubectl get statefulset -n x0tta6bl4-db
kubectl logs -f postgres-0 -n x0tta6bl4-db
```

### Verify Deployment

```bash
# Connect to database
kubectl exec -it postgres-0 -n x0tta6bl4-db -- psql -U postgres

# View replication status
kubectl exec postgres-0 -n x0tta6bl4-db -- \
  psql -U postgres -c "SELECT * FROM pg_stat_replication;"
```

## Database Migrations

### Using Alembic

```bash
# Create initial migration
alembic revision --autogenerate -m "Initial schema"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

### Migration History

```bash
# View migration status
alembic current
alembic history

# Upgrade to specific version
alembic upgrade <revision>
```

## Performance Tuning

### Connection Pool Tuning

Based on deployment size:

**Small (< 100 concurrent users)**
```
default_pool_size = 10
max_client_conn = 100
```

**Medium (100-500 users)**
```
default_pool_size = 25
max_client_conn = 500
```

**Large (> 500 users)**
```
default_pool_size = 50
max_client_conn = 1000
```

### PostgreSQL Tuning

Applied automatically for instance size:

```sql
-- View current settings
SHOW shared_buffers;
SHOW effective_cache_size;
SHOW work_mem;
SHOW maintenance_work_mem;
```

### Index Optimization

```bash
# Check missing indexes
SELECT * FROM v_missing_indexes;

# Check unused indexes
SELECT * FROM v_unused_indexes;

# Reindex if needed
REINDEX DATABASE x0tta6bl4;
```

## Troubleshooting

### Connection Issues

```bash
# Test connectivity
pg_isready -h localhost -p 5432

# Check max connections
psql -c "SHOW max_connections;"

# Kill idle connections
psql -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle';"
```

### Slow Queries

```sql
-- Enable logging
ALTER SYSTEM SET log_min_duration_statement = 1000;
SELECT pg_reload_conf();

-- Check slow queries
SELECT query, calls, mean_time FROM pg_stat_statements
ORDER BY mean_time DESC LIMIT 10;
```

### Replication Lag

```sql
-- Check lag
SELECT client_addr, state, write_lag, replay_lag FROM pg_stat_replication;

-- Monitor WAL archiving
SHOW archive_command;
SELECT * FROM pg_ls_archive_statusdir();
```

### Disk Space

```sql
-- Database size
SELECT datname, pg_size_pretty(pg_database_size(datname)) FROM pg_database;

-- Table sizes
SELECT tablename, pg_size_pretty(pg_total_relation_size(tablename))
FROM pg_tables WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(tablename) DESC;
```

## Security Considerations

### SSL/TLS

Enable SSL in production:
```sql
ALTER SYSTEM SET ssl = on;
ALTER SYSTEM SET ssl_cert_file = '/path/to/cert.pem';
ALTER SYSTEM SET ssl_key_file = '/path/to/key.pem';
SELECT pg_reload_conf();
```

### Password Security

```sql
-- Strong password policy
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Generate secure password
SELECT encode(gen_random_bytes(16), 'hex');
```

### Audit Logging

```sql
-- Enable audit log table (automatic)
SELECT * FROM audit_log ORDER BY created_at DESC;

-- View user actions
SELECT actor_id, action, result, created_at FROM audit_log
WHERE event_type = 'user_action';
```

## Backup Strategy

### RPO (Recovery Point Objective)
- **Daily full backups** - Retain 30 days
- **WAL archiving** - Continuous point-in-time recovery (PITR)
- **Streaming replication** - Real-time standby

### RTO (Recovery Time Objective)
- Streaming replication: < 5 seconds failover
- Point-in-time recovery: 30-60 minutes

## References

- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [pgBouncer Manual](https://pgbouncer.github.io/)
- [Alembic Docs](https://alembic.sqlalchemy.org/)
- [Prometheus PostgreSQL Exporter](https://github.com/prometheus-community/postgres_exporter)

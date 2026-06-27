#!/bin/bash
set -euo pipefail

HOST="${POSTGRES_HOST:-localhost}"
PORT="${POSTGRES_PORT:-5432}"
ADMIN_USER="${POSTGRES_ADMIN_USER:-postgres}"
DATABASE="${POSTGRES_DATABASE:-x0tta6bl4}"

psql_cmd="psql -h $HOST -p $PORT -U $ADMIN_USER -d $DATABASE -t"

echo "🔍 PostgreSQL Cluster Status"
echo "======================================"

echo ""
echo "📊 Server Information:"
$psql_cmd -c "SELECT version();"

echo ""
echo "💾 Database Size:"
$psql_cmd -c "SELECT datname, pg_size_pretty(pg_database_size(datname)) FROM pg_database WHERE datname = '$DATABASE';"

echo ""
echo "📈 Connection Statistics:"
$psql_cmd -c "
SELECT
  datname,
  count(*) as total_connections,
  count(*) FILTER (WHERE state = 'active') as active,
  count(*) FILTER (WHERE state = 'idle') as idle,
  count(*) FILTER (WHERE state = 'idle in transaction') as idle_in_transaction,
  count(*) FILTER (WHERE state = 'idle in transaction (aborted)') as idle_in_transaction_aborted
FROM pg_stat_activity
WHERE datname = '$DATABASE'
GROUP BY datname;
"

echo ""
echo "🔄 Replication Status:"
$psql_cmd -c "
SELECT
  client_addr,
  state,
  sent_lsn,
  write_lsn,
  flush_lsn,
  replay_lsn,
  sync_state
FROM pg_stat_replication;
" || echo "⚠️  No replication slots active"

echo ""
echo "📉 Slow Queries (> 1s):"
$psql_cmd -c "
SELECT
  query,
  calls,
  total_time / 1000 as total_seconds,
  mean_time as mean_ms,
  max_time as max_ms
FROM pg_stat_statements
WHERE mean_time > 1000
ORDER BY mean_time DESC
LIMIT 10;
" || echo "⚠️  pg_stat_statements not enabled"

echo ""
echo "📦 Table Sizes:"
$psql_cmd -c "
SELECT
  tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
LIMIT 10;
"

echo ""
echo "🗂️  Index Health:"
$psql_cmd -c "
SELECT
  schemaname,
  tablename,
  indexname,
  idx_scan,
  idx_tup_read,
  idx_tup_fetch
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC
LIMIT 10;
"

echo ""
echo "✅ Status check completed"

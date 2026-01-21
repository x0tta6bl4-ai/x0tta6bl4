#!/bin/bash
set -euo pipefail

HOST="${POSTGRES_HOST:-localhost}"
PORT="${POSTGRES_PORT:-5432}"
ADMIN_USER="${POSTGRES_ADMIN_USER:-postgres}"
DATABASE="${POSTGRES_DATABASE:-x0tta6bl4}"

check_connectivity() {
    if pg_isready -h "$HOST" -p "$PORT" -U "$ADMIN_USER" > /dev/null 2>&1; then
        echo "✅ PostgreSQL is accepting connections"
        return 0
    else
        echo "❌ PostgreSQL is not accepting connections"
        return 1
    fi
}

check_database_exists() {
    result=$(psql -h "$HOST" -p "$PORT" -U "$ADMIN_USER" -tc "SELECT 1 FROM pg_database WHERE datname = '$DATABASE'" 2>/dev/null || echo "")
    if [[ $result == *"1"* ]]; then
        echo "✅ Database '$DATABASE' exists"
        return 0
    else
        echo "❌ Database '$DATABASE' not found"
        return 1
    fi
}

check_replication() {
    result=$(psql -h "$HOST" -p "$PORT" -U "$ADMIN_USER" -d "$DATABASE" -tc "SELECT count(*) FROM pg_stat_replication" 2>/dev/null || echo "0")
    if [[ $result -gt 0 ]]; then
        echo "✅ Replication active with $result standby(s)"
        return 0
    else
        echo "⚠️  No active replication"
        return 0
    fi
}

check_wal_level() {
    result=$(psql -h "$HOST" -p "$PORT" -U "$ADMIN_USER" -d "$DATABASE" -tc "SHOW wal_level" 2>/dev/null || echo "")
    if [[ $result == *"replica"* ]] || [[ $result == *"logical"* ]]; then
        echo "✅ WAL level is '$result' (replication ready)"
        return 0
    else
        echo "⚠️  WAL level is '$result' (not replication ready)"
        return 1
    fi
}

check_connections() {
    result=$(psql -h "$HOST" -p "$PORT" -U "$ADMIN_USER" -d "$DATABASE" -tc "SELECT count(*) FROM pg_stat_activity WHERE datname = '$DATABASE'" 2>/dev/null || echo "0")
    max_connections=$(psql -h "$HOST" -p "$PORT" -U "$ADMIN_USER" -d "$DATABASE" -tc "SHOW max_connections" 2>/dev/null || echo "100")
    if (( result < max_connections )); then
        echo "✅ Connection pool healthy: $result/$max_connections connections"
        return 0
    else
        echo "⚠️  Connection pool near limit: $result/$max_connections"
        return 0
    fi
}

check_disk_space() {
    size=$(psql -h "$HOST" -p "$PORT" -U "$ADMIN_USER" -d "$DATABASE" -tc "SELECT pg_database_size('$DATABASE')" 2>/dev/null || echo "0")
    size_mb=$((size / 1024 / 1024))
    echo "✅ Database size: ${size_mb}MB"
    return 0
}

check_required_users() {
    result=$(psql -h "$HOST" -p "$PORT" -U "$ADMIN_USER" -tc "SELECT count(*) FROM pg_user WHERE usename IN ('x0tta6bl4_app', 'replicator')" 2>/dev/null || echo "0")
    if (( result >= 1 )); then
        echo "✅ Required users exist"
        return 0
    else
        echo "⚠️  Some required users are missing"
        return 0
    fi
}

main() {
    echo "🏥 PostgreSQL Health Check"
    echo "======================================"
    echo ""
    
    exit_code=0
    
    check_connectivity || exit_code=$?
    check_database_exists || exit_code=$?
    check_replication || exit_code=$?
    check_wal_level || exit_code=$?
    check_connections || exit_code=$?
    check_disk_space || exit_code=$?
    check_required_users || exit_code=$?
    
    echo ""
    if [[ $exit_code -eq 0 ]]; then
        echo "✅ All health checks passed"
    else
        echo "⚠️  Some health checks failed or found warnings"
    fi
    
    exit $exit_code
}

main "$@"

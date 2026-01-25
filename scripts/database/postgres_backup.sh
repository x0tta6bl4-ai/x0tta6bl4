#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="${POSTGRES_BACKUP_PATH:-./backups/postgres}"
DATABASE="${POSTGRES_DATABASE:-x0tta6bl4}"
HOST="${POSTGRES_HOST:-localhost}"
PORT="${POSTGRES_PORT:-5432}"
ADMIN_USER="${POSTGRES_ADMIN_USER:-postgres}"
RETENTION_DAYS="${POSTGRES_BACKUP_RETENTION_DAYS:-30}"

mkdir -p "$BACKUP_DIR"

backup_file="$BACKUP_DIR/backup_${DATABASE}_$(date +%Y%m%d_%H%M%S).sql.gz"

echo "💾 Creating backup: $backup_file"

PGPASSWORD="$POSTGRES_ADMIN_PASSWORD" pg_dump \
  -h "$HOST" \
  -p "$PORT" \
  -U "$ADMIN_USER" \
  -d "$DATABASE" \
  --no-password \
  --format=plain \
  --verbose \
  | gzip > "$backup_file"

size_mb=$(du -m "$backup_file" | cut -f1)
echo "✅ Backup completed: $backup_file ($size_mb MB)"

cleanup_old_backups() {
    echo "🗑️  Cleaning up backups older than $RETENTION_DAYS days"
    find "$BACKUP_DIR" -name "backup_*.sql.gz" -mtime "+$RETENTION_DAYS" -delete
    echo "✅ Cleanup completed"
}

cleanup_old_backups

#!/bin/bash
# Backup script для базы данных x0tta6bl4

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DB_FILE="$SCRIPT_DIR/x0tta6bl4_users.db"
BACKUP_DIR="$SCRIPT_DIR/backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/x0tta6bl4_users_$DATE.db"

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Check if database exists
if [ ! -f "$DB_FILE" ]; then
    echo "❌ Database file not found: $DB_FILE"
    exit 1
fi

# Create backup
cp "$DB_FILE" "$BACKUP_FILE"
echo "✅ Backup created: $BACKUP_FILE"

# Compress backup
gzip "$BACKUP_FILE"
echo "✅ Backup compressed: $BACKUP_FILE.gz"

# Keep only last 30 backups
cd "$BACKUP_DIR"
ls -t x0tta6bl4_users_*.db.gz | tail -n +31 | xargs -r rm
echo "✅ Old backups cleaned (keeping last 30)"

# Show backup size
BACKUP_SIZE=$(du -h "$BACKUP_FILE.gz" | cut -f1)
echo "📦 Backup size: $BACKUP_SIZE"

echo ""
echo "✅ Backup complete!"


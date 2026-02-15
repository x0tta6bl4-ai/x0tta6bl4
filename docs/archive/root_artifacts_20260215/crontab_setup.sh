#!/bin/bash
# Setup cron jobs для x0tta6bl4

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "⏰ Setting up cron jobs for x0tta6bl4"
echo "======================================"

# Backup database daily at 2 AM
(crontab -l 2>/dev/null | grep -v "backup_database.sh"; echo "0 2 * * * $SCRIPT_DIR/backup_database.sh >> $SCRIPT_DIR/logs/backup.log 2>&1") | crontab -
echo "✅ Daily backup scheduled (2 AM)"

# Check expired subscriptions daily at 3 AM
(crontab -l 2>/dev/null | grep -v "expired_subscriptions_checker.py"; echo "0 3 * * * /usr/bin/python3 $SCRIPT_DIR/expired_subscriptions_checker.py >> $SCRIPT_DIR/logs/expired_check.log 2>&1") | crontab -
echo "✅ Expired subscriptions check scheduled (3 AM)"

# Health check every hour
(crontab -l 2>/dev/null | grep -v "health_check.py"; echo "0 * * * * /usr/bin/python3 $SCRIPT_DIR/health_check.py >> $SCRIPT_DIR/logs/health_check.log 2>&1") | crontab -
echo "✅ Health check scheduled (every hour)"

# Create logs directory
mkdir -p "$SCRIPT_DIR/logs"
echo "✅ Logs directory created"

echo ""
echo "📋 Current cron jobs:"
crontab -l | grep -E "(backup|expired|health_check)" || echo "  (none found)"

echo ""
echo "✅ Cron setup complete!"


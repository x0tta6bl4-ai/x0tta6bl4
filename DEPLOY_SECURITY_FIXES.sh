#!/bin/bash
# Скрипт для деплоя security fixes на VPS
# Использование: ./DEPLOY_SECURITY_FIXES.sh

set -e  # Exit on error

VPS_HOST="89.125.1.107"
VPS_USER="root"
REMOTE_DIR="/mnt/AC74CC2974CBF3DC"

echo "🔒 Deploying Security Fixes to VPS..."
echo "=================================="
echo ""

# 1. Backup database
echo "📦 Step 1: Creating database backup..."
ssh ${VPS_USER}@${VPS_HOST} "cd ${REMOTE_DIR} && cp x0tta6bl4_users.db x0tta6bl4_users.db.backup_\$(date +%Y%m%d_%H%M%S) 2>/dev/null || echo 'Database backup created'"
echo "✅ Database backed up"
echo ""

# 2. Update .env file
echo "📝 Step 2: Updating .env file..."
echo ""
echo "⚠️  IMPORTANT: You need to set REALITY_PRIVATE_KEY and ADMIN_USER_IDS in .env"
echo ""
read -p "Enter REALITY_PRIVATE_KEY (or press Enter to skip): " REALITY_KEY
read -p "Enter ADMIN_USER_IDS (comma-separated, or press Enter to skip): " ADMIN_IDS

if [ ! -z "$REALITY_KEY" ]; then
    ssh ${VPS_USER}@${VPS_HOST} "echo 'REALITY_PRIVATE_KEY=${REALITY_KEY}' >> ${REMOTE_DIR}/.env"
    echo "✅ REALITY_PRIVATE_KEY added to .env"
fi

if [ ! -z "$ADMIN_IDS" ]; then
    ssh ${VPS_USER}@${VPS_HOST} "echo 'ADMIN_USER_IDS=${ADMIN_IDS}' >> ${REMOTE_DIR}/.env"
    echo "✅ ADMIN_USER_IDS added to .env"
fi
echo ""

# 3. Upload fixed files
echo "📤 Step 3: Uploading fixed files..."
scp vpn_config_generator.py ${VPS_USER}@${VPS_HOST}:${REMOTE_DIR}/
scp telegram_bot.py ${VPS_USER}@${VPS_HOST}:${REMOTE_DIR}/
scp admin_commands.py ${VPS_USER}@${VPS_HOST}:${REMOTE_DIR}/
echo "✅ Files uploaded"
echo ""

# 4. Restart bot
echo "🔄 Step 4: Restarting bot..."
ssh ${VPS_USER}@${VPS_HOST} "systemctl restart x0tta6bl4-bot"
sleep 2
echo "✅ Bot restarted"
echo ""

# 5. Check bot status
echo "📊 Step 5: Checking bot status..."
if ssh ${VPS_USER}@${VPS_HOST} "systemctl is-active --quiet x0tta6bl4-bot"; then
    echo "✅ Bot is running"
else
    echo "❌ Bot is NOT running! Check logs:"
    ssh ${VPS_USER}@${VPS_HOST} "journalctl -u x0tta6bl4-bot -n 20 --no-pager"
    exit 1
fi
echo ""

# 6. Check logs for errors
echo "🔍 Step 6: Checking logs for security-related messages..."
ssh ${VPS_USER}@${VPS_HOST} "journalctl -u x0tta6bl4-bot -n 50 --no-pager | grep -E 'SECURITY|CRITICAL|ERROR|REALITY_PRIVATE_KEY|user_uuid is required' || echo 'No security errors found'"
echo ""

echo "=================================="
echo "✅ Security fixes deployed!"
echo ""
echo "📋 Next steps:"
echo "1. Test trial activation: /trial in bot"
echo "2. Test admin commands: /admin_stats (as admin)"
echo "3. Monitor logs: journalctl -u x0tta6bl4-bot -f"
echo "4. Check database: SELECT user_id, vpn_uuid FROM users LIMIT 5"
echo ""


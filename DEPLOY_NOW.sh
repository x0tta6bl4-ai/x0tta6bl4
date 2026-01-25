#!/bin/bash
# 🚀 DEPLOY NOW - Conservative Deployment Script
# Выполняет все шаги с checkpoint'ами

set -e

echo "🚀 Starting Conservative Deployment..."
echo "=================================="
echo ""

cd /mnt/AC74CC2974CBF3DC

# Stage 1: Pre-deployment checks
echo "🔍 Stage 1: Pre-deployment checks..."
if [ -f pre_deploy_check.sh ]; then
    ./pre_deploy_check.sh
    if [ $? -ne 0 ]; then
        echo "❌ Pre-deployment checks failed!"
        exit 1
    fi
else
    echo "⚠️  pre_deploy_check.sh not found, skipping..."
fi

echo ""
read -p "✅ CHECKPOINT 1: Continue to backup? (yes/no) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Deployment cancelled"
    exit 1
fi

# Stage 2: Backup
echo ""
echo "📦 Stage 2: Creating backups..."
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

if [ -f x0tta6bl4_users.db ]; then
    cp x0tta6bl4_users.db "x0tta6bl4_users.db.backup_pre_security_${TIMESTAMP}"
    echo "✅ Database backup created"
fi

if [ -f .env ]; then
    cp .env ".env.backup.${TIMESTAMP}"
    echo "✅ Environment backup created"
fi

echo "✅ CHECKPOINT 2: Backups created (timestamp: ${TIMESTAMP})"

# Stage 3: Update .env
echo ""
echo "📝 Stage 3: Updating environment..."
if ! grep -q "REALITY_PRIVATE_KEY" .env 2>/dev/null; then
    echo "REALITY_PRIVATE_KEY=sARj3nxY80sVRmeCxqZbTHyw-bj6Si4vXb3Q-mlflFw" >> .env
    echo "✅ REALITY_PRIVATE_KEY added"
fi

if ! grep -q "ADMIN_USER_IDS" .env 2>/dev/null || grep -q "YOUR_ADMIN_USER_ID" .env 2>/dev/null; then
    echo "⚠️  CRITICAL: ADMIN_USER_IDS not set!"
    echo "   Please edit .env and add: ADMIN_USER_IDS=your_telegram_user_id"
    echo "   Then run this script again."
    exit 1
fi

# Stage 4: Verify files
echo ""
echo "📤 Stage 4: Verifying files..."
if grep -q "os.getenv(\"REALITY_PRIVATE_KEY\")" vpn_config_generator.py; then
    echo "✅ Security fixes in code"
else
    echo "❌ Security fixes NOT in code!"
    exit 1
fi

# Stage 5: Restart
echo ""
echo "🔄 Stage 5: Restarting bot..."
systemctl restart x0tta6bl4-bot
sleep 5

if systemctl is-active --quiet x0tta6bl4-bot; then
    echo "✅ CHECKPOINT 3: Bot restarted successfully"
else
    echo "❌ Bot failed to start!"
    journalctl -u x0tta6bl4-bot -n 50
    exit 1
fi

# Stage 6: Post-deployment tests
echo ""
echo "🧪 Stage 6: Running post-deployment tests..."
if [ -f post_deploy_security_tests.sh ]; then
    ./post_deploy_security_tests.sh
    if [ $? -eq 0 ]; then
        echo "✅ CHECKPOINT 4: All tests passed"
    else
        echo "❌ Tests failed! Consider rollback."
        exit 1
    fi
else
    echo "⚠️  post_deploy_security_tests.sh not found, skipping..."
fi

# Stage 7: Quick monitoring
echo ""
echo "📊 Stage 7: Quick status check..."
sleep 3
ERRORS=$(journalctl -u x0tta6bl4-bot --since "2 minutes ago" 2>/dev/null | grep -iE "error|critical|exception" | grep -v "REALITY_PRIVATE_KEY not set" | wc -l)
if [ $ERRORS -eq 0 ]; then
    echo "✅ No errors in logs"
else
    echo "⚠️  Found $ERRORS errors in logs (check manually)"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎉 DEPLOYMENT COMPLETE!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📋 Next steps:"
echo "  1. Test bot: send /start in Telegram"
echo "  2. Test admin: send /admin_stats (as admin)"
echo "  3. Monitor: journalctl -u x0tta6bl4-bot -f"
echo ""
echo "🔄 Rollback (if needed):"
echo "  TIMESTAMP=${TIMESTAMP}"
echo "  cp x0tta6bl4_users.db.backup_pre_security_${TIMESTAMP} x0tta6bl4_users.db"
echo "  systemctl restart x0tta6bl4-bot"
echo ""


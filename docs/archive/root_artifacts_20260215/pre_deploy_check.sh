#!/bin/bash
# Pre-Deployment Security Check
# Проверяет что все готово для безопасного деплоя

set -e

echo "🔒 Pre-Deployment Security Check"
echo "=================================="
echo ""

# 1. Check environment variables
echo "1️⃣ Checking environment variables..."
if [ ! -f .env ]; then
    echo "❌ CRITICAL: .env file not found!"
    exit 1
fi

source .env

if [ -z "$REALITY_PRIVATE_KEY" ]; then
    echo "❌ CRITICAL: REALITY_PRIVATE_KEY not set in .env!"
    exit 1
fi

if [ ${#REALITY_PRIVATE_KEY} -lt 32 ]; then
    echo "❌ CRITICAL: REALITY_PRIVATE_KEY too short (${#REALITY_PRIVATE_KEY} chars, need >=32)!"
    exit 1
fi

if [ -z "$ADMIN_USER_ID" ] && [ -z "$ADMIN_USER_IDS" ]; then
    echo "❌ CRITICAL: No admin configured (ADMIN_USER_ID or ADMIN_USER_IDS)!"
    exit 1
fi

echo "✅ Environment variables OK"
echo ""

# 2. Check database backup
echo "2️⃣ Checking database backup..."
if [ -f "x0tta6bl4_users.db" ]; then
    timestamp=$(date +%Y%m%d_%H%M%S)
    backup_file="x0tta6bl4_users.db.backup_pre_security_${timestamp}"
    cp x0tta6bl4_users.db "$backup_file"
    echo "✅ Database backup created: $backup_file"
else
    echo "⚠️  No existing database (first deployment?)"
fi
echo ""

# 3. Check disk space
echo "3️⃣ Checking disk space..."
available=$(df -h . | tail -1 | awk '{print $4}')
echo "Available space: $available"
if [ $(df . | tail -1 | awk '{print $4}') -lt 1000000 ]; then
    echo "⚠️  WARNING: Less than 1GB free space"
else
    echo "✅ Disk space OK"
fi
echo ""

# 4. Check bot status
echo "4️⃣ Checking bot status..."
if systemctl is-active --quiet x0tta6bl4-bot 2>/dev/null; then
    echo "✅ Bot is currently running"
    current_users=$(sqlite3 x0tta6bl4_users.db "SELECT COUNT(*) FROM users;" 2>/dev/null || echo "0")
    echo "   Current users: $current_users"
else
    echo "⚠️  Bot is not running (first deployment?)"
fi
echo ""

# 5. Check Python syntax
echo "5️⃣ Checking Python syntax..."
python3 -m py_compile vpn_config_generator.py telegram_bot.py admin_commands.py 2>&1
if [ $? -eq 0 ]; then
    echo "✅ Python syntax OK"
else
    echo "❌ CRITICAL: Python syntax errors!"
    exit 1
fi
echo ""

# 6. Check imports
echo "6️⃣ Checking imports..."
python3 -c "
import sys
sys.path.insert(0, '.')
try:
    from vpn_config_generator import generate_uuid, generate_vless_link
    from admin_commands import is_admin
    from database import get_user
    print('✅ All imports OK')
except ImportError as e:
    print(f'❌ Import error: {e}')
    sys.exit(1)
" 2>&1
if [ $? -ne 0 ]; then
    exit 1
fi
echo ""

# 7. Check secrets not in code
echo "7️⃣ Checking secrets not hardcoded..."
if grep -r "sARj3nxY80sVRmeCxqZbTHyw-bj6Si4vXb3Q-mlflFw" *.py 2>/dev/null; then
    echo "❌ CRITICAL: Hardcoded REALITY_PRIVATE_KEY found in code!"
    exit 1
fi

if grep -r "DEFAULT_UUID = " *.py 2>/dev/null; then
    echo "❌ CRITICAL: DEFAULT_UUID still in code!"
    exit 1
fi

echo "✅ No hardcoded secrets found"
echo ""

echo "=================================="
echo "✅ All pre-deployment checks PASSED"
echo "=================================="
echo ""
echo "Ready for deployment! 🚀"


#!/bin/bash
# Post-Deployment Security Tests
# Проверяет что security fixes работают после деплоя

set -e

echo "🔒 Post-Deployment Security Tests"
echo "=================================="
echo ""

# Test 1: Secrets not in logs
echo "1️⃣ Checking logs for leaked secrets..."
if journalctl -u x0tta6bl4-bot --since "5 minutes ago" 2>/dev/null | grep -iE "REALITY_PRIVATE_KEY.*=|password.*=|secret.*=" | grep -v "not set"; then
    echo "❌ CRITICAL: Secrets found in logs!"
    exit 1
else
    echo "✅ No secrets in logs"
fi
echo ""

# Test 2: Unique UUIDs
echo "2️⃣ Testing UUID uniqueness..."
python3 << 'EOF'
import sys
sys.path.insert(0, '.')

from database import get_active_users

users = get_active_users()

if len(users) == 0:
    print("⚠️  No users yet - skipping UUID test")
    exit(0)

uuids = [u.get('vpn_uuid') for u in users if u.get('vpn_uuid')]
unique_uuids = set(uuids)

if len(uuids) != len(unique_uuids):
    print(f"❌ CRITICAL: Duplicate UUIDs found! {len(uuids)} total, {len(unique_uuids)} unique")
    exit(1)

print(f"✅ All {len(uuids)} UUIDs are unique")
EOF

if [ $? -ne 0 ]; then
    exit 1
fi
echo ""

# Test 3: Payment validation exists
echo "3️⃣ Testing payment validation code..."
if grep -q "total_amount != MONTHLY_PRICE" telegram_bot.py; then
    echo "✅ Payment amount validation exists"
else
    echo "❌ CRITICAL: Payment validation not found!"
    exit 1
fi

if grep -q "currency != \"USD\"" telegram_bot.py; then
    echo "✅ Payment currency validation exists"
else
    echo "❌ CRITICAL: Currency validation not found!"
    exit 1
fi

if grep -q "invoice_payload" telegram_bot.py; then
    echo "✅ Payment payload validation exists"
else
    echo "❌ CRITICAL: Payload validation not found!"
    exit 1
fi
echo ""

# Test 4: Admin auth restrictive
echo "4️⃣ Testing admin authentication..."
python3 << 'EOF'
import sys
import os
sys.path.insert(0, '.')

from admin_commands import is_admin

# Test with non-admin user
test_user_id = 99999999

# Clear admin env vars for test
os.environ.pop('ADMIN_USER_ID', None)
os.environ.pop('ADMIN_USER_IDS', None)

if is_admin(test_user_id):
    print("❌ CRITICAL: Admin auth NOT working - unauthorized user has access!")
    exit(1)

print("✅ Admin auth working - non-admin correctly denied")
EOF

if [ $? -ne 0 ]; then
    exit 1
fi
echo ""

# Test 5: Bot is running
echo "5️⃣ Testing bot status..."
if systemctl is-active --quiet x0tta6bl4-bot; then
    echo "✅ Bot is running"
else
    echo "❌ CRITICAL: Bot is not running!"
    exit 1
fi
echo ""

# Test 6: No errors in recent logs
echo "6️⃣ Checking for errors in logs..."
error_count=$(journalctl -u x0tta6bl4-bot --since "5 minutes ago" --no-pager 2>/dev/null | grep -iE "ERROR|CRITICAL|Exception|Traceback" | grep -v "REALITY_PRIVATE_KEY not set" | wc -l)
if [ $error_count -gt 0 ]; then
    echo "⚠️  WARNING: $error_count errors found in logs (check manually)"
    journalctl -u x0tta6bl4-bot --since "5 minutes ago" --no-pager | grep -iE "ERROR|CRITICAL" | tail -5
else
    echo "✅ No critical errors in logs"
fi
echo ""

echo "=================================="
echo "✅ All post-deployment security tests PASSED"
echo "=================================="


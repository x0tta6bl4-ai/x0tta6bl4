#!/bin/bash
# Monitor deployment for 5 minutes after deploy
# Watches logs and metrics for issues

echo "📊 Monitoring deployment for 5 minutes..."
echo "Press Ctrl+C to stop early"
echo ""

# Watch logs for errors
echo "Watching logs for errors..."
journalctl -u x0tta6bl4-bot -f --since "1 minute ago" 2>/dev/null | grep --color=always -E "ERROR|CRITICAL|Exception|UUID|REALITY|SECURITY" &
LOG_PID=$!

# Monitor bot status
echo "Monitoring bot status..."
for i in {1..30}; do
    if systemctl is-active --quiet x0tta6bl4-bot; then
        status="✅ Running"
    else
        status="❌ NOT Running"
    fi
    
    # Count recent errors
    error_count=$(journalctl -u x0tta6bl4-bot --since "1 minute ago" --no-pager 2>/dev/null | grep -iE "ERROR|CRITICAL" | grep -v "REALITY_PRIVATE_KEY not set" | wc -l)
    
    echo "[$i/30] Bot status: $status | Errors (last min): $error_count"
    
    sleep 10
done

# Cleanup
kill $LOG_PID 2>/dev/null

echo ""
echo "✅ 5-minute monitoring complete"
echo ""
echo "📋 Summary:"
echo "  - Check logs: journalctl -u x0tta6bl4-bot -n 100"
echo "  - Check status: systemctl status x0tta6bl4-bot"
echo "  - Check users: sqlite3 x0tta6bl4_users.db 'SELECT COUNT(*) FROM users;'"


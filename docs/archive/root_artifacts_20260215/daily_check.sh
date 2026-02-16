#!/bin/bash
# Ежедневная проверка статуса бота и статистики
# Добавь в crontab: 0 9 * * * /mnt/AC74CC2974CBF3DC/daily_check.sh

cd /mnt/AC74CC2974CBF3DC

echo "🔍 Daily Check - $(date)"
echo "=========================="
echo ""

# Проверить статус бота
echo "🤖 Bot Status:"
if systemctl is-active --quiet x0tta6bl4-bot; then
    echo "  ✅ Bot is running"
else
    echo "  ❌ Bot is NOT running!"
    echo "  Restarting..."
    systemctl restart x0tta6bl4-bot
    sleep 2
    if systemctl is-active --quiet x0tta6bl4-bot; then
        echo "  ✅ Bot restarted successfully"
    else
        echo "  ❌ Bot failed to start!"
    fi
fi
echo ""

# Показать статистику
echo "📊 Statistics:"
python3 monitor_stats.py
echo ""

# Проверить последние логи на ошибки
echo "🔍 Recent Errors (last 20 lines):"
journalctl -u x0tta6bl4-bot -n 20 --no-pager | grep -i error || echo "  ✅ No errors found"
echo ""

echo "✅ Daily check complete"
echo ""


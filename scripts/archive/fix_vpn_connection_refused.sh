#!/bin/bash
# Скрипт для исправления connection refused
# Запустить на сервере: ssh root@89.125.1.107

set -euo pipefail

echo "🔧 Исправление connection refused..."

# Убить старые процессы
pkill -9 xray 2>/dev/null || true
pkill -9 xray-linux-amd6 2>/dev/null || true
sleep 2

# Сбросить failed статус
systemctl reset-failed xray

# Перезапустить
systemctl start xray
sleep 4

# Проверка
if systemctl is-active --quiet xray; then
    echo "✅ Xray запущен"
    ss -tlnp | grep 39829 && echo "✅ Порт 39829 слушается"
    echo ""
    echo "✅ Проблема исправлена!"
else
    echo "❌ Xray не запустился"
    journalctl -u xray -n 10 --no-pager
    exit 1
fi


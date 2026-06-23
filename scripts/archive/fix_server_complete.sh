#!/bin/bash
# Полное исправление сервера VPN
# Запустить: ssh root@89.125.1.107 'bash -s' < fix_server_complete.sh

set -euo pipefail

echo "🔧 Полное исправление сервера VPN..."

# 1. Убиваем все процессы
echo "1️⃣ Убиваем старые процессы..."
killall -9 xray xray-linux-amd64 x-ui 2>/dev/null || true
lsof -ti:39829 | xargs kill -9 2>/dev/null || true
lsof -ti:62789 | xargs kill -9 2>/dev/null || true
sleep 3

# 2. Останавливаем x-ui
echo "2️⃣ Останавливаем x-ui..."
systemctl stop x-ui 2>/dev/null || true
systemctl disable x-ui 2>/dev/null || true

# 3. Восстанавливаем конфигурацию из бэкапа
echo "3️⃣ Восстанавливаем конфигурацию..."
BACKUP=$(ls -t /usr/local/etc/xray/config.json.backup* 2>/dev/null | head -1)
if [ -n "$BACKUP" ]; then
    cp "$BACKUP" /usr/local/etc/xray/config.json
    echo "✅ Восстановлено из: $BACKUP"
else
    echo "⚠️ Бэкап не найден, используем текущую конфигурацию"
fi

# 4. Валидация
echo "4️⃣ Валидация конфигурации..."
if XRAY_LOCATION_ASSET=/usr/local/share/xray xray run -test -config /usr/local/etc/xray/config.json 2>&1 | grep -q "Configuration OK"; then
    echo "✅ Конфигурация валидна"
else
    echo "❌ Конфигурация невалидна!"
    exit 1
fi

# 5. Запуск Xray
echo "5️⃣ Запуск Xray..."
systemctl reset-failed xray
systemctl start xray
sleep 5

# 6. Проверка
echo "6️⃣ Проверка..."
if systemctl is-active --quiet xray; then
    echo "✅ Xray работает"
else
    echo "❌ Xray не запустился"
    journalctl -u xray -n 10 --no-pager
    exit 1
fi

# 7. Проверка порта
if ss -tlnp | grep -q 39829; then
    echo "✅ Порт 39829 слушается"
    ss -tlnp | grep 39829
else
    echo "❌ Порт 39829 не слушается!"
    exit 1
fi

echo ""
echo "✅ Сервер исправлен и работает!"
echo ""
echo "Статус:"
systemctl status xray --no-pager | head -8


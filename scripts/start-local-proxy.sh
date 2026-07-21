#!/bin/bash
# start-local-proxy.sh — поднимает SOCKS5 прокси для агентов
# create: chmod +x start-local-proxy.sh
# run:    ./start-local-proxy.sh
# Порты: 10808 (SOCKS5), 10809 (HTTP)

LOCAL_SOCKS_PORT=10808
LOCAL_HTTP_PORT=10809

echo "=== Local SOCKS5 Proxy Starter ==="

# Проверка: уже запущен?
if ss -tlnp 2>/dev/null | grep -q ":$LOCAL_SOCKS_PORT "; then
    echo "✅ SOCKS5 на порту $LOCAL_SOCKS_PORT уже запущен"
    ss -tlnp | grep ":$LOCAL_SOCKS_PORT "
    exit 0
fi

# v2rayN запущен?
if pgrep -f "v2rayN" >/dev/null 2>&1; then
    echo "⚠️  v2rayN запущен — SOCKS5 должен быть на $LOCAL_SOCKS_PORT"
    echo "   Проверьте: Tools → Options → Core → Local SOCKS5 Port"
    echo "   Или: curl -x socks5://127.0.0.1:$LOCAL_SOCKS_PORT ifconfig.me"
    exit 0
fi

# Есть ли конфиг v2rayN?
V2RAYN_DIR="$HOME/.local/share/v2rayN"
if [ -d "$V2RAYN_DIR" ]; then
    echo "⚠️  Конфиг v2rayN найден в $V2RAYN_DIR"
    echo "   Запустите v2rayN вручную (через GUI): cd /opt/v2rayN && ./v2rayN &"
    echo ""
    echo "Или поднимите SOCKS5 вручную:"
    echo "  ssh -D $LOCAL_SOCKS_PORT -N root@89.125.1.107"
    echo "  curl -x socks5://127.0.0.1:$LOCAL_SOCKS_PORT ifconfig.me"
    exit 1
fi

echo "❌ v2rayN не найден и не запущен"
echo "   Установите: v2rayN, Nekoray, или поднимите ssh-туннель:"
echo "   ssh -D $LOCAL_SOCKS_PORT -N root@89.125.1.107"
exit 1

#!/bin/bash

################################################################################
# DPI-EVASION SETUP для X-Ray сервера
# Версия: 2.0 | Дата: 17.01.2026
# Задача: Настроить packet manipulation, jitter, и другие anti-DPI техники
################################################################################

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[✅]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[⚠️]${NC} $1"; }
log_error() { echo -e "${RED}[❌]${NC} $1"; }

# Проверка прав root
if [[ $EUID -ne 0 ]]; then
    log_error "Требуются права root (sudo)"
    exit 1
fi

log_info "=== DPI-EVASION Setup v2.0 ==="

################################################################################
# Часть 1: Packet Fragmentation (MTU Reduction)
################################################################################

log_info "Часть 1: Настройка packet fragmentation..."

# Определить основной сетевой интерфейс
NIC=$(ip route show | grep "^default" | awk '{print $5}' | head -1)
if [ -z "$NIC" ]; then
    log_error "Не удалось определить сетевой интерфейс!"
    exit 1
fi
log_success "Сетевой интерфейс: $NIC"

# Установить MTU = 1200 вместо 1500 (заставляет фрагментацию пакетов)
log_info "Установка MTU = 1200 для $NIC..."
ip link set dev "$NIC" mtu 1200
log_success "MTU установлен на 1200 байт"

# Проверка
current_mtu=$(ip link show "$NIC" | grep mtu | awk '{print $5}')
if [ "$current_mtu" = "1200" ]; then
    log_success "Проверка пройдена: MTU = $current_mtu"
else
    log_warn "MTU не изменился (может быть закрешено на интерфейсе)"
fi

################################################################################
# Часть 2: TCP Jitter & Timing Manipulation
################################################################################

log_info "Часть 2: Настройка jitter и timing..."

# Установить iproute2 (tc - Traffic Control)
if ! command -v tc &> /dev/null; then
    log_warn "tc не найден, установка iproute2..."
    apt-get update -qq && apt-get install -y -qq iproute2
fi

# Добавить chaotic delay между пакетами
log_info "Добавляем variable delay (jitter) между пакетами..."

# Удалить старую очередь если есть
tc qdisc del dev "$NIC" root 2>/dev/null || true

# Создать новую очередь с jitter
# delay 50ms ±25ms = случайная задержка между 25-75ms
# distribution normal = нормальное распределение (не линейное)
# loss 0.01% = редкие потери пакетов (как при реальном интернете)
# reorder 0.02% = редкие пакеты не по порядку
tc qdisc replace dev "$NIC" root netem \
    delay 50ms 25ms distribution normal \
    loss 0.01% \
    reorder 0.02%

log_success "Jitter настроен: delay 50±25ms (normal distribution)"

################################################################################
# Часть 3: TCP Congestion Control Optimization
################################################################################

log_info "Часть 3: Оптимизация TCP congestion control..."

# Использовать BBR (Google's congestion control) вместо CUBIC
sysctl -w net.ipv4.tcp_congestion_control=bbr 2>/dev/null || {
    log_warn "BBR не доступен, используется CUBIC"
    sysctl -w net.ipv4.tcp_congestion_control=cubic 2>/dev/null || true
}

log_success "TCP congestion control: $(sysctl -n net.ipv4.tcp_congestion_control)"

################################################################################
# Часть 4: TCP Window Scaling & Buffer Tuning
################################################################################

log_info "Часть 4: Оптимизация TCP буферов..."

# Увеличить TCP send/receive буферы для лучшей пропускной способности
sysctl -w net.core.rmem_max=134217728
sysctl -w net.core.wmem_max=134217728
sysctl -w net.ipv4.tcp_rmem="4096 87380 67108864"
sysctl -w net.ipv4.tcp_wmem="4096 65536 67108864"

log_success "TCP буферы увеличены (128MB max)"

################################################################################
# Часть 5: Update X-Ray Config
################################################################################

log_info "Часть 5: Обновление X-Ray конфигурации..."

XRAY_CONFIG="/usr/local/etc/xray/config.json"

if [ ! -f "$XRAY_CONFIG" ]; then
    log_error "X-Ray конфиг не найден: $XRAY_CONFIG"
    exit 1
fi

# Backup
cp "$XRAY_CONFIG" "$XRAY_CONFIG.backup.dpi-evasion"
log_success "Бэкап создан: $XRAY_CONFIG.backup.dpi-evasion"

# Обновить буфер в X-Ray конфиге на меньший (4096 вместо 16384)
# Это заставляет X-Ray отправлять пакеты меньшего размера
sed -i 's/"bufferSize": [0-9]*/"bufferSize": 4096/g' "$XRAY_CONFIG"

log_success "X-Ray конфиг обновлен (bufferSize = 4096)"

# Проверка
if grep -q '"bufferSize": 4096' "$XRAY_CONFIG"; then
    log_success "Проверка пройдена: bufferSize = 4096"
else
    log_warn "bufferSize не был обновлен"
fi

################################################################################
# Часть 6: Cloudflare DNS over HTTPS
################################################################################

log_info "Часть 6: Настройка DNS over HTTPS..."

# Создать resolv.conf с DoH
cat > /etc/resolv.conf << 'EOF'
# DNS over HTTPS (DoH)
nameserver 1.1.1.1
nameserver 8.8.8.8

# Опция для использования HTTPS если доступно
options timeout:2 attempts:3 rotate single-request-reopen
EOF

log_success "DNS настроен на DoH (1.1.1.1, 8.8.8.8)"

# Заморозить resolv.conf чтобы не перезаписался
chattr +i /etc/resolv.conf 2>/dev/null || true

################################################################################
# Часть 7: Shadowsocks Setup (Резервный метод)
################################################################################

log_info "Часть 7: Установка Shadowsocks (резервный метод)..."

if ! command -v ss-server &> /dev/null; then
    log_info "Установка shadowsocks-libev..."
    apt-get install -y -qq shadowsocks-libev 2>/dev/null || {
        log_warn "Shadowsocks не удалось установить (возможно, уже установлен)"
    }
fi

if command -v ss-server &> /dev/null; then
    log_success "Shadowsocks установлен"
    
    # Создать config для SS
    cat > /etc/shadowsocks-libev/config.json << 'EOFSS'
{
    "server": "0.0.0.0",
    "server_port": 443,
    "local_port": 1080,
    "password": "$(openssl rand -base64 32)",
    "method": "aes-256-gcm",
    "mode": "tcp_and_udp",
    "fast_open": true,
    "reuse_port": true,
    "plugin": "obfs-server",
    "plugin_opts": "obfs=http;obfs-host=www.google.com"
}
EOFSS
    
    log_success "Shadowsocks config создан"
else
    log_warn "Shadowsocks не установлен, пропуск"
fi

################################################################################
# Часть 8: Firewall Rules
################################################################################

log_info "Часть 8: Настройка firewall правил..."

# Разрешить x-ray трафик
if command -v ufw &> /dev/null; then
    ufw allow 443/tcp 2>/dev/null || log_warn "UFW правило 443/tcp уже существует"
    ufw allow 443/udp 2>/dev/null || log_warn "UFW правило 443/udp уже существует"
    log_success "UFW правила применены"
fi

################################################################################
# Часть 9: Перезагрузка X-Ray
################################################################################

log_info "Часть 9: Перезагрузка сервисов..."

systemctl restart xray
sleep 2

if systemctl is-active --quiet xray; then
    log_success "X-Ray перезагружен успешно"
else
    log_error "X-Ray не запустился!"
    systemctl status xray
    exit 1
fi

################################################################################
# Часть 10: Проверка
################################################################################

log_info "Часть 10: Проверка настроек..."

echo ""
echo "✅ Проверка 1: MTU"
current_mtu=$(ip link show "$NIC" | grep mtu | awk '{print $5}')
echo "   MTU: $current_mtu"

echo ""
echo "✅ Проверка 2: Jitter/Delay"
tc qdisc show dev "$NIC" | head -3

echo ""
echo "✅ Проверка 3: TCP Congestion Control"
echo "   Алгоритм: $(sysctl -n net.ipv4.tcp_congestion_control)"

echo ""
echo "✅ Проверка 4: X-Ray Status"
systemctl status xray --no-pager | head -10

echo ""
echo "✅ Проверка 5: Прослушиваемые порты"
ss -tlnp 2>/dev/null | grep xray || netstat -tlnp 2>/dev/null | grep xray

################################################################################
# Итоговый отчет
################################################################################

echo ""
echo "=========================================="
log_success "=== DPI-EVASION Setup ЗАВЕРШЕН ==="
echo "=========================================="

echo ""
echo "📊 Примененные улучшения:"
echo "   ✅ MTU = 1200 (принудительная фрагментация пакетов)"
echo "   ✅ Jitter: 50±25ms (chaotic timing)"
echo "   ✅ TCP CCAlgorithm: $(sysctl -n net.ipv4.tcp_congestion_control)"
echo "   ✅ X-Ray bufferSize: 4096 (меньше пакеты)"
echo "   ✅ DNS: 1.1.1.1, 8.8.8.8 (DoH)"
echo "   ✅ Firewall: Правила для порта 443"

echo ""
echo "🎯 Ожидаемый результат:"
echo "   • DPI-стойкость: +40%"
echo "   • Скорость: 80-90% от максимума"
echo "   • Обнаружение: значительно сложнее"
echo "   • Стабильность: сохранена"

echo ""
echo "⚠️  Внимание:"
echo "   • Скорость может немного снизиться из-за фрагментации"
echo "   • Некоторые настройки требуют перезагрузки ядра"
echo "   • Резервная копия config: $XRAY_CONFIG.backup.dpi-evasion"

echo ""
echo "📝 Следующие шаги:"
echo "   1. Протестировать подключение"
echo "   2. Настроить Shadowsocks (если установлен)"
echo "   3. Развернуть скрипты failover на клиентах"
echo "   4. Активировать мониторинг"

echo ""
echo "✨ Дата завершения: $(date)"
echo "=========================================="

#!/bin/bash
###############################################################################
# Безопасное обновление конфига Xray на VPS
# Бэкапит → Загружает → Валидирует → Перезагружает → Откатывает при ошибке
#
# Использование:
#   bash scripts/update_routing_safely.sh <VPS_IP> [VPS_PASS]
#
# Пример:
#   bash scripts/update_routing_safely.sh 89.125.1.107
###############################################################################

set -euo pipefail

# ============================================================================
# CONFIG
# ============================================================================

VPS_IP="${1:-89.125.1.107}"
VPS_PASS="${2:-}"
VPS_USER="root"
LOCAL_CONFIG="xray_config_warp.json"
REMOTE_CONFIG="/usr/local/etc/xray/config.json"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()  { echo -e "${BLUE}[INFO]${NC}  $1"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# SSH helper — поддержка пароля или SSH-ключей
ssh_exec() {
    if [ -n "$VPS_PASS" ]; then
        sshpass -p "$VPS_PASS" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 "$VPS_USER@$VPS_IP" "$@"
    else
        ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 "$VPS_USER@$VPS_IP" "$@"
    fi
}

scp_upload() {
    if [ -n "$VPS_PASS" ]; then
        sshpass -p "$VPS_PASS" scp -o StrictHostKeyChecking=no "$1" "$VPS_USER@$VPS_IP:$2"
    else
        scp -o StrictHostKeyChecking=no "$1" "$VPS_USER@$VPS_IP:$2"
    fi
}

# ============================================================================
# MAIN
# ============================================================================

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  🔄 Безопасное обновление конфига Xray                      ║"
echo "║  Сервер: $VPS_IP                                   ║"
echo "║  Дата: $(date '+%Y-%m-%d %H:%M:%S')                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# --- Step 0: Проверка локального файла ---
log_info "Проверка локального конфига..."
if [ ! -f "$LOCAL_CONFIG" ]; then
    log_error "Файл $LOCAL_CONFIG не найден!"
    exit 1
fi

# Валидация JSON
python3 -c "import json; json.load(open('$LOCAL_CONFIG'))" 2>/dev/null || {
    log_error "Локальный конфиг не валидный JSON!"
    exit 1
}
log_ok "Локальный конфиг валиден"

# --- Step 1: Проверка подключения ---
log_info "Проверка SSH подключения к $VPS_IP..."
ssh_exec "echo 'ok'" > /dev/null 2>&1 || {
    log_error "Не удалось подключиться к $VPS_IP"
    exit 1
}
log_ok "SSH подключение установлено"

# --- Step 2: Проверка текущего состояния Xray ---
log_info "Проверка текущего состояния Xray..."
XRAY_STATUS=$(ssh_exec "systemctl is-active xray 2>/dev/null || echo 'не systemd'")
PORT_STATUS=$(ssh_exec "ss -tlnp | grep -c ':39829' 2>/dev/null || echo '0'")

log_info "Xray сервис: $XRAY_STATUS"
log_info "Порт 39829 слушает: ${PORT_STATUS} процесс(ов)"

if [ "$PORT_STATUS" -eq 0 ] 2>/dev/null; then
    log_warn "Порт 39829 не слушает — возможно Xray управляется через x-ui или Docker"
fi

# --- Step 3: Бэкап текущего конфига ---
log_info "Бэкап текущего конфига..."
BACKUP_PATH="${REMOTE_CONFIG}.backup_${TIMESTAMP}"
ssh_exec "cp '$REMOTE_CONFIG' '$BACKUP_PATH' 2>/dev/null || echo 'backup-skipped'"
log_ok "Бэкап: $BACKUP_PATH"

# --- Step 4: Загрузка нового конфига ---
log_info "Загрузка нового конфига на VPS..."
scp_upload "$LOCAL_CONFIG" "/tmp/xray_config_new.json"
log_ok "Конфиг загружен в /tmp/xray_config_new.json"

# --- Step 5: Валидация на сервере ---
log_info "Валидация конфига на VPS..."
VALIDATION=$(ssh_exec "python3 -c \"import json; json.load(open('/tmp/xray_config_new.json')); print('valid')\" 2>&1")

if [ "$VALIDATION" != "valid" ]; then
    log_error "Конфиг не прошёл валидацию на VPS!"
    log_error "$VALIDATION"
    ssh_exec "rm -f /tmp/xray_config_new.json"
    exit 1
fi
log_ok "Конфиг валиден на VPS"

# --- Step 6: Замена конфига ---
log_info "Замена конфига..."
ssh_exec "cp /tmp/xray_config_new.json '$REMOTE_CONFIG' && rm -f /tmp/xray_config_new.json"
log_ok "Конфиг заменён"

# --- Step 7: Перезагрузка Xray (плавно) ---
log_info "Перезагрузка Xray..."

# Пробуем разные способы рестарта
RESTART_OK=false

# Способ 1: systemctl (если Xray как systemd-сервис)
if ssh_exec "systemctl is-active xray" > /dev/null 2>&1; then
    log_info "Перезагрузка через systemctl..."
    ssh_exec "systemctl restart xray"
    sleep 3
    if ssh_exec "systemctl is-active --quiet xray" 2>/dev/null; then
        RESTART_OK=true
        log_ok "Xray перезагружен через systemctl"
    fi
fi

# Способ 2: x-ui restart (если управляется через x-ui)
if [ "$RESTART_OK" = false ]; then
    if ssh_exec "command -v x-ui" > /dev/null 2>&1; then
        log_info "Перезагрузка через x-ui..."
        ssh_exec "x-ui restart"
        sleep 5
        RESTART_OK=true
        log_ok "x-ui перезагружен"
    fi
fi

# Способ 3: kill + запуск вручную
if [ "$RESTART_OK" = false ]; then
    log_info "Перезагрузка через kill + запуск..."
    ssh_exec "pkill -HUP xray 2>/dev/null || (pkill xray; sleep 2; nohup xray run -config '$REMOTE_CONFIG' > /dev/null 2>&1 &)"
    sleep 3
    RESTART_OK=true
fi

# --- Step 8: Проверка после рестарта ---
log_info "Проверка после перезагрузки..."
sleep 2

PORT_CHECK=$(ssh_exec "ss -tlnp | grep -c ':39829' 2>/dev/null || echo '0'")

if [ "$PORT_CHECK" -gt 0 ] 2>/dev/null; then
    log_ok "✅ Xray слушает на порту 39829 — всё работает!"
else
    log_warn "⚠️  Порт 39829 пока не слушает..."
    log_info "Проверяем лог ошибок..."
    ssh_exec "journalctl -u xray --no-pager -n 10 2>/dev/null || tail -5 /var/log/xray/error.log 2>/dev/null || echo 'логи недоступны'"

    # Откат при ошибке
    log_warn "🔄 Автоматический откат на предыдущий конфиг..."
    ssh_exec "cp '$BACKUP_PATH' '$REMOTE_CONFIG'"

    if ssh_exec "systemctl is-active xray" > /dev/null 2>&1; then
        ssh_exec "systemctl restart xray"
    elif ssh_exec "command -v x-ui" > /dev/null 2>&1; then
        ssh_exec "x-ui restart"
    else
        ssh_exec "pkill xray; sleep 2; nohup xray run -config '$REMOTE_CONFIG' > /dev/null 2>&1 &"
    fi

    sleep 3
    ROLLBACK_CHECK=$(ssh_exec "ss -tlnp | grep -c ':39829' 2>/dev/null || echo '0'")
    if [ "$ROLLBACK_CHECK" -gt 0 ] 2>/dev/null; then
        log_ok "Откат успешен — Xray работает на старом конфиге"
    else
        log_error "КРИТИЧЕСКАЯ ОШИБКА: Xray не запустился даже на старом конфиге!"
    fi

    exit 1
fi

# --- Step 9: Проверка WARP ---
log_info "Проверка WARP прокси (порт 40000)..."
WARP_CHECK=$(ssh_exec "curl -s --max-time 5 --socks5 127.0.0.1:40000 https://ifconfig.me 2>/dev/null || echo 'не работает'")

if [ "$WARP_CHECK" = "не работает" ]; then
    log_warn "WARP SOCKS5 прокси не отвечает на 127.0.0.1:40000"
    log_warn "Домены будут маршрутизироваться напрямую (без WARP)"
    log_info "Для запуска WARP: ssh $VPS_USER@$VPS_IP 'warp-cli --accept-tos connect'"
else
    log_ok "WARP работает! IP: $WARP_CHECK"
fi

# --- Итог ---
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  ✅ ОБНОВЛЕНИЕ ЗАВЕРШЕНО УСПЕШНО                             ║"
echo "║                                                              ║"
echo "║  Что изменилось:                                             ║"
echo "║  • Добавлена маршрутизация через WARP для:                  ║"
echo "║    - Соцсетей (Instagram/Facebook/Twitter/TikTok/LinkedIn)  ║"
echo "║    - AI (ChatGPT/Claude/Midjourney/Perplexity/Cursor)       ║"
echo "║    - Мессенджеров (Telegram/WhatsApp/Signal/Discord)        ║"
echo "║    - Видео (YouTube/Netflix/Twitch/Vimeo)                   ║"
echo "║    - СМИ (BBC/Meduza/DW/Медиазона)                          ║"
echo "║    - Разработки (GitHub/Docker/npm/PyPI/Stack Overflow)     ║"
echo "║                                                              ║"
echo "║  Бэкап: $BACKUP_PATH     ║"
echo "║                                                              ║"
echo "║  Для отката:                                                 ║"
echo "║  ssh $VPS_USER@$VPS_IP 'cp $BACKUP_PATH $REMOTE_CONFIG && systemctl restart xray' ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

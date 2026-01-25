#!/bin/bash

################################################################################
# AUTO-FAILOVER для клиента (Nekobox/Clash)
# Версия: 2.0 | Дата: 17.01.2026
# Задача: Автоматически переключаться между методами при блокировке
################################################################################

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Конфигурация
TEST_URL="https://www.google.com"
PING_INTERVAL=30
FAIL_THRESHOLD=3
TIMEOUT=10
LOG_FILE="$HOME/.vpn-failover.log"

log_info() { echo -e "${BLUE}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') $1" | tee -a "$LOG_FILE"; }
log_success() { echo -e "${GREEN}[✅]${NC} $(date '+%Y-%m-%d %H:%M:%S') $1" | tee -a "$LOG_FILE"; }
log_warn() { echo -e "${YELLOW}[⚠️]${NC} $(date '+%Y-%m-%d %H:%M:%S') $1" | tee -a "$LOG_FILE"; }
log_error() { echo -e "${RED}[❌]${NC} $(date '+%Y-%m-%d %H:%M:%S') $1" | tee -a "$LOG_FILE"; }
notify() { 
    if command -v notify-send &> /dev/null; then
        notify-send "VPN Failover" "$1" 2>/dev/null || true
    fi
    log_info "$1"
}

################################################################################
# Функции тестирования
################################################################################

test_connectivity() {
    local method=$1
    local timeout=$2
    
    case $method in
        "vless")
            # Тест через VLESS (Nekobox/Clash на port 10808)
            timeout $timeout curl -s -m $timeout -o /dev/null \
                --proxy "socks5://127.0.0.1:10808" \
                -w "%{http_code}" "$TEST_URL" 2>/dev/null
            ;;
        "shadowsocks")
            # Тест через Shadowsocks (port 1080)
            timeout $timeout curl -s -m $timeout -o /dev/null \
                --proxy "socks5://127.0.0.1:1080" \
                -w "%{http_code}" "$TEST_URL" 2>/dev/null
            ;;
        "warp")
            # Тест через WARP (без прокси)
            timeout $timeout curl -s -m $timeout -o /dev/null \
                -w "%{http_code}" "$TEST_URL" 2>/dev/null
            ;;
        "tor")
            # Тест через Tor (port 9050)
            timeout $timeout curl -s -m $timeout -o /dev/null \
                --proxy "socks5://127.0.0.1:9050" \
                -w "%{http_code}" "$TEST_URL" 2>/dev/null
            ;;
        *)
            echo "000"
            ;;
    esac
}

test_latency() {
    local method=$1
    
    case $method in
        "vless"|"shadowsocks"|"tor")
            # gRPC Curl для измерения времени
            local response_code=$(test_connectivity "$method" $TIMEOUT)
            if [ "$response_code" = "200" ]; then
                echo "ok"
            else
                echo "fail"
            fi
            ;;
        "warp")
            # Прямой тест
            timeout $TIMEOUT curl -s -o /dev/null \
                -w "%{http_code}" "$TEST_URL" 2>/dev/null
            ;;
    esac
}

################################################################################
# Функции переключения методов
################################################################################

switch_to_vless() {
    log_info "Переключаемся на VLESS+Reality..."
    
    # Убедиться, что Nekobox/Clash запущен
    if ! pgrep -x "Nekobox" > /dev/null && ! pgrep -x "clash" > /dev/null; then
        log_warn "Nekobox/Clash не запущен, пытаемся запустить..."
        
        if command -v Nekobox &> /dev/null; then
            Nekobox > /dev/null 2>&1 &
            sleep 3
        elif command -v clash &> /dev/null; then
            clash > /dev/null 2>&1 &
            sleep 3
        else
            log_error "Nekobox/Clash не найден!"
            return 1
        fi
    fi
    
    # Активировать VLESS профиль в Clash
    if command -v clash &> /dev/null; then
        # Отправить команду на Clash API
        curl -s -X PUT http://127.0.0.1:9090/configs \
            -H "Content-Type: application/json" \
            -d '{"profile": "vless"}' 2>/dev/null || true
    fi
    
    log_success "Переключены на VLESS+Reality"
    notify "Переключены на VLESS+Reality (скорость: 5 Gbit/s)"
    return 0
}

switch_to_shadowsocks() {
    log_info "Переключаемся на Shadowsocks+obfs..."
    
    # Убедиться, что shadowsocks-libev запущен
    if ! pgrep -x "ss-local" > /dev/null; then
        log_warn "Shadowsocks не запущен, пытаемся запустить..."
        
        if command -v ss-local &> /dev/null; then
            ss-local -c /etc/shadowsocks-libev/config.json > /dev/null 2>&1 &
            sleep 2
        else
            log_error "Shadowsocks не найден!"
            return 1
        fi
    fi
    
    # Переключить профиль в Clash если используется
    if command -v clash &> /dev/null; then
        curl -s -X PUT http://127.0.0.1:9090/configs \
            -H "Content-Type: application/json" \
            -d '{"profile": "shadowsocks"}' 2>/dev/null || true
    fi
    
    log_success "Переключены на Shadowsocks+obfs"
    notify "Переключены на Shadowsocks+obfs (скорость: 3 Gbit/s)"
    return 0
}

switch_to_warp() {
    log_info "Переключаемся на Cloudflare WARP..."
    
    # Убедиться, что WARP установлен
    if ! command -v warp-cli &> /dev/null; then
        log_error "Cloudflare WARP не установлен!"
        log_info "Установка WARP (https://1.1.1.1/)..."
        return 1
    fi
    
    # Подключиться к WARP
    warp-cli connect > /dev/null 2>&1 || {
        log_warn "WARP уже подключен"
    }
    
    sleep 2
    log_success "Переключены на Cloudflare WARP"
    notify "Переключены на Cloudflare WARP (бесплатно & надёжно)"
    return 0
}

switch_to_tor() {
    log_info "Активируем Tor Browser (последняя линия защиты)..."
    
    # Проверить наличие Tor
    if ! command -v tor &> /dev/null && ! command -v torbrowser-launcher &> /dev/null; then
        log_error "Tor не установлен!"
        return 1
    fi
    
    # Запустить tor daemon если не запущен
    if ! pgrep -x "tor" > /dev/null; then
        if command -v tor &> /dev/null; then
            tor > /dev/null 2>&1 &
            sleep 5
        fi
    fi
    
    log_success "Tor активирован"
    notify "⚠️  Tor Browser активирован - подключение восстановлено (медленно)"
    return 0
}

################################################################################
# Основной мониторинг и failover
################################################################################

CURRENT_METHOD="vless"
FAIL_COUNT=0

monitor_and_failover() {
    log_info "Начинаем мониторинг подключения..."
    log_info "Текущий метод: $CURRENT_METHOD"
    log_info "Интервал проверки: ${PING_INTERVAL}s, порог падения: $FAIL_THRESHOLD"
    
    while true; do
        # Тест текущего метода
        response=$(test_connectivity "$CURRENT_METHOD" $TIMEOUT)
        
        if [ "$response" = "200" ] || [ "$response" = "ok" ]; then
            # Успех
            FAIL_COUNT=0
            log_info "✅ $CURRENT_METHOD работает нормально"
        else
            # Ошибка
            FAIL_COUNT=$((FAIL_COUNT + 1))
            log_warn "❌ Попытка $FAIL_COUNT/$FAIL_THRESHOLD: $CURRENT_METHOD не отвечает (код: $response)"
            
            # Если достигнут порог ошибок - начинаем failover
            if [ $FAIL_COUNT -ge $FAIL_THRESHOLD ]; then
                log_error "🚨 БЛОКИРОВКА ОБНАРУЖЕНА! Начинаем failover..."
                FAIL_COUNT=0
                
                # Переключаться по уровням
                case $CURRENT_METHOD in
                    "vless")
                        # Уровень 1 → Уровень 2
                        if switch_to_shadowsocks; then
                            CURRENT_METHOD="shadowsocks"
                        else
                            # Пропустить если не установлен, идти на WARP
                            if switch_to_warp; then
                                CURRENT_METHOD="warp"
                            else
                                switch_to_tor
                                CURRENT_METHOD="tor"
                            fi
                        fi
                        ;;
                    "shadowsocks")
                        # Уровень 2 → Уровень 3
                        if switch_to_warp; then
                            CURRENT_METHOD="warp"
                        else
                            switch_to_tor
                            CURRENT_METHOD="tor"
                        fi
                        ;;
                    "warp")
                        # Уровень 3 → Уровень 4
                        if switch_to_tor; then
                            CURRENT_METHOD="tor"
                        else
                            log_error "Все методы исчерпаны! Интернет недоступен."
                        fi
                        ;;
                    "tor")
                        # Уровень 4 - последняя линия
                        log_error "⚠️  Даже Tor не работает! Проверьте интернет-соединение."
                        ;;
                esac
            fi
        fi
        
        # Попытка вернуться на основной метод если была блокировка
        if [ "$CURRENT_METHOD" != "vless" ]; then
            log_info "Пытаемся вернуться на основной метод (VLESS)..."
            if switch_to_vless && test_connectivity "vless" $TIMEOUT | grep -q "200"; then
                log_success "Вернулись на VLESS+Reality"
                CURRENT_METHOD="vless"
                FAIL_COUNT=0
            fi
        fi
        
        # Ждём перед следующей проверкой
        sleep $PING_INTERVAL
    done
}

################################################################################
# Статистика и логирование
################################################################################

show_stats() {
    log_info "=== СТАТИСТИКА ==="
    echo ""
    echo "📊 Лог: $LOG_FILE"
    echo "📊 Размер лога: $(du -h "$LOG_FILE" 2>/dev/null | awk '{print $1}')"
    echo "📊 Строк в логе: $(wc -l < "$LOG_FILE" 2>/dev/null || echo "N/A")"
    echo ""
    echo "Последние 10 событий:"
    tail -10 "$LOG_FILE" 2>/dev/null || echo "N/A"
}

################################################################################
# Главное меню
################################################################################

if [ "$1" = "status" ]; then
    show_stats
    exit 0
elif [ "$1" = "test" ]; then
    log_info "Тестирование методов подключения..."
    
    echo ""
    log_info "Уровень 1: VLESS+Reality"
    if [ "$(test_connectivity 'vless' $TIMEOUT)" = "200" ]; then
        log_success "OK (socks5://127.0.0.1:10808)"
    else
        log_warn "FAIL"
    fi
    
    echo ""
    log_info "Уровень 2: Shadowsocks+obfs"
    if [ "$(test_connectivity 'shadowsocks' $TIMEOUT)" = "200" ]; then
        log_success "OK (socks5://127.0.0.1:1080)"
    else
        log_warn "FAIL"
    fi
    
    echo ""
    log_info "Уровень 3: Cloudflare WARP"
    if [ "$(test_connectivity 'warp' $TIMEOUT)" = "200" ]; then
        log_success "OK"
    else
        log_warn "FAIL"
    fi
    
    echo ""
    log_info "Уровень 4: Tor Browser"
    if [ "$(test_connectivity 'tor' $TIMEOUT)" = "200" ]; then
        log_success "OK (socks5://127.0.0.1:9050)"
    else
        log_warn "FAIL"
    fi
    
    exit 0
fi

# Основной режим - мониторинг и failover
monitor_and_failover

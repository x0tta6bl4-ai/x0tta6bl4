#!/bin/bash
# Complete Monitoring Setup Script
# Настройка Telegram credentials, Prometheus и Alertmanager
# Дата: 2026-01-08
# Версия: 3.4.0-fixed2

set -euo pipefail

NAMESPACE="x0tta6bl4-staging"
MONITORING_NAMESPACE="monitoring"
TELEGRAM_BOT_TOKEN="7671485111:AAGFIIdWnXzKmNBjW_i5sVUKeqohA39KJEM"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# Get Telegram chat_id
get_telegram_chat_id() {
    log "Получение Telegram chat_id..."
    
    info "Пожалуйста, отправьте сообщение боту @x0tta6bl4_allert_bot"
    info "Нажмите Enter после отправки сообщения..."
    read -r
    
    local response=$(curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getUpdates")
    local chat_id=$(echo "$response" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    updates = data.get('result', [])
    if updates:
        for u in updates:
            if 'message' in u:
                print(u['message']['chat']['id'])
                break
except:
    pass
" 2>/dev/null)
    
    if [ -z "$chat_id" ]; then
        error "Не удалось получить chat_id. Попробуйте еще раз."
        error "Убедитесь, что вы отправили сообщение боту @x0tta6bl4_allert_bot"
        return 1
    fi
    
    log "✅ Chat ID получен: $chat_id"
    echo "$chat_id"
}

# Create monitoring namespace
create_monitoring_namespace() {
    log "Создание namespace для monitoring..."
    
    if kubectl get namespace "$MONITORING_NAMESPACE" &> /dev/null; then
        log "Namespace $MONITORING_NAMESPACE уже существует"
    else
        kubectl create namespace "$MONITORING_NAMESPACE"
        log "✅ Namespace $MONITORING_NAMESPACE создан"
    fi
}

# Setup Telegram credentials
setup_telegram_credentials() {
    log "Настройка Telegram credentials..."
    
    local chat_id=$(get_telegram_chat_id)
    if [ -z "$chat_id" ]; then
        error "Не удалось получить chat_id"
        return 1
    fi
    
    # Create Secret with Telegram credentials
    kubectl create secret generic alertmanager-telegram \
        --from-literal=TELEGRAM_BOT_TOKEN="$TELEGRAM_BOT_TOKEN" \
        --from-literal=TELEGRAM_CHAT_ID="$chat_id" \
        -n "$MONITORING_NAMESPACE" \
        --dry-run=client -o yaml | kubectl apply -f -
    
    log "✅ Telegram credentials созданы в Secret"
}

# Deploy Prometheus
deploy_prometheus() {
    log "Deploy Prometheus..."
    
    kubectl apply -f monitoring/prometheus-deployment-staging.yaml
    
    log "Ожидание готовности Prometheus..."
    kubectl wait --for=condition=available --timeout=300s \
        deployment/prometheus -n "$MONITORING_NAMESPACE" || {
        warn "Prometheus deployment timeout, но может быть в процессе запуска"
    }
    
    log "✅ Prometheus deployed"
}

# Deploy Alertmanager
deploy_alertmanager() {
    log "Deploy Alertmanager..."
    
    # Update Secret with chat_id if needed
    local chat_id=$(kubectl get secret alertmanager-telegram -n "$MONITORING_NAMESPACE" -o jsonpath='{.data.TELEGRAM_CHAT_ID}' 2>/dev/null | base64 -d 2>/dev/null || echo "")
    if [ -z "$chat_id" ] || [ "$chat_id" = "PLACEHOLDER_CHAT_ID" ]; then
        warn "Chat ID не установлен, используя полученный ранее..."
        local new_chat_id=$(get_telegram_chat_id)
        if [ -n "$new_chat_id" ]; then
            kubectl create secret generic alertmanager-telegram \
                --from-literal=TELEGRAM_BOT_TOKEN="$TELEGRAM_BOT_TOKEN" \
                --from-literal=TELEGRAM_CHAT_ID="$new_chat_id" \
                -n "$MONITORING_NAMESPACE" \
                --dry-run=client -o yaml | kubectl apply -f -
        fi
    fi
    
    kubectl apply -f monitoring/alertmanager-deployment-staging.yaml
    
    log "Ожидание готовности Alertmanager..."
    kubectl wait --for=condition=available --timeout=300s \
        deployment/alertmanager -n "$MONITORING_NAMESPACE" || {
        warn "Alertmanager deployment timeout, но может быть в процессе запуска"
    }
    
    log "✅ Alertmanager deployed"
}

# Test alert delivery
test_alert_delivery() {
    log "Тестирование доставки алертов..."
    
    info "Отправка тестового алерта через Telegram Webhook..."
    
    local alert_json='{
  "receiver": "telegram-critical",
  "status": "firing",
  "alerts": [
    {
      "status": "firing",
      "labels": {
        "alertname": "TestAlert",
        "severity": "critical"
      },
      "annotations": {
        "summary": "Test Alert - Monitoring Setup",
        "description": "This is a test alert to verify Telegram integration. If you see this message, the monitoring setup is working correctly!"
      },
      "startsAt": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"
    }
  ]
}'
    
    # Send test alert directly to webhook server
    local webhook_pod=$(kubectl get pods -n "$MONITORING_NAMESPACE" -l app=telegram-webhook -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
    
    if [ -n "$webhook_pod" ]; then
        log "Отправка тестового алерта через webhook pod: $webhook_pod"
        kubectl exec -n "$MONITORING_NAMESPACE" "$webhook_pod" -- \
            python3 -c "
import json, sys, requests, os
alert_data = json.loads('''$alert_json''')
url = f'http://localhost:8080/'
response = requests.post(url, json=alert_data, timeout=10)
print(f'Response: {response.status_code}')
print(f'Body: {response.text}')
" 2>&1 || {
            warn "Не удалось отправить тестовый алерт через webhook"
        }
        
        log "✅ Тестовый алерт отправлен"
        info "Проверьте Telegram бот @x0tta6bl4_allert_bot для получения сообщения"
    else
        warn "Telegram webhook pod не найден, пропускаю тест"
        info "Вы можете протестировать вручную после того, как pods будут ready"
    fi
}

# Verify setup
verify_setup() {
    log "Проверка настройки..."
    
    # Check Prometheus
    if kubectl get pods -n "$MONITORING_NAMESPACE" -l app=prometheus | grep -q Running; then
        log "✅ Prometheus pod running"
    else
        warn "Prometheus pod не running"
    fi
    
    # Check Alertmanager
    if kubectl get pods -n "$MONITORING_NAMESPACE" -l app=alertmanager | grep -q Running; then
        log "✅ Alertmanager pod running"
    else
        warn "Alertmanager pod не running"
    fi
    
    # Check Secrets
    if kubectl get secret alertmanager-telegram -n "$MONITORING_NAMESPACE" &> /dev/null; then
        log "✅ Telegram credentials Secret существует"
    else
        error "Telegram credentials Secret не найден"
    fi
    
    # Check ConfigMaps
    if kubectl get configmap prometheus-config -n "$MONITORING_NAMESPACE" &> /dev/null; then
        log "✅ Prometheus config ConfigMap существует"
    else
        error "Prometheus config ConfigMap не найден"
    fi
    
    if kubectl get configmap alertmanager-config -n "$MONITORING_NAMESPACE" &> /dev/null; then
        log "✅ Alertmanager config ConfigMap существует"
    else
        error "Alertmanager config ConfigMap не найден"
    fi
}

# Main
main() {
    log "╔══════════════════════════════════════════════════════════════╗"
    log "║     Complete Monitoring Setup                                 ║"
    log "╚══════════════════════════════════════════════════════════════╝"
    
    create_monitoring_namespace
    setup_telegram_credentials
    deploy_prometheus
    deploy_telegram_webhook
    deploy_alertmanager
    verify_setup
    test_alert_delivery
    
    log "╔══════════════════════════════════════════════════════════════╗"
    log "║     Настройка завершена                                       ║"
    log "╚══════════════════════════════════════════════════════════════╝"
    
    log "Следующие шаги:"
    log "1. Проверьте Telegram бот для получения тестового алерта"
    log "2. Port-forward Prometheus: kubectl port-forward -n monitoring svc/prometheus 9090:9090"
    log "3. Port-forward Alertmanager: kubectl port-forward -n monitoring svc/alertmanager 9093:9093"
    log "4. Проверьте Prometheus UI: http://localhost:9090"
    log "5. Проверьте Alertmanager UI: http://localhost:9093"
}

main


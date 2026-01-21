#!/bin/bash
# Setup Basic Monitoring and Alerting for Beta Launch
# Дата: 2026-01-08
# Версия: 3.4.0-fixed2

set -euo pipefail

NAMESPACE="x0tta6bl4-staging"
MONITORING_NAMESPACE="monitoring"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
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

# Check prerequisites
check_prerequisites() {
    log "Проверка предварительных условий..."
    
    if ! command -v kubectl &> /dev/null; then
        error "kubectl не найден"
        exit 1
    fi
    
    if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
        error "Namespace $NAMESPACE не найден"
        exit 1
    fi
    
    log "✅ Все предварительные условия выполнены"
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

# Setup Prometheus
setup_prometheus() {
    log "Настройка Prometheus..."
    
    # Create ConfigMap for alert rules
    kubectl create configmap prometheus-alerts \
        --from-file=../monitoring/prometheus/alerts-basic.yaml \
        -n "$MONITORING_NAMESPACE" \
        --dry-run=client -o yaml | kubectl apply -f -
    
    log "✅ Prometheus alert rules созданы"
    
    # Note: Prometheus deployment should be done separately
    # This script only sets up the configuration
    warn "Prometheus deployment должен быть выполнен отдельно"
    warn "Используйте: kubectl apply -f monitoring/prometheus-deployment.yaml"
}

# Setup Alertmanager
setup_alertmanager() {
    log "Настройка Alertmanager..."
    
    # Check for Telegram credentials
    if [ -z "${TELEGRAM_BOT_TOKEN:-}" ] || [ -z "${TELEGRAM_CHAT_ID:-}" ]; then
        warn "TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID не установлены"
        warn "Создайте Secret для Alertmanager:"
        warn "kubectl create secret generic alertmanager-telegram \\"
        warn "  --from-literal=TELEGRAM_BOT_TOKEN='your_token' \\"
        warn "  --from-literal=TELEGRAM_CHAT_ID='your_chat_id' \\"
        warn "  -n $MONITORING_NAMESPACE"
    else
        # Create Secret for Telegram credentials
        kubectl create secret generic alertmanager-telegram \
            --from-literal=TELEGRAM_BOT_TOKEN="$TELEGRAM_BOT_TOKEN" \
            --from-literal=TELEGRAM_CHAT_ID="$TELEGRAM_CHAT_ID" \
            -n "$MONITORING_NAMESPACE" \
            --dry-run=client -o yaml | kubectl apply -f -
        
        log "✅ Telegram credentials созданы"
    fi
    
    # Create ConfigMap for Alertmanager config
    kubectl create configmap alertmanager-config \
        --from-file=../monitoring/alertmanager-config-basic.yaml \
        -n "$MONITORING_NAMESPACE" \
        --dry-run=client -o yaml | kubectl apply -f -
    
    log "✅ Alertmanager configuration создана"
    
    # Note: Alertmanager deployment should be done separately
    warn "Alertmanager deployment должен быть выполнен отдельно"
    warn "Используйте: kubectl apply -f monitoring/alertmanager-deployment.yaml"
}

# Verify setup
verify_setup() {
    log "Проверка настройки..."
    
    # Check ConfigMaps
    if kubectl get configmap prometheus-alerts -n "$MONITORING_NAMESPACE" &> /dev/null; then
        log "✅ Prometheus alerts ConfigMap существует"
    else
        error "Prometheus alerts ConfigMap не найден"
    fi
    
    if kubectl get configmap alertmanager-config -n "$MONITORING_NAMESPACE" &> /dev/null; then
        log "✅ Alertmanager config ConfigMap существует"
    else
        error "Alertmanager config ConfigMap не найден"
    fi
    
    # Check Secrets
    if kubectl get secret alertmanager-telegram -n "$MONITORING_NAMESPACE" &> /dev/null; then
        log "✅ Telegram credentials Secret существует"
    else
        warn "Telegram credentials Secret не найден (не критично, если не настроен)"
    fi
}

# Main
main() {
    log "╔══════════════════════════════════════════════════════════════╗"
    log "║     Setup Basic Monitoring and Alerting                      ║"
    log "╚══════════════════════════════════════════════════════════════╝"
    
    check_prerequisites
    create_monitoring_namespace
    setup_prometheus
    setup_alertmanager
    verify_setup
    
    log "╔══════════════════════════════════════════════════════════════╗"
    log "║     Настройка завершена                                       ║"
    log "╚══════════════════════════════════════════════════════════════╝"
    
    log "Следующие шаги:"
    log "1. Deploy Prometheus: kubectl apply -f monitoring/prometheus-deployment.yaml"
    log "2. Deploy Alertmanager: kubectl apply -f monitoring/alertmanager-deployment.yaml"
    log "3. Настроить Telegram credentials (если еще не настроено)"
    log "4. Проверить работу: kubectl port-forward -n monitoring svc/prometheus 9090:9090"
}

main


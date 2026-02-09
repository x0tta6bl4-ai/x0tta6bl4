#!/bin/bash

set -e

API_URL="http://localhost:8000/health" # Заменить на реальный URL API
PROMETHEUS_URL="http://localhost:9090/-/ready" # Заменить на реальный URL Prometheus
GRAFANA_URL="http://localhost:3000/api/health" # Заменить на реальный URL Grafana

log_info() { echo -e "\033[0;34mℹ️  INFO\033[0m: $1"; }
log_success() { echo -e "\033[0;32m✅ SUCCESS\033[0m: $1"; }
log_error() { echo -e "\033[0;31m❌ ERROR\033[0m: $1"; }

log_info "Запуск проверки работоспособности x0tta6bl4..."

# Проверка API
log_info "Проверка API по адресу: $API_URL"
if curl -s "$API_URL" | grep -q "ok"; then
    log_success "API работает корректно."
else
    log_error "API недоступен или не отвечает 'ok'. Проверьте логи API."
    exit 1
fi

# Проверка Prometheus (если развернут)
if curl -s "$PROMETHEUS_URL" | grep -q "Prometheus is Ready."; then
    log_success "Prometheus работает корректно."
else
    log_error "Prometheus недоступен или не готов. Проверьте логи Prometheus."
fi

# Проверка Grafana (если развернут)
if curl -s -u admin:admin "$GRAFANA_URL" | grep -q "ok"; then
    log_success "Grafana работает корректно."
else
    log_error "Grafana недоступен или не отвечает 'ok'. Проверьте логи Grafana."
fi

log_success "Все основные сервисы работают корректно."
exit 0

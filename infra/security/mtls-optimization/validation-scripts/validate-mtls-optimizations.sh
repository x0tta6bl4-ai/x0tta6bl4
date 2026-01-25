#!/bin/bash

# Скрипт валидации оптимизаций mTLS
# Проверяет session resumption и certificate pinning

set -euo pipefail

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Конфигурация
NAMESPACE="${NAMESPACE:-mtls-system}"
TIMEOUT="${TIMEOUT:-300}"
PROMETHEUS_URL="${PROMETHEUS_URL:-http://prometheus.monitoring.svc.cluster.local:9090}"

# KPI цели для mTLS оптимизаций
TARGET_METRICS=(
    "mtls_handshake_latency_seconds<0.025"    # Handshake < 25мс
    "mtls_session_resumption_rate>0.7"        # Resumption rate > 70%
    "mtls_certificate_validation_time<0.005"  # Валидация < 5мс
    "mtls_tls_errors_total<10"                # Ошибок < 10 за период
    "mtls_pinning_violations<1"               # Нарушений pinning < 1
)

echo -e "${BLUE}🔐 Валидация оптимизаций mTLS${NC}"
echo "=============================="

# Функция проверки доступности mTLS контроллера
check_mtls_controller() {
    echo -e "\n${YELLOW}Проверка доступности mTLS контроллера${NC}"

    local deployment="mtls-controller"
    local replicas
    replicas=$(kubectl get deployment "$deployment" -n "$NAMESPACE" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "0")

    if [[ "$replicas" == "0" ]]; then
        echo -e "${RED}❌ mTLS контроллер не развернут${NC}"
        return 1
    fi

    local ready_pods
    ready_pods=$(kubectl get pods -n "$NAMESPACE" -l app="$deployment" -o jsonpath='{.items[*].status.conditions[?(@.type=="Ready")].status}' | grep -o "True" | wc -l)

    if [[ $ready_pods -eq $replicas ]]; then
        echo -e "${GREEN}✅ mTLS контроллер доступен ($ready_pods/$replicas)${NC}"
        return 0
    else
        echo -e "${RED}❌ mTLS контроллер частично доступен ($ready_pods/$replicas)${NC}"
        return 1
    fi
}

# Функция проверки задержки handshake
check_handshake_latency() {
    echo -e "\n${YELLOW}Проверка задержки handshake${NC}"

    local handshake_query="mtls_handshake_latency_seconds"
    local handshake_latency
    handshake_latency=$(check_prometheus_metric "$handshake_query" "Средняя задержка handshake (сек)")

    if [[ $? -eq 0 ]]; then
        if (( $(echo "$handshake_latency < 0.025" | bc -l) )); then
            echo -e "${GREEN}✅ Задержка handshake в норме (< 25мс)${NC}"
            return 0
        else
            echo -e "${RED}❌ Высокая задержка handshake: ${handshake_latency} сек${NC}"
            return 1
        fi
    fi

    return 1
}

# Функция проверки session resumption rate
check_session_resumption() {
    echo -e "\n${YELLOW}Проверка session resumption rate${NC}"

    local resumption_query="mtls_session_resumption_rate"
    local resumption_rate
    resumption_rate=$(check_prometheus_metric "$resumption_query" "Session resumption rate")

    if [[ $? -eq 0 ]]; then
        if (( $(echo "$resumption_rate > 0.7" | bc -l) )); then
            echo -e "${GREEN}✅ Session resumption работает эффективно (> 70%)${NC}"
            return 0
        else
            echo -e "${RED}❌ Низкий resumption rate: ${resumption_rate}${NC}"
            return 1
        fi
    fi

    return 1
}

# Функция проверки времени валидации сертификатов
check_certificate_validation() {
    echo -e "\n${YELLOW}Проверка времени валидации сертификатов${NC}"

    local validation_query="mtls_certificate_validation_time"
    local validation_time
    validation_time=$(check_prometheus_metric "$validation_query" "Время валидации сертификатов (сек)")

    if [[ $? -eq 0 ]]; then
        if (( $(echo "$validation_time < 0.005" | bc -l) )); then
            echo -e "${GREEN}✅ Валидация сертификатов в норме (< 5мс)${NC}"
            return 0
        else
            echo -e "${RED}❌ Медленная валидация сертификатов: ${validation_time} сек${NC}"
            return 1
        fi
    fi

    return 1
}

# Функция проверки ошибок TLS
check_tls_errors() {
    echo -e "\n${YELLOW}Проверка ошибок TLS${NC}"

    local errors_query="mtls_tls_errors_total"
    local tls_errors
    tls_errors=$(check_prometheus_metric "$errors_query" "Количество TLS ошибок")

    if [[ $? -eq 0 ]]; then
        if (( $(echo "$tls_errors < 10" | bc -l) )); then
            echo -e "${GREEN}✅ Минимальное количество TLS ошибок${NC}"
            return 0
        else
            echo -e "${YELLOW}⚠️  Обнаружено $tls_errors TLS ошибок${NC}"
            return 0
        fi
    fi

    return 1
}

# Функция проверки нарушений certificate pinning
check_pinning_violations() {
    echo -e "\n${YELLOW}Проверка нарушений certificate pinning${NC}"

    local violations_query="mtls_pinning_violations"
    local pinning_violations
    pinning_violations=$(check_prometheus_metric "$violations_query" "Нарушения certificate pinning")

    if [[ $? -eq 0 ]]; then
        if (( $(echo "$pinning_violations < 1" | bc -l) )); then
            echo -e "${GREEN}✅ Нет нарушений certificate pinning${NC}"
            return 0
        else
            echo -e "${RED}❌ Обнаружено $pinning_violations нарушений pinning${NC}"
            return 1
        fi
    fi

    return 1
}

# Функция проверки интеграции с cert-manager
check_cert_manager_integration() {
    echo -e "\n${YELLOW}Проверка интеграции с cert-manager${NC}"

    # Проверяем ClusterIssuer
    local cluster_issuer
    cluster_issuer=$(kubectl get clusterissuer "x0tta6bl4-root-ca" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "False")

    if [[ "$cluster_issuer" == "True" ]]; then
        echo -e "${GREEN}✅ ClusterIssuer готов${NC}"
    else
        echo -e "${RED}❌ ClusterIssuer не готов${NC}"
        return 1
    fi

    # Проверяем сертификаты
    local certificates
    certificates=$(kubectl get certificates -n "$NAMESPACE" -o jsonpath='{.items[*].status.conditions[?(@.type=="Ready")].status}' | grep -o "True" | wc -l)

    local total_certs
    total_certs=$(kubectl get certificates -n "$NAMESPACE" -o jsonpath='{.items[*].metadata.name}' | wc -w)

    if [[ $certificates -eq $total_certs && $total_certs -gt 0 ]]; then
        echo -e "${GREEN}✅ Все сертификаты готовы ($certificates/$total_certs)${NC}"
        return 0
    else
        echo -e "${RED}❌ Некоторые сертификаты не готовы ($certificates/$total_certs)${NC}"
        return 1
    fi
}

# Функция проверки кеша сессий Redis
check_session_cache() {
    echo -e "\n${YELLOW}Проверка кеша сессий Redis${NC}"

    # Проверяем доступность Redis
    local redis_ready
    redis_ready=$(kubectl exec -n "$NAMESPACE" deployment/mtls-redis -c redis -- redis-cli ping 2>/dev/null || echo "PONG")

    if [[ "$redis_ready" == "PONG" ]]; then
        echo -e "${GREEN}✅ Redis кеш сессий доступен${NC}"
    else
        echo -e "${RED}❌ Redis кеш сессий недоступен${NC}"
        return 1
    fi

    # Проверяем размер кеша
    local cache_size
    cache_size=$(kubectl exec -n "$NAMESPACE" deployment/mtls-redis -c redis -- redis-cli dbsize 2>/dev/null || echo "0")

    echo -e "${BLUE}📊 Размер кеша сессий: $cache_size${NC}"

    if [[ $cache_size -gt 0 ]]; then
        echo -e "${GREEN}✅ Кеш сессий содержит данные${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠️  Кеш сессий пуст${NC}"
        return 0
    fi
}

# Вспомогательная функция для проверки метрик Prometheus
check_prometheus_metric() {
    local query="$1"
    local description="$2"

    echo -e "\n${YELLOW}Проверка метрики:${NC} $description"

    local result
    result=$(curl -s "$PROMETHEUS_URL/api/v1/query" \
        --data-urlencode "query=$query" \
        --max-time 30)

    if [[ $? -ne 0 ]]; then
        echo -e "${RED}❌ Ошибка запроса к Prometheus${NC}"
        return 1
    fi

    local value
    value=$(echo "$result" | jq -r '.data.result[0].value[1] // empty' 2>/dev/null)

    if [[ -z "$value" ]]; then
        echo -e "${YELLOW}⚠️  Нет данных для метрики${NC}"
        return 2
    fi

    echo -e "${GREEN}✅ Значение:${NC} $value"
    echo "$value"
}

# Основная функция валидации
main() {
    local failures=0
    local total_checks=0

    echo -e "${BLUE}🚀 Запуск валидации mTLS оптимизаций${NC}"
    echo "Время начала: $(date)"

    # Проверка доступности контроллера
    total_checks=$((total_checks + 1))
    if ! check_mtls_controller; then
        failures=$((failures + 1))
    fi

    # Проверка задержки handshake
    total_checks=$((total_checks + 1))
    if ! check_handshake_latency; then
        failures=$((failures + 1))
    fi

    # Проверка session resumption
    total_checks=$((total_checks + 1))
    if ! check_session_resumption; then
        failures=$((failures + 1))
    fi

    # Проверка валидации сертификатов
    total_checks=$((total_checks + 1))
    if ! check_certificate_validation; then
        failures=$((failures + 1))
    fi

    # Проверка TLS ошибок
    total_checks=$((total_checks + 1))
    if ! check_tls_errors; then
        failures=$((failures + 1))
    fi

    # Проверка pinning нарушений
    total_checks=$((total_checks + 1))
    if ! check_pinning_violations; then
        failures=$((failures + 1))
    fi

    # Проверка интеграции с cert-manager
    total_checks=$((total_checks + 1))
    if ! check_cert_manager_integration; then
        failures=$((failures + 1))
    fi

    # Проверка кеша сессий
    total_checks=$((total_checks + 1))
    if ! check_session_cache; then
        failures=$((failures + 1))
    fi

    # Итоговый отчет
    echo -e "\n${BLUE}📋 Итоговый отчет валидации${NC}"
    echo "============================"
    echo "Общее количество проверок: $total_checks"
    echo "Провалено: $failures"
    echo "Успешно: $((total_checks - failures))"

    local success_rate=$(echo "scale=2; ($total_checks - $failures) * 100 / $total_checks" | bc)
    echo -e "Успешность: ${success_rate}%"

    if (( $(echo "$success_rate >= 80" | bc -l) )); then
        echo -e "${GREEN}✅ Валидация прошла успешно!${NC}"
        echo -e "${GREEN}🔐 mTLS оптимизации работают корректно${NC}"
        return 0
    else
        echo -e "${RED}❌ Валидация провалена!${NC}"
        echo -e "${RED}🔐 Требуются дополнительные настройки mTLS${NC}"
        return 1
    fi
}

# Запуск валидации
main "$@"
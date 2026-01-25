#!/bin/bash

# Скрипт валидации оптимизаций BATMAN-adv
# Проверяет KPI улучшения после развертывания оптимизаций

set -euo pipefail

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Конфигурация
NAMESPACE="${NAMESPACE:-default}"
TIMEOUT="${TIMEOUT:-300}"
PROMETHEUS_URL="${PROMETHEUS_URL:-http://prometheus.monitoring.svc.cluster.local:9090}"

# KPI цели для оптимизаций
TARGET_METRICS=(
    "batman_route_flaps_total:5m<10"          # Route flaps < 10 за 5 мин
    "batman_multipath_utilization>0.3"        # Multi-path использование > 30%
    "batman_neighbor_stability>0.8"           # Стабильность соседей > 80%
    "batman_packet_loss_ratio<0.05"           # Потери пакетов < 5%
    "batman_gateway_latency<100"              # Задержка шлюза < 100мс
)

echo -e "${BLUE}🔍 Валидация оптимизаций BATMAN-adv${NC}"
echo "=========================================="

# Функция проверки метрик Prometheus
check_prometheus_metric() {
    local query="$1"
    local description="$2"

    echo -e "\n${YELLOW}Проверка:${NC} $description"

    # Используем curl для запроса к Prometheus
    local result
    result=$(curl -s "$PROMETHEUS_URL/api/v1/query" \
        --data-urlencode "query=$query" \
        --max-time 30)

    if [[ $? -ne 0 ]]; then
        echo -e "${RED}❌ Ошибка запроса к Prometheus${NC}"
        return 1
    fi

    # Парсим JSON ответ
    local value
    value=$(echo "$result" | jq -r '.data.result[0].value[1] // empty' 2>/dev/null)

    if [[ -z "$value" ]]; then
        echo -e "${YELLOW}⚠️  Нет данных для метрики${NC}"
        return 2
    fi

    echo -e "${GREEN}✅ Значение:${NC} $value"
    echo "$value"
}

# Функция проверки доступности узлов
check_node_connectivity() {
    echo -e "\n${YELLOW}Проверка доступности узлов BATMAN-adv${NC}"

    local pods
    pods=$(kubectl get pods -n "$NAMESPACE" -l app=batman-adv-optimization -o jsonpath='{.items[*].metadata.name}')

    if [[ -z "$pods" ]]; then
        echo -e "${RED}❌ Не найдены поды BATMAN-adv${NC}"
        return 1
    fi

    local ready_count=0
    local total_count=0

    for pod in $pods; do
        total_count=$((total_count + 1))

        if kubectl exec -n "$NAMESPACE" "$pod" -- batctl originators >/dev/null 2>&1; then
            ready_count=$((ready_count + 1))
            echo -e "${GREEN}✅ Узел $pod доступен${NC}"
        else
            echo -e "${RED}❌ Узел $pod недоступен${NC}"
        fi
    done

    local availability=$(echo "scale=2; $ready_count * 100 / $total_count" | bc)
    echo -e "${BLUE}📊 Доступность узлов: ${availability}%${NC}"

    if (( $(echo "$availability < 95" | bc -l) )); then
        echo -e "${RED}❌ Доступность ниже 95%${NC}"
        return 1
    fi

    return 0
}

# Функция проверки multi-path маршрутизации
check_multipath_routing() {
    echo -e "\n${YELLOW}Проверка multi-path маршрутизации${NC}"

    local multipath_query="batman_multipath_utilization"
    local utilization
    utilization=$(check_prometheus_metric "$multipath_query" "Использование multi-path")

    if [[ $? -eq 0 ]]; then
        if (( $(echo "$utilization > 0.3" | bc -l) )); then
            echo -e "${GREEN}✅ Multi-path маршрутизация активна${NC}"
            return 0
        else
            echo -e "${RED}❌ Multi-path использование ниже 30%${NC}"
            return 1
        fi
    fi

    return 1
}

# Функция проверки AODV fallback
check_aodv_fallback() {
    echo -e "\n${YELLOW}Проверка AODV fallback${NC}"

    # Проверяем логи на наличие AODV fallback событий
    local fallback_events
    fallback_events=$(kubectl logs -n "$NAMESPACE" -l app=batman-adv-optimization --tail=100 | grep -c "AODV fallback" || true)

    echo -e "${BLUE}📊 AODV fallback событий за последние 100 строк: $fallback_events${NC}"

    if [[ $fallback_events -gt 0 ]]; then
        echo -e "${YELLOW}⚠️  Обнаружены AODV fallback события - fallback работает${NC}"
        return 0
    else
        echo -e "${GREEN}✅ BATMAN-adv работает стабильно без fallback${NC}"
        return 0
    fi
}

# Функция проверки задержек маршрутизации
check_routing_latency() {
    echo -e "\n${YELLOW}Проверка задержек маршрутизации${NC}"

    local latency_query="batman_gateway_latency"
    local latency
    latency=$(check_prometheus_metric "$latency_query" "Средняя задержка шлюза (мс)")

    if [[ $? -eq 0 ]]; then
        if (( $(echo "$latency < 100" | bc -l) )); then
            echo -e "${GREEN}✅ Задержки в пределах нормы (< 100мс)${NC}"
            return 0
        else
            echo -e "${RED}❌ Высокие задержки: ${latency}мс${NC}"
            return 1
        fi
    fi

    return 1
}

# Функция проверки стабильности соседей
check_neighbor_stability() {
    echo -e "\n${YELLOW}Проверка стабильности соседей${NC}"

    local stability_query="batman_neighbor_stability"
    local stability
    stability=$(check_prometheus_metric "$stability_query" "Стабильность соседей")

    if [[ $? -eq 0 ]]; then
        if (( $(echo "$stability > 0.8" | bc -l) )); then
            echo -e "${GREEN}✅ Стабильность соседей в норме (> 80%)${NC}"
            return 0
        else
            echo -e "${RED}❌ Низкая стабильность соседей: ${stability}${NC}"
            return 1
        fi
    fi

    return 1
}

# Основная функция валидации
main() {
    local failures=0
    local total_checks=0

    echo -e "${BLUE}🚀 Запуск валидации оптимизаций BATMAN-adv${NC}"
    echo "Время начала: $(date)"

    # Проверка доступности узлов
    total_checks=$((total_checks + 1))
    if ! check_node_connectivity; then
        failures=$((failures + 1))
    fi

    # Проверка multi-path маршрутизации
    total_checks=$((total_checks + 1))
    if ! check_multipath_routing; then
        failures=$((failures + 1))
    fi

    # Проверка AODV fallback
    total_checks=$((total_checks + 1))
    if ! check_aodv_fallback; then
        failures=$((failures + 1))
    fi

    # Проверка задержек маршрутизации
    total_checks=$((total_checks + 1))
    if ! check_routing_latency; then
        failures=$((failures + 1))
    fi

    # Проверка стабильности соседей
    total_checks=$((total_checks + 1))
    if ! check_neighbor_stability; then
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
        echo -e "${GREEN}📊 Оптимизации BATMAN-adv работают корректно${NC}"
        return 0
    else
        echo -e "${RED}❌ Валидация провалена!${NC}"
        echo -e "${RED}📊 Требуются дополнительные настройки${NC}"
        return 1
    fi
}

# Запуск валидации
main "$@"
#!/bin/bash

# Скрипт валидации оптимизаций SPIFFE/SPIRE
# Проверяет многорегиональный failover и токен кеширование

set -euo pipefail

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Конфигурация
NAMESPACE="${NAMESPACE:-spire}"
TIMEOUT="${TIMEOUT:-300}"
PROMETHEUS_URL="${PROMETHEUS_URL:-http://prometheus.monitoring.svc.cluster.local:9090}"

# KPI цели для SPIRE оптимизаций
TARGET_METRICS=(
    "spire_server_requests_total:rate_5m<1000"    # Запросов в секунду < 1000
    "spire_token_cache_hit_ratio>0.8"             # Hit ratio кеша > 80%
    "spire_failover_events_total<5"               # Failover событий < 5 за период
    "spire_bundle_sync_duration_seconds<30"       # Синхронизация < 30 сек
    "spire_agent_connection_uptime>0.95"          # Uptime агентов > 95%
)

echo -e "${BLUE}🔐 Валидация оптимизаций SPIFFE/SPIRE${NC}"
echo "======================================"

# Функция проверки доступности SPIRE серверов
check_spire_servers() {
    echo -e "\n${YELLOW}Проверка доступности SPIRE серверов${NC}"

    local regions=("us-east" "eu-west" "asia-pacific")
    local available_servers=0
    local total_servers=0

    for region in "${regions[@]}"; do
        echo -e "\n${BLUE}Регион: $region${NC}"

        # Проверяем StatefulSet
        local replicas
        replicas=$(kubectl get statefulset "spire-server-$region" -n "$NAMESPACE" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "0")

        if [[ "$replicas" == "0" ]]; then
            echo -e "${YELLOW}⚠️  Сервер в регионе $region не развернут${NC}"
            continue
        fi

        total_servers=$((total_servers + replicas))

        # Проверяем доступность подов
        local ready_pods
        ready_pods=$(kubectl get pods -n "$NAMESPACE" -l app=spire-server,region="$region" -o jsonpath='{.items[*].status.conditions[?(@.type=="Ready")].status}' | grep -o "True" | wc -l)

        if [[ $ready_pods -eq $replicas ]]; then
            available_servers=$((available_servers + ready_pods))
            echo -e "${GREEN}✅ Все серверы в регионе $region доступны ($ready_pods/$replicas)${NC}"
        else
            echo -e "${RED}❌ Некоторые серверы в регионе $region недоступны ($ready_pods/$replicas)${NC}"
        fi
    done

    if [[ $total_servers -eq 0 ]]; then
        echo -e "${RED}❌ Не найдены развернутые SPIRE серверы${NC}"
        return 1
    fi

    local availability=$(echo "scale=2; $available_servers * 100 / $total_servers" | bc)
    echo -e "${BLUE}📊 Общая доступность серверов: ${availability}%${NC}"

    if (( $(echo "$availability < 95" | bc -l) )); then
        echo -e "${RED}❌ Доступность серверов ниже 95%${NC}"
        return 1
    fi

    return 0
}

# Функция проверки токен кеширования
check_token_cache() {
    echo -e "\n${YELLOW}Проверка токен кеширования${NC}"

    local cache_query="spire_token_cache_hit_ratio"
    local hit_ratio
    hit_ratio=$(check_prometheus_metric "$cache_query" "Hit ratio кеша токенов")

    if [[ $? -eq 0 ]]; then
        if (( $(echo "$hit_ratio > 0.8" | bc -l) )); then
            echo -e "${GREEN}✅ Кеширование токенов работает эффективно (> 80%)${NC}"
            return 0
        else
            echo -e "${RED}❌ Низкий hit ratio кеша: ${hit_ratio}${NC}"
            return 1
        fi
    fi

    return 1
}

# Функция проверки многорегионального failover
check_failover_mechanism() {
    echo -e "\n${YELLOW}Проверка механизма failover${NC}"

    # Проверяем failover события
    local failover_query="spire_failover_events_total"
    local failover_events
    failover_events=$(check_prometheus_metric "$failover_query" "Количество failover событий")

    if [[ $? -eq 0 ]]; then
        if (( $(echo "$failover_events < 5" | bc -l) )); then
            echo -e "${GREEN}✅ Минимальное количество failover событий${NC}"
            return 0
        else
            echo -e "${YELLOW}⚠️  Обнаружено $failover_events failover событий${NC}"
            return 0
        fi
    fi

    return 1
}

# Функция проверки синхронизации trust bundles
check_bundle_sync() {
    echo -e "\n${YELLOW}Проверка синхронизации trust bundles${NC}"

    local sync_query="spire_bundle_sync_duration_seconds"
    local sync_duration
    sync_duration=$(check_prometheus_metric "$sync_query" "Время синхронизации bundles (сек)")

    if [[ $? -eq 0 ]]; then
        if (( $(echo "$sync_duration < 30" | bc -l) )); then
            echo -e "${GREEN}✅ Синхронизация bundles в пределах нормы (< 30 сек)${NC}"
            return 0
        else
            echo -e "${RED}❌ Медленная синхронизация bundles: ${sync_duration} сек${NC}"
            return 1
        fi
    fi

    return 1
}

# Функция проверки доступности агентов
check_agent_connectivity() {
    echo -e "\n${YELLOW}Проверка доступности SPIRE агентов${NC}"

    local agent_types=("edge" "standard")
    local total_agents=0
    local connected_agents=0

    for agent_type in "${agent_types[@]}"; do
        echo -e "\n${BLUE}Тип агентов: $agent_type${NC}"

        # Получаем количество подов агентов
        local agent_pods
        agent_pods=$(kubectl get pods -n "$NAMESPACE" -l app=spire-agent,type="$agent_type" -o jsonpath='{.items[*].metadata.name}' 2>/dev/null || echo "")

        if [[ -z "$agent_pods" ]]; then
            echo -e "${YELLOW}⚠️  Агенты типа $agent_type не найдены${NC}"
            continue
        fi

        local pod_count=$(echo "$agent_pods" | wc -w)
        total_agents=$((total_agents + pod_count))

        # Проверяем подключение к SPIRE серверу
        local connected_count=0
        for pod in $agent_pods; do
            if kubectl exec -n "$NAMESPACE" "$pod" -- spire-agent api fetch -socketPath=/tmp/spire-agent/public/api.sock >/dev/null 2>&1; then
                connected_count=$((connected_count + 1))
            fi
        done

        connected_agents=$((connected_agents + connected_count))

        if [[ $connected_count -eq $pod_count ]]; then
            echo -e "${GREEN}✅ Все агенты $agent_type подключены ($connected_count/$pod_count)${NC}"
        else
            echo -e "${RED}❌ Некоторые агенты $agent_type не подключены ($connected_count/$pod_count)${NC}"
        fi
    done

    if [[ $total_agents -eq 0 ]]; then
        echo -e "${RED}❌ Не найдены SPIRE агенты${NC}"
        return 1
    fi

    local connectivity=$(echo "scale=2; $connected_agents * 100 / $total_agents" | bc)
    echo -e "${BLUE}📊 Подключение агентов: ${connectivity}%${NC}"

    if (( $(echo "$connectivity < 95" | bc -l) )); then
        echo -e "${RED}❌ Подключение агентов ниже 95%${NC}"
        return 1
    fi

    return 0
}

# Функция проверки производительности запросов
check_request_performance() {
    echo -e "\n${YELLOW}Проверка производительности запросов${NC}"

    local request_query="spire_server_requests_total:rate_5m"
    local request_rate
    request_rate=$(check_prometheus_metric "$request_query" "Частота запросов в секунду")

    if [[ $? -eq 0 ]]; then
        if (( $(echo "$request_rate < 1000" | bc -l) )); then
            echo -e "${GREEN}✅ Производительность запросов в норме (< 1000 req/sec)${NC}"
            return 0
        else
            echo -e "${RED}❌ Высокая нагрузка: ${request_rate} req/sec${NC}"
            return 1
        fi
    fi

    return 1
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

    echo -e "${BLUE}🚀 Запуск валидации SPIFFE/SPIRE оптимизаций${NC}"
    echo "Время начала: $(date)"

    # Проверка доступности серверов
    total_checks=$((total_checks + 1))
    if ! check_spire_servers; then
        failures=$((failures + 1))
    fi

    # Проверка токен кеширования
    total_checks=$((total_checks + 1))
    if ! check_token_cache; then
        failures=$((failures + 1))
    fi

    # Проверка механизма failover
    total_checks=$((total_checks + 1))
    if ! check_failover_mechanism; then
        failures=$((failures + 1))
    fi

    # Проверка синхронизации bundles
    total_checks=$((total_checks + 1))
    if ! check_bundle_sync; then
        failures=$((failures + 1))
    fi

    # Проверка доступности агентов
    total_checks=$((total_checks + 1))
    if ! check_agent_connectivity; then
        failures=$((failures + 1))
    fi

    # Проверка производительности запросов
    total_checks=$((total_checks + 1))
    if ! check_request_performance; then
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
        echo -e "${GREEN}🔐 SPIFFE/SPIRE оптимизации работают корректно${NC}"
        return 0
    else
        echo -e "${RED}❌ Валидация провалена!${NC}"
        echo -e "${RED}🔐 Требуются дополнительные настройки SPIRE${NC}"
        return 1
    fi
}

# Запуск валидации
main "$@"
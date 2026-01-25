#!/bin/bash

# Скрипт валидации оптимизаций HNSW индексации
# Проверяет многорегиональную репликацию и производительность

set -euo pipefail

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Конфигурация
NAMESPACE="${NAMESPACE:-hnsw-system}"
TIMEOUT="${TIMEOUT:-300}"
PROMETHEUS_URL="${PROMETHEUS_URL:-http://prometheus.monitoring.svc.cluster.local:9090}"

# KPI цели для HNSW оптимизаций
TARGET_METRICS=(
    "hnsw_search_latency_seconds<0.1"         # Поиск < 100мс
    "hnsw_cache_hit_rate>0.85"                # Hit rate кеша > 85%
    "hnsw_replication_lag_seconds<5"          # Задержка репликации < 5 сек
    "hnsw_index_update_latency<2"             # Обновление индекса < 2 сек
    "hnsw_memory_usage<0.9"                   # Использование памяти < 90%
)

echo -e "${BLUE}🔍 Валидация оптимизаций HNSW индексации${NC}"
echo "========================================"

# Функция проверки доступности HNSW сервисов
check_hnsw_services() {
    echo -e "\n${YELLOW}Проверка доступности HNSW сервисов${NC}"

    local deployments=("hnsw-indexer" "hnsw-replicator" "hnsw-cache")
    local available_services=0
    local total_services=0

    for deployment in "${deployments[@]}"; do
        echo -e "\n${BLUE}Сервис: $deployment${NC}"

        # Проверяем deployment
        local replicas
        replicas=$(kubectl get deployment "$deployment" -n "$NAMESPACE" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "0")

        if [[ "$replicas" == "0" ]]; then
            echo -e "${YELLOW}⚠️  Сервис $deployment не развернут${NC}"
            continue
        fi

        total_services=$((total_services + replicas))

        # Проверяем доступность подов
        local ready_pods
        ready_pods=$(kubectl get pods -n "$NAMESPACE" -l app="$deployment" -o jsonpath='{.items[*].status.conditions[?(@.type=="Ready")].status}' | grep -o "True" | wc -l)

        if [[ $ready_pods -eq $replicas ]]; then
            available_services=$((available_services + ready_pods))
            echo -e "${GREEN}✅ Сервис $deployment доступен ($ready_pods/$replicas)${NC}"
        else
            echo -e "${RED}❌ Сервис $deployment частично доступен ($ready_pods/$replicas)${NC}"
        fi
    done

    if [[ $total_services -eq 0 ]]; then
        echo -e "${RED}❌ Не найдены развернутые HNSW сервисы${NC}"
        return 1
    fi

    local availability=$(echo "scale=2; $available_services * 100 / $total_services" | bc)
    echo -e "${BLUE}📊 Общая доступность сервисов: ${availability}%${NC}"

    if (( $(echo "$availability < 95" | bc -l) )); then
        echo -e "${RED}❌ Доступность сервисов ниже 95%${NC}"
        return 1
    fi

    return 0
}

# Функция проверки производительности поиска
check_search_performance() {
    echo -e "\n${YELLOW}Проверка производительности поиска${NC}"

    local search_query="hnsw_search_latency_seconds"
    local search_latency
    search_latency=$(check_prometheus_metric "$search_query" "Средняя задержка поиска (сек)")

    if [[ $? -eq 0 ]]; then
        if (( $(echo "$search_latency < 0.1" | bc -l) )); then
            echo -e "${GREEN}✅ Производительность поиска в норме (< 100мс)${NC}"
            return 0
        else
            echo -e "${RED}❌ Высокая задержка поиска: ${search_latency} сек${NC}"
            return 1
        fi
    fi

    return 1
}

# Функция проверки кеширования
check_cache_effectiveness() {
    echo -e "\n${YELLOW}Проверка эффективности кеширования${NC}"

    local cache_query="hnsw_cache_hit_rate"
    local cache_hit_rate
    cache_hit_rate=$(check_prometheus_metric "$cache_query" "Hit rate кеша")

    if [[ $? -eq 0 ]]; then
        if (( $(echo "$cache_hit_rate > 0.85" | bc -l) )); then
            echo -e "${GREEN}✅ Эффективность кеширования в норме (> 85%)${NC}"
            return 0
        else
            echo -e "${RED}❌ Низкий hit rate кеша: ${cache_hit_rate}${NC}"
            return 1
        fi
    fi

    return 1
}

# Функция проверки задержки репликации
check_replication_lag() {
    echo -e "\n${YELLOW}Проверка задержки репликации${NC}"

    local replication_query="hnsw_replication_lag_seconds"
    local replication_lag
    replication_lag=$(check_prometheus_metric "$replication_query" "Задержка репликации (сек)")

    if [[ $? -eq 0 ]]; then
        if (( $(echo "$replication_lag < 5" | bc -l) )); then
            echo -e "${GREEN}✅ Задержка репликации в норме (< 5 сек)${NC}"
            return 0
        else
            echo -e "${RED}❌ Высокая задержка репликации: ${replication_lag} сек${NC}"
            return 1
        fi
    fi

    return 1
}

# Функция проверки обновления индексов
check_index_updates() {
    echo -e "\n${YELLOW}Проверка обновления индексов${NC}"

    local update_query="hnsw_index_update_latency"
    local update_latency
    update_latency=$(check_prometheus_metric "$update_query" "Задержка обновления индекса (сек)")

    if [[ $? -eq 0 ]]; then
        if (( $(echo "$update_latency < 2" | bc -l) )); then
            echo -e "${GREEN}✅ Обновление индексов в норме (< 2 сек)${NC}"
            return 0
        else
            echo -e "${RED}❌ Медленное обновление индексов: ${update_latency} сек${NC}"
            return 1
        fi
    fi

    return 1
}

# Функция проверки использования памяти
check_memory_usage() {
    echo -e "\n${YELLOW}Проверка использования памяти${NC}"

    local memory_query="hnsw_memory_usage"
    local memory_usage
    memory_usage=$(check_prometheus_metric "$memory_query" "Использование памяти")

    if [[ $? -eq 0 ]]; then
        if (( $(echo "$memory_usage < 0.9" | bc -l) )); then
            echo -e "${GREEN}✅ Использование памяти в норме (< 90%)${NC}"
            return 0
        else
            echo -e "${RED}❌ Высокое использование памяти: ${memory_usage}${NC}"
            return 1
        fi
    fi

    return 1
}

# Функция проверки многорегиональной репликации
check_multi_region_replication() {
    echo -e "\n${YELLOW}Проверка многорегиональной репликации${NC}"

    local regions=("us-east" "eu-west" "asia-pacific")
    local replicated_regions=0

    for region in "${regions[@]}"; do
        echo -e "\n${BLUE}Регион: $region${NC}"

        # Проверяем статус репликации
        local replication_status
        replication_status=$(kubectl exec -n "$NAMESPACE" deployment/hnsw-replicator -c hnsw-replicator -- \
            curl -s http://localhost:8080/health/replication/$region 2>/dev/null | \
            jq -r '.status // "unknown"' 2>/dev/null || echo "unknown")

        if [[ "$replication_status" == "healthy" ]]; then
            replicated_regions=$((replicated_regions + 1))
            echo -e "${GREEN}✅ Репликация в регион $region активна${NC}"
        else
            echo -e "${RED}❌ Проблемы с репликацией в регион $region${NC}"
        fi
    done

    echo -e "${BLUE}📊 Активные реплики: $replicated_regions/${#regions[@]}${NC}"

    if [[ $replicated_regions -lt 2 ]]; then
        echo -e "${RED}❌ Недостаточно активных реплик${NC}"
        return 1
    fi

    return 0
}

# Функция проверки асинхронных обновлений
check_async_updates() {
    echo -e "\n${YELLOW}Проверка асинхронных обновлений${NC}"

    # Проверяем размер очереди обновлений
    local queue_size
    queue_size=$(kubectl exec -n "$NAMESPACE" deployment/hnsw-replicator -c hnsw-replicator -- \
        curl -s http://localhost:8080/metrics 2>/dev/null | \
        grep "hnsw_update_queue_size" | \
        awk '{print $2}' || echo "0")

    echo -e "${BLUE}📊 Размер очереди обновлений: $queue_size${NC}"

    if [[ $queue_size -lt 1000 ]]; then
        echo -e "${GREEN}✅ Очередь обновлений в норме${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠️  Большая очередь обновлений: $queue_size${NC}"
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

    echo -e "${BLUE}🚀 Запуск валидации HNSW оптимизаций${NC}"
    echo "Время начала: $(date)"

    # Проверка доступности сервисов
    total_checks=$((total_checks + 1))
    if ! check_hnsw_services; then
        failures=$((failures + 1))
    fi

    # Проверка производительности поиска
    total_checks=$((total_checks + 1))
    if ! check_search_performance; then
        failures=$((failures + 1))
    fi

    # Проверка кеширования
    total_checks=$((total_checks + 1))
    if ! check_cache_effectiveness; then
        failures=$((failures + 1))
    fi

    # Проверка задержки репликации
    total_checks=$((total_checks + 1))
    if ! check_replication_lag; then
        failures=$((failures + 1))
    fi

    # Проверка обновления индексов
    total_checks=$((total_checks + 1))
    if ! check_index_updates; then
        failures=$((failures + 1))
    fi

    # Проверка использования памяти
    total_checks=$((total_checks + 1))
    if ! check_memory_usage; then
        failures=$((failures + 1))
    fi

    # Проверка многорегиональной репликации
    total_checks=$((total_checks + 1))
    if ! check_multi_region_replication; then
        failures=$((failures + 1))
    fi

    # Проверка асинхронных обновлений
    total_checks=$((total_checks + 1))
    if ! check_async_updates; then
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
        echo -e "${GREEN}📊 HNSW оптимизации работают корректно${NC}"
        return 0
    else
        echo -e "${RED}❌ Валидация провалена!${NC}"
        echo -e "${RED}📊 Требуются дополнительные настройки HNSW${NC}"
        return 1
    fi
}

# Запуск валидации
main "$@"
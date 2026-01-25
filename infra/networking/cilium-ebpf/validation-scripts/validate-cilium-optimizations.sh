#!/bin/bash

# Скрипт валидации оптимизаций Cilium eBPF
# Проверяет consistency checks и снижение ложных срабатываний

set -euo pipefail

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Конфигурация
NAMESPACE="${NAMESPACE:-kube-system}"
TIMEOUT="${TIMEOUT:-300}"
PROMETHEUS_URL="${PROMETHEUS_URL:-http://prometheus.monitoring.svc.cluster.local:9090}"

# KPI цели для Cilium оптимизаций
TARGET_METRICS=(
    "cilium_policy_evaluation_seconds<0.01"   # Оценка политик < 10мс
    "cilium_false_positive_ratio<0.12"        # Ложные срабатывания < 12%
    "cilium_policy_consistency>0.95"          # Консистентность > 95%
    "cilium_ebpf_compilation_time<30"         # Компиляция < 30 сек
    "cilium_drop_count<100"                   # Дропов < 100 за период
)

echo -e "${BLUE}🔍 Валидация оптимизаций Cilium eBPF${NC}"
echo "===================================="

# Функция проверки доступности Cilium агентов
check_cilium_agents() {
    echo -e "\n${YELLOW}Проверка доступности Cilium агентов${NC}"

    local cilium_pods
    cilium_pods=$(kubectl get pods -n "$NAMESPACE" -l k8s-app=cilium -o jsonpath='{.items[*].metadata.name}')

    if [[ -z "$cilium_pods" ]]; then
        echo -e "${RED}❌ Не найдены Cilium поды${NC}"
        return 1
    fi

    local ready_count=0
    local total_count=0

    for pod in $cilium_pods; do
        total_count=$((total_count + 1))

        if kubectl exec -n "$NAMESPACE" "$pod" -- cilium status >/dev/null 2>&1; then
            ready_count=$((ready_count + 1))
            echo -e "${GREEN}✅ Cilium агент $pod готов${NC}"
        else
            echo -e "${RED}❌ Cilium агент $pod не готов${NC}"
        fi
    done

    local availability=$(echo "scale=2; $ready_count * 100 / $total_count" | bc)
    echo -e "${BLUE}📊 Доступность агентов: ${availability}%${NC}"

    if (( $(echo "$availability < 95" | bc -l) )); then
        echo -e "${RED}❌ Доступность агентов ниже 95%${NC}"
        return 1
    fi

    return 0
}

# Функция проверки оценки политик
check_policy_evaluation() {
    echo -e "\n${YELLOW}Проверка оценки политик${NC}"

    local evaluation_query="cilium_policy_evaluation_seconds"
    local evaluation_time
    evaluation_time=$(check_prometheus_metric "$evaluation_query" "Время оценки политик (сек)")

    if [[ $? -eq 0 ]]; then
        if (( $(echo "$evaluation_time < 0.01" | bc -l) )); then
            echo -e "${GREEN}✅ Оценка политик в норме (< 10мс)${NC}"
            return 0
        else
            echo -e "${RED}❌ Медленная оценка политик: ${evaluation_time} сек${NC}"
            return 1
        fi
    fi

    return 1
}

# Функция проверки ложных срабатываний
check_false_positive_rate() {
    echo -e "\n${YELLOW}Проверка уровня ложных срабатываний${NC}"

    local false_positive_query="cilium_false_positive_ratio"
    local false_positive_rate
    false_positive_rate=$(check_prometheus_metric "$false_positive_query" "Уровень ложных срабатываний")

    if [[ $? -eq 0 ]]; then
        if (( $(echo "$false_positive_rate < 0.12" | bc -l) )); then
            echo -e "${GREEN}✅ Ложные срабатывания в норме (< 12%)${NC}"
            return 0
        else
            echo -e "${RED}❌ Высокий уровень ложных срабатываний: ${false_positive_rate}${NC}"
            return 1
        fi
    fi

    return 1
}

# Функция проверки consistency checks
check_policy_consistency() {
    echo -e "\n${YELLOW}Проверка consistency checks${NC}"

    local consistency_query="cilium_policy_consistency"
    local consistency_score
    consistency_score=$(check_prometheus_metric "$consistency_query" "Консистентность политик")

    if [[ $? -eq 0 ]]; then
        if (( $(echo "$consistency_score > 0.95" | bc -l) )); then
            echo -e "${GREEN}✅ Консистентность политик в норме (> 95%)${NC}"
            return 0
        else
            echo -e "${RED}❌ Низкая консистентность политик: ${consistency_score}${NC}"
            return 1
        fi
    fi

    return 1
}

# Функция проверки компиляции eBPF
check_ebpf_compilation() {
    echo -e "\n${YELLOW}Проверка компиляции eBPF${NC}"

    local compilation_query="cilium_ebpf_compilation_time"
    local compilation_time
    compilation_time=$(check_prometheus_metric "$compilation_query" "Время компиляции eBPF (сек)")

    if [[ $? -eq 0 ]]; then
        if (( $(echo "$compilation_time < 30" | bc -l) )); then
            echo -e "${GREEN}✅ Компиляция eBPF в норме (< 30 сек)${NC}"
            return 0
        else
            echo -e "${RED}❌ Медленная компиляция eBPF: ${compilation_time} сек${NC}"
            return 1
        fi
    fi

    return 1
}

# Функция проверки количества дропов
check_drop_count() {
    echo -e "\n${YELLOW}Проверка количества дропов${NC}"

    local drop_query="cilium_drop_count"
    local drop_count
    drop_count=$(check_prometheus_metric "$drop_query" "Количество дропов")

    if [[ $? -eq 0 ]]; then
        if (( $(echo "$drop_count < 100" | bc -l) )); then
            echo -e "${GREEN}✅ Количество дропов в норме (< 100)${NC}"
            return 0
        else
            echo -e "${YELLOW}⚠️  Высокое количество дропов: $drop_count${NC}"
            return 0
        fi
    fi

    return 1
}

# Функция проверки Hubble интеграции
check_hubble_integration() {
    echo -e "\n${YELLOW}Проверка интеграции Hubble${NC}"

    # Проверяем Hubble Relay
    local hubble_relay
    hubble_relay=$(kubectl get pods -n "$NAMESPACE" -l k8s-app=hubble-relay -o jsonpath='{.items[*].status.conditions[?(@.type=="Ready")].status}' | grep -o "True" | wc -l)

    local total_relay
    total_relay=$(kubectl get pods -n "$NAMESPACE" -l k8s-app=hubble-relay -o jsonpath='{.items[*].metadata.name}' | wc -w)

    if [[ $hubble_relay -eq $total_relay && $total_relay -gt 0 ]]; then
        echo -e "${GREEN}✅ Hubble Relay доступен ($hubble_relay/$total_relay)${NC}"
    else
        echo -e "${RED}❌ Hubble Relay недоступен ($hubble_relay/$total_relay)${NC}"
        return 1
    fi

    # Проверяем Hubble UI
    local hubble_ui
    hubble_ui=$(kubectl get pods -n "$NAMESPACE" -l k8s-app=hubble-ui -o jsonpath='{.items[*].status.conditions[?(@.type=="Ready")].status}' | grep -o "True" | wc -l)

    local total_ui
    total_ui=$(kubectl get pods -n "$NAMESPACE" -l k8s-app=hubble-ui -o jsonpath='{.items[*].metadata.name}' | wc -w)

    if [[ $hubble_ui -eq $total_ui && $total_ui -gt 0 ]]; then
        echo -e "${GREEN}✅ Hubble UI доступен ($hubble_ui/$total_ui)${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠️  Hubble UI недоступен ($hubble_ui/$total_ui)${NC}"
        return 0
    fi
}

# Функция проверки многорегиональной синхронизации
check_multi_region_sync() {
    echo -e "\n${YELLOW}Проверка многорегиональной синхронизации${NC}"

    local regions=("us-east" "eu-west" "asia-pacific")
    local synced_regions=0

    for region in "${regions[@]}"; do
        echo -e "\n${BLUE}Регион: $region${NC}"

        # Проверяем синхронизацию политик
        local sync_status
        sync_status=$(kubectl exec -n "$NAMESPACE" cilium-0 -- cilium policy get 2>/dev/null | grep -c "Revision:" || echo "0")

        if [[ $sync_status -gt 0 ]]; then
            synced_regions=$((synced_regions + 1))
            echo -e "${GREEN}✅ Политики в регионе $region синхронизированы${NC}"
        else
            echo -e "${RED}❌ Проблемы синхронизации в регионе $region${NC}"
        fi
    done

    echo -e "${BLUE}📊 Синхронизированные регионы: $synced_regions/${#regions[@]}${NC}"

    if [[ $synced_regions -lt 2 ]]; then
        echo -e "${RED}❌ Недостаточно синхронизированных регионов${NC}"
        return 1
    fi

    return 0
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

    echo -e "${BLUE}🚀 Запуск валидации Cilium eBPF оптимизаций${NC}"
    echo "Время начала: $(date)"

    # Проверка доступности агентов
    total_checks=$((total_checks + 1))
    if ! check_cilium_agents; then
        failures=$((failures + 1))
    fi

    # Проверка оценки политик
    total_checks=$((total_checks + 1))
    if ! check_policy_evaluation; then
        failures=$((failures + 1))
    fi

    # Проверка ложных срабатываний
    total_checks=$((total_checks + 1))
    if ! check_false_positive_rate; then
        failures=$((failures + 1))
    fi

    # Проверка consistency checks
    total_checks=$((total_checks + 1))
    if ! check_policy_consistency; then
        failures=$((failures + 1))
    fi

    # Проверка компиляции eBPF
    total_checks=$((total_checks + 1))
    if ! check_ebpf_compilation; then
        failures=$((failures + 1))
    fi

    # Проверка количества дропов
    total_checks=$((total_checks + 1))
    if ! check_drop_count; then
        failures=$((failures + 1))
    fi

    # Проверка Hubble интеграции
    total_checks=$((total_checks + 1))
    if ! check_hubble_integration; then
        failures=$((failures + 1))
    fi

    # Проверка многорегиональной синхронизации
    total_checks=$((total_checks + 1))
    if ! check_multi_region_sync; then
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
        echo -e "${GREEN}📊 Cilium eBPF оптимизации работают корректно${NC}"
        return 0
    else
        echo -e "${RED}❌ Валидация провалена!${NC}"
        echo -e "${RED}📊 Требуются дополнительные настройки Cilium${NC}"
        return 1
    fi
}

# Запуск валидации
main "$@"
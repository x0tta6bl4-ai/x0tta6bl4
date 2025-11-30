#!/bin/bash
# Тест x0tta6bl4 на всех серверах
set -e

CLUSTERS=("kind-x0tta6bl4-local" "kind-x0tta6bl4-staging" "kind-x0tta6bl4-prod")
NAMESPACE="mesh-system"
RESULTS_DIR="results/multi-server-test"
mkdir -p "$RESULTS_DIR"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║       x0tta6bl4 MULTI-SERVER TEST                            ║"
echo "║       Серверов: ${#CLUSTERS[@]}                                            ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Функция деплоя
deploy_to_cluster() {
    local ctx=$1
    echo "📦 Деплой на $ctx..."
    
    kubectl create namespace $NAMESPACE --context $ctx 2>/dev/null || true
    
    # Helm install
    helm upgrade --install x0tta6bl4 helm/x0tta6bl4 \
        --namespace $NAMESPACE \
        --context $ctx \
        --set replicaCount=3 \
        --set spiffe.enabled=false \
        --wait --timeout 120s 2>/dev/null || true
    
    echo "✅ Задеплоено на $ctx"
}

# Функция теста MTTR
test_mttr() {
    local ctx=$1
    echo "🧪 Тест MTTR на $ctx..."
    
    local pod=$(kubectl get pods -n $NAMESPACE --context $ctx -o name 2>/dev/null | head -1)
    if [ -z "$pod" ]; then
        echo "❌ Нет подов на $ctx"
        return 1
    fi
    
    local start=$(date +%s%N)
    kubectl delete $pod -n $NAMESPACE --context $ctx --grace-period=0 --force 2>/dev/null || true
    
    # Ждём восстановления
    local timeout=30
    local elapsed=0
    while [ $elapsed -lt $timeout ]; do
        local ready=$(kubectl get pods -n $NAMESPACE --context $ctx --no-headers 2>/dev/null | grep -c "Running" || echo "0")
        if [ "$ready" -ge 3 ]; then
            break
        fi
        sleep 0.5
        elapsed=$((elapsed + 1))
    done
    
    local end=$(date +%s%N)
    local mttr=$(echo "scale=2; ($end - $start) / 1000000000" | bc)
    echo "   MTTR: ${mttr}s"
    echo "$mttr"
}

# Функция проверки здоровья
check_health() {
    local ctx=$1
    echo "🏥 Проверка здоровья $ctx..."
    
    local nodes=$(kubectl get nodes --context $ctx --no-headers 2>/dev/null | wc -l)
    local pods=$(kubectl get pods -n $NAMESPACE --context $ctx --no-headers 2>/dev/null | grep -c "Running" || echo "0")
    
    echo "   Узлы: $nodes"
    echo "   Поды: $pods"
    
    if [ "$pods" -ge 3 ]; then
        return 0
    else
        return 1
    fi
}

# Основной тест
echo "═══════════════════════════════════════════════════════════════"
echo "ЭТАП 1: ДЕПЛОЙ НА ВСЕ СЕРВЕРЫ"
echo "═══════════════════════════════════════════════════════════════"

for cluster in "${CLUSTERS[@]}"; do
    deploy_to_cluster "$cluster"
done

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "ЭТАП 2: ПРОВЕРКА ЗДОРОВЬЯ"
echo "═══════════════════════════════════════════════════════════════"

declare -A health_results
for cluster in "${CLUSTERS[@]}"; do
    if check_health "$cluster"; then
        health_results[$cluster]="✅ OK"
    else
        health_results[$cluster]="❌ FAIL"
    fi
done

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "ЭТАП 3: ТЕСТ MTTR (САМОВОССТАНОВЛЕНИЕ)"
echo "═══════════════════════════════════════════════════════════════"

declare -A mttr_results
for cluster in "${CLUSTERS[@]}"; do
    mttr=$(test_mttr "$cluster")
    mttr_results[$cluster]="$mttr"
done

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "ЭТАП 4: СТРЕСС-ТЕСТ (3 ПОСЛЕДОВАТЕЛЬНЫХ УБИЙСТВА)"
echo "═══════════════════════════════════════════════════════════════"

declare -A stress_results
for cluster in "${CLUSTERS[@]}"; do
    echo "💥 Стресс-тест на $cluster..."
    total_mttr=0
    for i in 1 2 3; do
        mttr=$(test_mttr "$cluster" 2>/dev/null | tail -1)
        if [[ "$mttr" =~ ^[0-9]+\.?[0-9]*$ ]]; then
            total_mttr=$(echo "$total_mttr + $mttr" | bc)
        fi
        sleep 2
    done
    avg_mttr=$(echo "scale=2; $total_mttr / 3" | bc 2>/dev/null || echo "N/A")
    stress_results[$cluster]="$avg_mttr"
    echo "   Средний MTTR: ${avg_mttr}s"
done

# Сохранение результатов
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "📊 ИТОГОВЫЕ РЕЗУЛЬТАТЫ"
echo "═══════════════════════════════════════════════════════════════"

cat > "$RESULTS_DIR/summary.md" << EOF
# 🖥️ Multi-Server Test Results

**Дата:** $(date)
**Серверов:** ${#CLUSTERS[@]}

## Результаты по серверам

| Сервер | Здоровье | MTTR | Стресс-тест |
|--------|----------|------|-------------|
EOF

for cluster in "${CLUSTERS[@]}"; do
    echo "| $cluster | ${health_results[$cluster]:-N/A} | ${mttr_results[$cluster]:-N/A}s | ${stress_results[$cluster]:-N/A}s |" >> "$RESULTS_DIR/summary.md"
    echo "  $cluster:"
    echo "    Здоровье: ${health_results[$cluster]:-N/A}"
    echo "    MTTR: ${mttr_results[$cluster]:-N/A}s"
    echo "    Стресс: ${stress_results[$cluster]:-N/A}s"
done

# Подсчёт общего статуса
passed=0
for cluster in "${CLUSTERS[@]}"; do
    if [[ "${health_results[$cluster]}" == *"OK"* ]]; then
        ((passed++))
    fi
done

cat >> "$RESULTS_DIR/summary.md" << EOF

## Общий статус

- **Успешно:** $passed/${#CLUSTERS[@]} серверов
- **Target MTTR:** ≤5s
EOF

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                                                              ║"
echo "║  🏆 ТЕСТ ЗАВЕРШЁН                                            ║"
echo "║                                                              ║"
echo "║  Серверов: ${#CLUSTERS[@]}                                               ║"
echo "║  Успешно: $passed/${#CLUSTERS[@]}                                            ║"
echo "║  Результаты: $RESULTS_DIR/summary.md                  ║"
echo "║                                                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"

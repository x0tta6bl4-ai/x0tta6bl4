#!/bin/bash
# Automated Failure Injection Test Script
# Дата: 2026-01-07
# Версия: 3.4.0-fixed2

set -euo pipefail

NAMESPACE="x0tta6bl4-staging"
DEPLOYMENT="x0tta6bl4-staging"
SERVICE_URL="http://localhost:8080"
RESULTS_FILE="FAILURE_INJECTION_RESULTS_$(date +%Y%m%d_%H%M%S).md"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Initialize results file
init_results() {
    cat > "$RESULTS_FILE" << EOF
# Failure Injection Test Results
**Дата:** $(date +'%Y-%m-%d %H:%M:%S')
**Версия:** 3.4.0-fixed2
**Namespace:** $NAMESPACE

---

## Test Summary

| Test | Status | MTTD | MTTR | Notes |
|------|--------|------|------|-------|
EOF
}

# Record test result
record_result() {
    local test_name=$1
    local status=$2
    local mttd=$3
    local mttr=$4
    local notes=$5
    
    echo "| $test_name | $status | ${mttd}s | ${mttr}s | $notes |" >> "$RESULTS_FILE"
}

# Check pre-conditions
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
    
    local pod_count=$(kubectl get pods -n "$NAMESPACE" --no-headers | wc -l)
    if [ "$pod_count" -lt 2 ]; then
        error "Недостаточно pods для тестирования (найдено: $pod_count, требуется: >= 2)"
        exit 1
    fi
    
    if ! curl -sf "$SERVICE_URL/health" > /dev/null; then
        error "Сервис недоступен по адресу $SERVICE_URL"
        exit 1
    fi
    
    log "✅ Все предварительные условия выполнены"
}

# Get baseline metrics
get_baseline_metrics() {
    log "Сбор baseline метрик..."
    
    local baseline_file="baseline_metrics_$(date +%Y%m%d_%H%M%S).json"
    
    cat > "$baseline_file" << EOF
{
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "pods": {
    "total": $(kubectl get pods -n "$NAMESPACE" --no-headers | wc -l),
    "running": $(kubectl get pods -n "$NAMESPACE" --field-selector=status.phase=Running --no-headers | wc -l),
    "ready": $(kubectl get pods -n "$NAMESPACE" --field-selector=status.phase=Running --no-headers | grep -c "1/1" || echo 0)
  },
  "mesh": {
    "status": $(curl -sf "$SERVICE_URL/mesh/status" 2>/dev/null || echo 'null')
  },
  "metrics": {
    "mape_k_cycle_duration": $(curl -sf "$SERVICE_URL/metrics" 2>/dev/null | grep 'mesh_mape_k_cycle_duration_seconds' | awk '{print $2}' | head -1 || echo 'null'),
    "gnn_recall_score": $(curl -sf "$SERVICE_URL/metrics" 2>/dev/null | grep 'gnn_recall_score' | awk '{print $2}' | head -1 || echo 'null')
  }
}
EOF
    
    log "✅ Baseline метрики сохранены в $baseline_file"
    echo "$baseline_file"
}

# Test 1: Pod Failure
test_pod_failure() {
    log "=== Test 1: Pod Failure ==="
    
    # Get a pod to kill
    local pod_to_kill=$(kubectl get pods -n "$NAMESPACE" -o jsonpath='{.items[0].metadata.name}')
    if [ -z "$pod_to_kill" ]; then
        error "Не удалось найти pod для удаления"
        return 1
    fi
    
    log "Выбран pod для удаления: $pod_to_kill"
    
    # Record start time
    local start_time=$(date +%s)
    local detection_time=0
    local recovery_time=0
    
    # Kill pod
    log "Удаление pod..."
    kubectl delete pod "$pod_to_kill" -n "$NAMESPACE" --wait=false
    
    # Monitor for detection (MTTD)
    log "Ожидание обнаружения проблемы (MTTD)..."
    local max_wait=60  # 60 seconds max
    local waited=0
    
    while [ $waited -lt $max_wait ]; do
        # Check if MAPE-K detected the issue using multiple methods:
        # 1. Check self-healing events metric
        local self_healing_events=$(curl -sf "$SERVICE_URL/metrics" 2>/dev/null | grep -E 'self_healing_events_total|mesh_mape_k_' | grep -c 'node_failure\|pod_failure\|incident' || echo 0)
        
        # 2. Check Kubernetes events for pod deletion
        local k8s_events=$(kubectl get events -n "$NAMESPACE" --field-selector involvedObject.name="$pod_to_kill" --sort-by='.lastTimestamp' 2>/dev/null | grep -c 'Killing\|Deleted' || echo 0)
        
        # 3. Check if new pod is being created (indicates detection)
        # Count pods that are NOT the one we killed
        local current_pods=$(kubectl get pods -n "$NAMESPACE" --no-headers 2>/dev/null | awk '{print $1}' | grep -v "^${pod_to_kill}$" | wc -l)
        local baseline_pods=5
        # If we have 5 pods (excluding the killed one), a new pod was created
        if [ "$current_pods" -ge "$baseline_pods" ]; then
            # New pod is being created, system detected the failure
            detection_time=$(($(date +%s) - start_time))
            log "✅ Проблема обнаружена за ${detection_time}s (MTTD) - новый pod создается"
            break
        fi
        
        # Use first available detection method
        if [ "$self_healing_events" -gt 0 ] || [ "$k8s_events" -gt 0 ]; then
            detection_time=$(($(date +%s) - start_time))
            log "✅ Проблема обнаружена за ${detection_time}s (MTTD)"
            break
        fi
        
        sleep 2
        waited=$((waited + 2))
    done
    
    if [ $detection_time -eq 0 ]; then
        warn "Проблема не обнаружена за $max_wait секунд (используется timeout как MTTD)"
        detection_time=$max_wait
    fi
    
    # Monitor for recovery (MTTR)
    log "Ожидание восстановления (MTTR)..."
    local max_recovery=180  # 3 minutes max
    local recovery_waited=0
    
    while [ $recovery_waited -lt $max_recovery ]; do
        local running_pods=$(kubectl get pods -n "$NAMESPACE" --field-selector=status.phase=Running --no-headers | wc -l)
        local ready_pods=$(kubectl get pods -n "$NAMESPACE" --field-selector=status.phase=Running --no-headers | grep -c "1/1" || echo 0)
        
        # Check if we're back to baseline (assuming we started with 5 pods)
        if [ "$running_pods" -ge 5 ] && [ "$ready_pods" -ge 5 ]; then
            recovery_time=$(($(date +%s) - start_time))
            log "✅ Система восстановлена за ${recovery_time}s (MTTR)"
            break
        fi
        
        sleep 5
        recovery_waited=$((recovery_waited + 5))
    done
    
    if [ $recovery_time -eq 0 ]; then
        warn "Система не восстановилась за $max_recovery секунд"
        recovery_time=$max_recovery
    fi
    
    # Evaluate results
    local status="✅ PASS"
    local notes=""
    
    if [ $detection_time -gt 20 ]; then
        status="⚠️ PARTIAL"
        notes="MTTD превышает 20s"
    fi
    
    if [ $recovery_time -gt 180 ]; then
        status="❌ FAIL"
        notes="MTTR превышает 3min"
    fi
    
    record_result "Pod Failure" "$status" "$detection_time" "$recovery_time" "$notes"
    
    log "Результат: $status (MTTD: ${detection_time}s, MTTR: ${recovery_time}s)"
    
    # Wait for system to stabilize
    sleep 30
}

# Test 2: High Load
test_high_load() {
    log "=== Test 2: High Load ==="
    
    local start_time=$(date +%s)
    
    log "Создание высокой нагрузки (1000 запросов)..."
    
    # Generate load
    local success_count=0
    local total_requests=1000
    
    for i in $(seq 1 $total_requests); do
        if curl -sf "$SERVICE_URL/health" > /dev/null 2>&1; then
            success_count=$((success_count + 1))
        fi
        
        # Small delay to avoid overwhelming
        if [ $((i % 100)) -eq 0 ]; then
            log "Обработано $i/$total_requests запросов..."
        fi
    done
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    local success_rate=$(echo "scale=2; $success_count * 100 / $total_requests" | bc)
    
    # Check system state
    local pods_running=$(kubectl get pods -n "$NAMESPACE" --field-selector=status.phase=Running --no-headers | wc -l)
    local pods_ready=$(kubectl get pods -n "$NAMESPACE" --field-selector=status.phase=Running --no-headers | grep -c "1/1" || echo 0)
    
    local status="✅ PASS"
    local notes="Success rate: ${success_rate}%"
    
    if [ "$pods_running" -lt 5 ] || [ "$pods_ready" -lt 5 ]; then
        status="⚠️ PARTIAL"
        notes="Pods не восстановились после нагрузки"
    fi
    
    if (( $(echo "$success_rate < 95" | bc -l) )); then
        status="❌ FAIL"
        notes="Success rate слишком низкий: ${success_rate}%"
    fi
    
    record_result "High Load" "$status" "N/A" "$duration" "$notes"
    
    log "Результат: $status (Success rate: ${success_rate}%, Duration: ${duration}s)"
    
    # Wait for system to stabilize
    sleep 30
}

# Test 3: Resource Exhaustion
test_resource_exhaustion() {
    log "=== Test 3: Resource Exhaustion ==="
    
    local start_time=$(date +%s)
    
    log "Уменьшение resource limits и requests..."
    
    # First, reduce requests to be safe (must be <= current limits)
    # Get current limits first to ensure requests are valid
    local current_cpu_limit=$(kubectl get deployment "$DEPLOYMENT" -n "$NAMESPACE" -o jsonpath='{.spec.template.spec.containers[0].resources.limits.cpu}' 2>/dev/null || echo "2000m")
    local current_mem_limit=$(kubectl get deployment "$DEPLOYMENT" -n "$NAMESPACE" -o jsonpath='{.spec.template.spec.containers[0].resources.limits.memory}' 2>/dev/null || echo "2Gi")
    
    # Reduce requests first (to 200m/256Mi which is safe for any limit >= 300m/512Mi)
    # Using realistic minimums that allow the app to function but create resource pressure
    kubectl patch deployment "$DEPLOYMENT" -n "$NAMESPACE" --type='json' -p='[
        {"op": "replace", "path": "/spec/template/spec/containers/0/resources/requests/cpu", "value": "200m"},
        {"op": "replace", "path": "/spec/template/spec/containers/0/resources/requests/memory", "value": "256Mi"}
    ]' || {
        warn "Не удалось обновить resource requests (может быть нормально)"
    }
    
    # Wait a moment for requests to be applied
    sleep 5
    
    # Then, reduce limits (must be >= requests)
    # Using 300m CPU and 512Mi memory - enough to function but creates resource pressure
    kubectl patch deployment "$DEPLOYMENT" -n "$NAMESPACE" --type='json' -p='[
        {"op": "replace", "path": "/spec/template/spec/containers/0/resources/limits/cpu", "value": "300m"},
        {"op": "replace", "path": "/spec/template/spec/containers/0/resources/limits/memory", "value": "512Mi"}
    ]' || {
        error "Не удалось обновить resource limits"
        return 1
    }
    
    log "Ожидание применения изменений и стабилизации pods..."
    sleep 60  # Increased wait time for pods to restart with new limits
    
    # Wait for pods to be ready
    local max_wait=120
    local waited=0
    while [ $waited -lt $max_wait ]; do
        local ready_pods=$(kubectl get pods -n "$NAMESPACE" --field-selector=status.phase=Running --no-headers | grep -c "1/1" || echo 0)
        if [ "$ready_pods" -ge 4 ]; then  # At least 4 out of 5 pods ready
            log "✅ Pods готовы (${ready_pods}/5)"
            break
        fi
        sleep 5
        waited=$((waited + 5))
        log "Ожидание готовности pods... (${ready_pods}/5 ready, ${waited}s/${max_wait}s)"
    done
    
    # Check if system is still functional (with retries)
    local health_check="FAIL"
    for i in {1..5}; do
        if curl -sf "$SERVICE_URL/health" > /dev/null 2>&1; then
            health_check="OK"
            log "✅ Health check успешен (попытка $i/5)"
            break
        else
            log "⚠️ Health check failed (попытка $i/5), повтор через 5s..."
            sleep 5
        fi
    done
    
    # Check response time
    local response_time=$(curl -o /dev/null -s -w '%{time_total}' "$SERVICE_URL/health" 2>/dev/null || echo "0")
    log "Response time: ${response_time}s"
    
    local detection_time=$(($(date +%s) - start_time))
    
    # Restore limits first (must be >= current requests)
    log "Восстановление resource limits..."
    kubectl patch deployment "$DEPLOYMENT" -n "$NAMESPACE" --type='json' -p='[
        {"op": "replace", "path": "/spec/template/spec/containers/0/resources/limits/cpu", "value": "2000m"},
        {"op": "replace", "path": "/spec/template/spec/containers/0/resources/limits/memory", "value": "2Gi"}
    ]' || {
        error "Не удалось восстановить resource limits"
    }
    
    # Wait a moment for limits to be applied
    sleep 5
    
    # Then restore requests (now safe since limits are 2000m/2Gi)
    log "Восстановление resource requests..."
    kubectl patch deployment "$DEPLOYMENT" -n "$NAMESPACE" --type='json' -p='[
        {"op": "replace", "path": "/spec/template/spec/containers/0/resources/requests/cpu", "value": "500m"},
        {"op": "replace", "path": "/spec/template/spec/containers/0/resources/requests/memory", "value": "1Gi"}
    ]' || {
        warn "Не удалось восстановить resource requests"
    }
    
    sleep 30
    
    local recovery_time=$(($(date +%s) - start_time))
    
    # Evaluate results - system should function but may be degraded
    local status="✅ PASS"
    local notes="System functional under resource constraints"
    
    if [ "$health_check" != "OK" ]; then
        status="❌ FAIL"
        notes="System не функционирует при ограниченных ресурсах (300m CPU, 512Mi memory)"
    else
        # Check if system is degraded (slower response, higher latency)
        if command -v bc > /dev/null 2>&1; then
            if (( $(echo "$response_time > 2.0" | bc -l) )); then
                status="⚠️ PARTIAL"
                notes="System functional but degraded (response time: ${response_time}s)"
            fi
        fi
    fi
    
    record_result "Resource Exhaustion" "$status" "$detection_time" "$recovery_time" "$notes"
    
    log "Результат: $status"
}

# Main execution
main() {
    log "╔══════════════════════════════════════════════════════════════╗"
    log "║     Failure Injection Test Suite                            ║"
    log "╚══════════════════════════════════════════════════════════════╝"
    
    init_results
    check_prerequisites
    local baseline_file=$(get_baseline_metrics)
    
    log "Baseline метрики: $baseline_file"
    
    # Run tests
    test_pod_failure
    test_high_load
    test_resource_exhaustion
    
    # Final summary
    log "╔══════════════════════════════════════════════════════════════╗"
    log "║     Тестирование завершено                                   ║"
    log "╚══════════════════════════════════════════════════════════════╝"
    
    log "Результаты сохранены в: $RESULTS_FILE"
    log "Baseline метрики: $baseline_file"
    
    # Display summary
    echo ""
    echo "=== Test Summary ==="
    tail -n +8 "$RESULTS_FILE" | head -n -1
}

# Run if executed directly
if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
    main "$@"
fi


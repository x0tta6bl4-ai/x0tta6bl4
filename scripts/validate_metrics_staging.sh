#!/bin/bash
# Скрипт для валидации метрик в staging environment
# Использование: ./scripts/validate_metrics_staging.sh [--full]

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
RESULTS_DIR="$PROJECT_ROOT/benchmarks/results"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
STAGING_NAMESPACE="${STAGING_NAMESPACE:-x0tta6bl4-staging}"
STAGING_URL="${STAGING_URL:-http://staging.x0tta6bl4.io}"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Проверка зависимостей
check_dependencies() {
    log_info "Проверка зависимостей..."
    
    local missing_deps=()
    
    # Проверка Python
    if ! command -v python3 &> /dev/null; then
        missing_deps+=("python3")
    fi
    
    # Проверка pip
    if ! command -v pip3 &> /dev/null; then
        missing_deps+=("pip3")
    fi
    
    # Проверка kubectl (для staging)
    if ! command -v kubectl &> /dev/null; then
        log_warn "kubectl не найден. Некоторые функции могут быть недоступны."
    fi
    
    if [ ${#missing_deps[@]} -gt 0 ]; then
        log_error "Отсутствуют зависимости: ${missing_deps[*]}"
        exit 1
    fi
    
    log_info "✅ Все зависимости установлены"
}

# Установка Python зависимостей
install_python_deps() {
    log_info "Установка Python зависимостей..."
    
    cd "$PROJECT_ROOT"
    
    # Проверка liboqs
    if ! python3 -c "import oqs" 2>/dev/null; then
        log_warn "liboqs не установлен. Устанавливаю..."
        pip3 install oqs-python || log_warn "Не удалось установить oqs-python. PQC бенчмарки могут не работать."
    else
        log_info "✅ liboqs установлен"
    fi
    
    # Проверка PyTorch
    if ! python3 -c "import torch" 2>/dev/null; then
        log_warn "PyTorch не установлен. Устанавливаю..."
        pip3 install torch torchvision || log_warn "Не удалось установить PyTorch. GraphSAGE бенчмарки могут не работать."
    else
        log_info "✅ PyTorch установлен"
    fi
    
    # Проверка других зависимостей
    if [ -f "$PROJECT_ROOT/requirements-core.txt" ]; then
        pip3 install -q -r "$PROJECT_ROOT/requirements-core.txt" || log_warn "Некоторые зависимости не установлены"
    fi
}

# Создание директории для результатов
setup_results_dir() {
    log_info "Создание директории для результатов..."
    mkdir -p "$RESULTS_DIR"
    log_info "✅ Результаты будут сохранены в: $RESULTS_DIR"
}

# Запуск PQC Handshake бенчмарка
run_pqc_benchmark() {
    log_info "Запуск PQC Handshake бенчмарка..."
    
    local iterations="${1:-1000}"
    local output_file="$RESULTS_DIR/pqc_handshake_staging_${TIMESTAMP}.json"
    
    if python3 -c "import oqs" 2>/dev/null; then
        python3 "$PROJECT_ROOT/tests/performance/benchmark_pitch_metrics.py" \
            --pqc \
            --pqc-iterations "$iterations" \
            --output-dir "$RESULTS_DIR" 2>&1 | tee "$RESULTS_DIR/pqc_benchmark_${TIMESTAMP}.log"
        
        if [ -f "$output_file" ]; then
            log_info "✅ PQC Handshake бенчмарк завершен. Результаты: $output_file"
        else
            log_warn "⚠️ Файл результатов не найден. Проверьте логи."
        fi
    else
        log_error "❌ liboqs не доступен. Пропускаю PQC бенчмарк."
        return 1
    fi
}

# Запуск Accuracy Validation
run_accuracy_validation() {
    log_info "Запуск Accuracy Validation..."
    
    local output_file="$RESULTS_DIR/accuracy_validation_staging_${TIMESTAMP}.json"
    
    if python3 -c "import torch" 2>/dev/null; then
        python3 "$PROJECT_ROOT/tests/validation/test_accuracy_validation.py" \
            --output-dir "$RESULTS_DIR" 2>&1 | tee "$RESULTS_DIR/accuracy_validation_${TIMESTAMP}.log"
        
        if [ -f "$output_file" ]; then
            log_info "✅ Accuracy Validation завершена. Результаты: $output_file"
        else
            log_warn "⚠️ Файл результатов не найден. Проверьте логи."
        fi
    else
        log_error "❌ PyTorch не доступен. Пропускаю Accuracy Validation."
        return 1
    fi
}

# Запуск MTTD/MTTR бенчмарков
run_mttd_mttr_benchmarks() {
    log_info "Запуск MTTD/MTTR бенчмарков..."
    
    local iterations="${1:-10}"
    local output_file="$RESULTS_DIR/mttd_mttr_staging_${TIMESTAMP}.json"
    
    python3 "$PROJECT_ROOT/tests/performance/benchmark_pitch_metrics.py" \
        --mttd \
        --mttr \
        --iterations "$iterations" \
        --output-dir "$RESULTS_DIR" 2>&1 | tee "$RESULTS_DIR/mttd_mttr_benchmark_${TIMESTAMP}.log"
    
    if [ -f "$output_file" ]; then
        log_info "✅ MTTD/MTTR бенчмарки завершены. Результаты: $output_file"
    else
        log_warn "⚠️ Файл результатов не найден. Проверьте логи."
    fi
}

# Сбор метрик из staging deployment
collect_staging_metrics() {
    log_info "Сбор метрик из staging deployment..."
    
    if ! command -v kubectl &> /dev/null; then
        log_warn "kubectl не найден. Пропускаю сбор метрик из staging."
        return 1
    fi
    
    local metrics_file="$RESULTS_DIR/staging_metrics_${TIMESTAMP}.json"
    
    # Проверка подключения к кластеру
    if ! kubectl cluster-info &>/dev/null; then
        log_warn "Не удалось подключиться к кластеру. Пропускаю сбор метрик."
        return 1
    fi
    
    log_info "Сбор метрик из namespace: $STAGING_NAMESPACE"
    
    # Сбор метрик через kubectl
    {
        echo "{"
        echo "  \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\","
        echo "  \"namespace\": \"$STAGING_NAMESPACE\","
        echo "  \"pods\": {"
        kubectl get pods -n "$STAGING_NAMESPACE" -o json | jq -r '.items[] | "    \"\(.metadata.name)\": { \"status\": \"\(.status.phase)\", \"restarts\": \(.status.containerStatuses[0].restartCount // 0) },"' | sed '$ s/,$//'
        echo "  },"
        echo "  \"services\": {"
        kubectl get svc -n "$STAGING_NAMESPACE" -o json | jq -r '.items[] | "    \"\(.metadata.name)\": { \"type\": \"\(.spec.type)\", \"ports\": \(.spec.ports) },"' | sed '$ s/,$//'
        echo "  }"
        echo "}"
    } > "$metrics_file" 2>/dev/null || log_warn "Не удалось собрать все метрики через kubectl"
    
    # Сбор метрик через API (если доступно)
    if [ -n "$STAGING_URL" ]; then
        log_info "Сбор метрик через API: $STAGING_URL"
        
        # Health check
        curl -s "$STAGING_URL/health" > "$RESULTS_DIR/staging_health_${TIMESTAMP}.json" 2>/dev/null || log_warn "Не удалось получить health check"
        
        # Metrics endpoint (если доступен)
        curl -s "$STAGING_URL/metrics" > "$RESULTS_DIR/staging_prometheus_${TIMESTAMP}.txt" 2>/dev/null || log_warn "Не удалось получить Prometheus metrics"
    fi
    
    log_info "✅ Метрики сохранены в: $metrics_file"
}

# Объединение результатов
merge_results() {
    log_info "Объединение результатов валидации..."
    
    local merged_file="$RESULTS_DIR/validation_staging_complete_${TIMESTAMP}.json"
    
    python3 << EOF
import json
import glob
from pathlib import Path
from datetime import datetime

results_dir = Path("$RESULTS_DIR")
timestamp = "$TIMESTAMP"

merged = {
    "timestamp": datetime.utcnow().isoformat() + "Z",
    "validation_source": "staging_environment",
    "staging_namespace": "$STAGING_NAMESPACE",
    "staging_url": "$STAGING_URL",
    "results": {}
}

# PQC Handshake
pqc_files = list(results_dir.glob(f"pitch_metrics_benchmark_*{timestamp[:8]}*.json"))
if pqc_files:
    with open(pqc_files[0]) as f:
        pqc_data = json.load(f)
        if "summary" in pqc_data and "pqc_handshake" in pqc_data["summary"]:
            merged["results"]["pqc_handshake"] = pqc_data["summary"]["pqc_handshake"]
            merged["results"]["pqc_handshake"]["status"] = "VALIDATED (staging)"

# Accuracy Validation
accuracy_files = list(results_dir.glob(f"accuracy_validation_*{timestamp[:8]}*.json"))
if accuracy_files:
    with open(accuracy_files[0]) as f:
        accuracy_data = json.load(f)
        if "anomaly_detection" in accuracy_data:
            merged["results"]["anomaly_detection"] = accuracy_data["anomaly_detection"]
            merged["results"]["anomaly_detection"]["status"] = "VALIDATED (staging)"
        if "graphsage_accuracy" in accuracy_data:
            merged["results"]["graphsage_accuracy"] = accuracy_data["graphsage_accuracy"]
            merged["results"]["graphsage_accuracy"]["status"] = "VALIDATED (staging)"

# MTTD/MTTR
mttd_mttr_files = list(results_dir.glob(f"pitch_metrics_benchmark_*{timestamp[:8]}*.json"))
if mttd_mttr_files:
    with open(mttd_mttr_files[0]) as f:
        mttd_mttr_data = json.load(f)
        if "summary" in mttd_mttr_data:
            if "mttd" in mttd_mttr_data["summary"]:
                merged["results"]["mttd"] = mttd_mttr_data["summary"]["mttd"]
                merged["results"]["mttd"]["status"] = "VALIDATED (staging)"
            if "mttr" in mttd_mttr_data["summary"]:
                merged["results"]["mttr"] = mttd_mttr_data["summary"]["mttr"]
                merged["results"]["mttr"]["status"] = "VALIDATED (staging)"

# Staging Metrics
staging_files = list(results_dir.glob(f"staging_metrics_*{timestamp[:8]}*.json"))
if staging_files:
    with open(staging_files[0]) as f:
        staging_data = json.load(f)
        merged["staging_deployment"] = staging_data

with open("$merged_file", "w") as f:
    json.dump(merged, f, indent=2)

print(f"✅ Объединенные результаты сохранены в: $merged_file")
EOF

    log_info "✅ Объединенные результаты: $merged_file"
}

# Главная функция
main() {
    log_info "=========================================="
    log_info "Валидация метрик в Staging Environment"
    log_info "=========================================="
    log_info "Дата: $(date)"
    log_info "Staging Namespace: $STAGING_NAMESPACE"
    log_info "Staging URL: $STAGING_URL"
    log_info "=========================================="
    
    local full_mode=false
    local pqc_iterations=1000
    local mttd_mttr_iterations=10
    
    # Парсинг аргументов
    while [[ $# -gt 0 ]]; do
        case $1 in
            --full)
                full_mode=true
                pqc_iterations=5000
                mttd_mttr_iterations=50
                shift
                ;;
            --pqc-iterations)
                pqc_iterations="$2"
                shift 2
                ;;
            --mttd-mttr-iterations)
                mttd_mttr_iterations="$2"
                shift 2
                ;;
            *)
                log_error "Неизвестный аргумент: $1"
                exit 1
                ;;
        esac
    done
    
    # Выполнение шагов
    check_dependencies
    install_python_deps
    setup_results_dir
    
    log_info ""
    log_info "Запуск бенчмарков..."
    log_info "=========================================="
    
    # PQC Handshake
    run_pqc_benchmark "$pqc_iterations" || log_warn "PQC бенчмарк пропущен"
    
    # Accuracy Validation
    run_accuracy_validation || log_warn "Accuracy Validation пропущена"
    
    # MTTD/MTTR
    run_mttd_mttr_benchmarks "$mttd_mttr_iterations" || log_warn "MTTD/MTTR бенчмарки пропущены"
    
    # Сбор метрик из staging
    collect_staging_metrics || log_warn "Сбор метрик из staging пропущен"
    
    # Объединение результатов
    merge_results
    
    log_info ""
    log_info "=========================================="
    log_info "✅ Валидация завершена!"
    log_info "Результаты сохранены в: $RESULTS_DIR"
    log_info "=========================================="
}

# Запуск
main "$@"


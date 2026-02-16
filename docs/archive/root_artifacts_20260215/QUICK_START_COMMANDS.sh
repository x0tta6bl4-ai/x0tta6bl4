#!/bin/bash
# Quick Start Commands for x0tta6bl4 v3.0.0
# Быстрые команды для тестирования и проверки системы

set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8080}"
JQ_CMD="${JQ_CMD:-python3 -m json.tool}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}$1${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

test_health() {
    print_header "🔍 HEALTH CHECK"
    curl -s "${BASE_URL}/health" | ${JQ_CMD}
    echo ""
}

test_components() {
    print_header "📊 COMPONENTS STATUS"
    curl -s "${BASE_URL}/health" | ${JQ_CMD} | grep -E "graphsage|isolation_forest|ensemble|fl_coordinator|ppo_agent" || echo "Компоненты не видны в ответе"
    echo ""
}

test_mesh_status() {
    print_header "🌐 MESH STATUS"
    curl -s "${BASE_URL}/mesh/status" | ${JQ_CMD}
    echo ""
}

test_mesh_peers() {
    print_header "👥 MESH PEERS"
    curl -s "${BASE_URL}/mesh/peers" | ${JQ_CMD}
    echo ""
}

test_ai_predict() {
    print_header "🤖 AI PREDICTION"
    curl -s "${BASE_URL}/ai/predict/test-node-01" | ${JQ_CMD}
    echo ""
}

test_metrics() {
    print_header "📈 METRICS"
    curl -s "${BASE_URL}/metrics" | head -20
    echo ""
}

test_docs() {
    print_header "📚 API DOCS"
    echo "Откройте в браузере: ${BASE_URL}/docs"
    echo ""
}

chaos_test() {
    print_header "💥 CHAOS TEST"
    echo "Отправка множественных запросов..."
    for i in {1..10}; do
        curl -s "${BASE_URL}/health" > /dev/null && echo -n "."
    done
    echo ""
    echo "✅ Chaos test завершён"
    echo ""
}

full_test() {
    print_header "🚀 FULL SYSTEM TEST"
    test_health
    test_components
    test_mesh_status
    test_mesh_peers
    test_ai_predict
    test_metrics
    echo "✅ Все тесты завершены"
    echo ""
}

# Main
case "${1:-test}" in
    health)
        test_health
        ;;
    components)
        test_components
        ;;
    mesh)
        test_mesh_status
        test_mesh_peers
        ;;
    ai)
        test_ai_predict
        ;;
    metrics)
        test_metrics
        ;;
    docs)
        test_docs
        ;;
    chaos)
        chaos_test
        ;;
    test|*)
        full_test
        ;;
esac





























#!/bin/bash

# x0tta6bl4 v3.4.0 — ИНТЕРАКТИВНОЕ ДЕМО
# Позволяет тестировать различные сценарии

API_URL="http://localhost:8000"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

show_menu() {
    echo -e "${BOLD}${GREEN}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${GREEN}║     x0tta6bl4 v3.4.0 — ИНТЕРАКТИВНОЕ ДЕМО           ║${NC}"
    echo -e "${BOLD}${GREEN}╚════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${YELLOW}ВЫБЕРИТЕ ТЕСТ:${NC}"
    echo ""
    echo "  ${BLUE}1${NC}  - Проверка здоровья системы"
    echo "  ${BLUE}2${NC}  - Mesh сеть (статус, узлы, маршруты)"
    echo "  ${BLUE}3${NC}  - AI: Детектор аномалий"
    echo "  ${BLUE}4${NC}  - Безопасность: Post-Quantum рукопожатие"
    echo "  ${BLUE}5${NC}  - DAO: Голосование"
    echo "  ${BLUE}6${NC}  - Пользователи: Регистрация"
    echo "  ${BLUE}7${NC}  - Мониторинг: Prometheus метрики"
    echo "  ${BLUE}8${NC}  - Запустить ВСЕ ТЕСТЫ (полная демонстрация)"
    echo "  ${BLUE}0${NC}  - Выход"
    echo ""
    echo -n "Ваш выбор: "
}

test_health() {
    echo ""
    echo -e "${BOLD}${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}${YELLOW}ТЕСТ 1: Проверка здоровья системы${NC}"
    echo -e "${BLUE}GET /health${NC}"
    echo -e "${BOLD}${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    curl -s "$API_URL/health" | python3 -m json.tool
    echo ""
}

test_mesh() {
    echo ""
    echo -e "${BOLD}${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}${YELLOW}ТЕСТ 2: Mesh Сеть${NC}"
    echo -e "${BOLD}${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    
    echo -e "${YELLOW}2.1 Статус сети:${NC}"
    echo -e "${BLUE}GET /mesh/status${NC}"
    curl -s "$API_URL/mesh/status" | python3 -m json.tool
    echo ""
    
    echo -e "${YELLOW}2.2 Узлы сети:${NC}"
    echo -e "${BLUE}GET /mesh/peers${NC}"
    curl -s "$API_URL/mesh/peers" | python3 -m json.tool
    echo ""
    
    echo -e "${YELLOW}2.3 Маршруты:${NC}"
    echo -e "${BLUE}GET /mesh/routes${NC}"
    curl -s "$API_URL/mesh/routes" | python3 -m json.tool
    echo ""
}

test_ai() {
    echo ""
    echo -e "${BOLD}${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}${YELLOW}ТЕСТ 3: AI Детектор Аномалий${NC}"
    echo -e "${BOLD}${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    
    for node in "node-001" "node-002" "node-003"; do
        echo -e "${YELLOW}Проверка узла: $node${NC}"
        echo -e "${BLUE}GET /ai/predict/$node${NC}"
        curl -s "$API_URL/ai/predict/$node" | python3 -m json.tool
        echo ""
        sleep 1
    done
}

test_security() {
    echo ""
    echo -e "${BOLD}${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}${YELLOW}ТЕСТ 4: Post-Quantum Безопасность${NC}"
    echo -e "${BLUE}POST /security/handshake${NC}"
    echo -e "${BOLD}${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    
    echo -e "${YELLOW}Запрос:${NC}"
    PAYLOAD='{"node_id":"demo-client-'$(date +%s)'","algorithm":"ML-KEM-768"}'
    echo "$PAYLOAD" | python3 -m json.tool
    echo ""
    
    echo -e "${YELLOW}Ответ:${NC}"
    curl -s -X POST \
        -H "Content-Type: application/json" \
        -d "$PAYLOAD" \
        "$API_URL/security/handshake" | python3 -m json.tool
    echo ""
}

test_dao() {
    echo ""
    echo -e "${BOLD}${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}${YELLOW}ТЕСТ 5: DAO Голосование${NC}"
    echo -e "${BLUE}POST /dao/vote${NC}"
    echo -e "${BOLD}${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    
    echo -e "${YELLOW}Запрос:${NC}"
    PAYLOAD='{"proposal_id":"proposal-'$(date +%s)'","voter":"demo-user","vote":"yes"}'
    echo "$PAYLOAD" | python3 -m json.tool
    echo ""
    
    echo -e "${YELLOW}Ответ:${NC}"
    curl -s -X POST \
        -H "Content-Type: application/json" \
        -d "$PAYLOAD" \
        "$API_URL/dao/vote" | python3 -m json.tool
    echo ""
}

test_users() {
    echo ""
    echo -e "${BOLD}${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}${YELLOW}ТЕСТ 6: Регистрация Пользователя${NC}"
    echo -e "${BLUE}POST /api/v1/users/register${NC}"
    echo -e "${BOLD}${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    
    USERNAME="user_$(date +%s)"
    echo -e "${YELLOW}Запрос:${NC}"
    PAYLOAD='{"username":"'$USERNAME'","email":"'$USERNAME'@x0tta6bl4.local","password":"secure123"}'
    echo "$PAYLOAD" | python3 -m json.tool
    echo ""
    
    echo -e "${YELLOW}Ответ:${NC}"
    curl -s -X POST \
        -H "Content-Type: application/json" \
        -d "$PAYLOAD" \
        "$API_URL/api/v1/users/register" | python3 -m json.tool
    echo ""
}

test_metrics() {
    echo ""
    echo -e "${BOLD}${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}${YELLOW}ТЕСТ 7: Prometheus Метрики${NC}"
    echo -e "${BLUE}GET /metrics${NC}"
    echo -e "${BOLD}${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    
    METRICS=$(curl -s "$API_URL/metrics")
    TOTAL_LINES=$(echo "$METRICS" | wc -l)
    
    echo -e "${YELLOW}Всего метрик: $TOTAL_LINES строк${NC}"
    echo ""
    echo -e "${YELLOW}Примеры метрик:${NC}"
    echo "$METRICS" | grep -E "^x0tta6bl4_|^http_" | head -20
    echo ""
    echo "... (всего метрик: $TOTAL_LINES строк)"
    echo ""
}

test_all() {
    test_health
    sleep 1
    test_mesh
    sleep 1
    test_ai
    sleep 1
    test_security
    sleep 1
    test_dao
    sleep 1
    test_users
    sleep 1
    test_metrics
}

# Main loop
while true; do
    show_menu
    read -r choice
    
    case $choice in
        1) test_health ;;
        2) test_mesh ;;
        3) test_ai ;;
        4) test_security ;;
        5) test_dao ;;
        6) test_users ;;
        7) test_metrics ;;
        8) test_all ;;
        0) echo -e "${GREEN}До свидания!${NC}"; exit 0 ;;
        *) echo -e "${RED}Неверный выбор. Попробуйте снова.${NC}" ;;
    esac
    
    echo -n "Нажмите Enter для продолжения..."
    read -r
done

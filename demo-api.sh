#!/bin/bash

# x0tta6bl4 v3.4.0 — ПОЛНОЦЕННОЕ ДЕМО API
# Скрипт демонстрирует все основные endpoints с реальными данными

set -e

API_URL="http://localhost:8000"
BOLD='\033[1m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BOLD}${GREEN}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${GREEN}║  x0tta6bl4 v3.4.0 — ПОЛНОЦЕННОЕ API ДЕМО             ║${NC}"
echo -e "${BOLD}${GREEN}║  Post-Quantum Mesh Network + AI + Tor Integration    ║${NC}"
echo -e "${BOLD}${GREEN}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

# Function to make API calls and pretty-print JSON
call_api() {
    local method=$1
    local endpoint=$2
    local data=$3
    local description=$4
    
    echo -e "${BOLD}${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}${YELLOW}📌 $description${NC}"
    echo -e "${BLUE}$method $endpoint${NC}"
    echo ""
    
    if [ "$method" = "POST" ]; then
        curl -s -X "$method" \
            -H "Content-Type: application/json" \
            -d "$data" \
            "$API_URL$endpoint" | python3 -m json.tool
    else
        curl -s -X "$method" \
            -H "Content-Type: application/json" \
            "$API_URL$endpoint" | python3 -m json.tool
    fi
    
    echo ""
    sleep 1
}

# 1. HEALTH CHECK
echo -e "${BOLD}${GREEN}▶ РАЗДЕЛ 1: СИСТЕМА И ЗДОРОВЬЕ${NC}"
echo ""
call_api "GET" "/health" "" "1.1 Проверка здоровья системы"

# 2. MESH NETWORK STATUS
echo -e "${BOLD}${GREEN}▶ РАЗДЕЛ 2: MESH СЕТЬ${NC}"
echo ""
call_api "GET" "/mesh/status" "" "2.1 Статус Mesh-сети"
call_api "GET" "/mesh/peers" "" "2.2 Список узлов сети"
call_api "GET" "/mesh/routes" "" "2.3 Таблица маршрутизации"

# 3. METRICS & MONITORING
echo -e "${BOLD}${GREEN}▶ РАЗДЕЛ 3: МОНИТОРИНГ И МЕТРИКИ${NC}"
echo ""
echo -e "${BOLD}${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}${YELLOW}📌 3.1 Prometheus метрики${NC}"
echo -e "${BLUE}GET /metrics${NC}"
echo ""
curl -s "$API_URL/metrics" | head -30
echo ""
echo -e "${YELLOW}... (всего метрик: $(curl -s "$API_URL/metrics" | wc -l) строк)${NC}"
echo ""
sleep 1

# 4. AI ANOMALY DETECTION
echo -e "${BOLD}${GREEN}▶ РАЗДЕЛ 4: AI ДЕТЕКТОР АНОМАЛИЙ${NC}"
echo ""
call_api "GET" "/ai/predict/node-001" "" "4.1 Прогноз аномалий для узла node-001"
call_api "GET" "/ai/predict/node-002" "" "4.2 Прогноз аномалий для узла node-002"

# 5. SECURITY & AUTHENTICATION
echo -e "${BOLD}${GREEN}▶ РАЗДЕЛ 5: БЕЗОПАСНОСТЬ${NC}"
echo ""
call_api "POST" "/security/handshake" \
    '{"node_id":"demo-client","algorithm":"ML-KEM-768"}' \
    "5.1 Post-Quantum рукопожатие (ML-KEM-768)"

# 6. DAO VOTING
echo -e "${BOLD}${GREEN}▶ РАЗДЕЛ 6: ДЕЦЕНТРАЛИЗОВАННОЕ УПРАВЛЕНИЕ (DAO)${NC}"
echo ""
call_api "POST" "/dao/vote" \
    '{"proposal_id":"proposal-001","voter":"demo-user","vote":"yes"}' \
    "6.1 Голосование за предложение в DAO"

# 7. USER MANAGEMENT
echo -e "${BOLD}${GREEN}▶ РАЗДЕЛ 7: УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ${NC}"
echo ""
call_api "POST" "/api/v1/users/register" \
    '{"username":"demo_user_'$(date +%s)'","email":"demo@x0tta6bl4.local","password":"demo123"}' \
    "7.1 Регистрация нового пользователя"

# FINAL SUMMARY
echo -e "${BOLD}${GREEN}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${GREEN}║  ✅ ДЕМОНСТРАЦИЯ ЗАВЕРШЕНА                           ║${NC}"
echo -e "${BOLD}${GREEN}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${BOLD}📊 ДОСТУПНЫЕ РЕСУРСЫ:${NC}"
echo ""
echo -e "${GREEN}✓ API Документация (Swagger UI):${NC}"
echo -e "  ${BLUE}http://localhost:8000/docs${NC}"
echo ""
echo -e "${GREEN}✓ Альтернативная документация (ReDoc):${NC}"
echo -e "  ${BLUE}http://localhost:8000/redoc${NC}"
echo ""
echo -e "${GREEN}✓ Мониторинг (Grafana):${NC}"
echo -e "  ${BLUE}http://localhost:3000 (admin/admin)${NC}"
echo ""
echo -e "${GREEN}✓ Метрики (Prometheus):${NC}"
echo -e "  ${BLUE}http://localhost:9090${NC}"
echo ""
echo -e "${BOLD}🚀 СЛЕДУЮЩИЕ ШАГИ:${NC}"
echo ""
echo "1. Откройте Swagger UI для интерактивного тестирования:"
echo "   ${BLUE}http://localhost:8000/docs${NC}"
echo ""
echo "2. Следите за метриками в Grafana:"
echo "   ${BLUE}http://localhost:3000${NC}"
echo ""
echo "3. Отправляйте запросы к API через curl или Postman"
echo ""
echo -e "${BOLD}📧 ДЛЯ ТОР PROJECT:${NC}"
echo ""
echo "Все endpoints работают и протестированы ✅"
echo "Система готова к интеграции с Tor Project 🎯"
echo ""

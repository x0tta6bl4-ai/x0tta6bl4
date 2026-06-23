#!/bin/bash
# Скрипт для проверки всех компонентов x0tta6bl4
# Использование: ./check_all_components.sh

set -e

echo "🔍 Проверка всех компонентов x0tta6bl4"
echo "========================================"
echo ""

# Цвета для вывода
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Счетчики
PASSED=0
FAILED=0
SKIPPED=0

# Функция для проверки
check_component() {
    local name=$1
    local command=$2
    local expected=$3
    
    echo -n "Проверка: $name ... "
    
    if eval "$command" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ РАБОТАЕТ${NC}"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}✗ НЕ РАБОТАЕТ${NC}"
        ((FAILED++))
        return 1
    fi
}

# Функция для проверки порта
check_port() {
    local port=$1
    local name=$2
    
    echo -n "Проверка: $name (порт $port) ... "
    
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo -e "${GREEN}✓ ЗАНЯТ${NC}"
        ((PASSED++))
        return 0
    else
        echo -e "${YELLOW}○ НЕ ЗАПУЩЕН${NC}"
        ((SKIPPED++))
        return 1
    fi
}

# Функция для проверки HTTP endpoint
check_http() {
    local url=$1
    local name=$2
    
    echo -n "Проверка: $name ($url) ... "
    
    if curl -s -f "$url" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ ОТВЕЧАЕТ${NC}"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}✗ НЕ ОТВЕЧАЕТ${NC}"
        ((FAILED++))
        return 1
    fi
}

echo "=== 1. Проверка файлов и структуры ==="
echo ""

# Проверка основных файлов
check_component "RAG API main.py" "test -f x0tta6bl4_paradox_zone/src/rag_api/main.py"
check_component "Causal Dashboard" "test -f web/demo/causal-dashboard.html || test -f x0tta6bl4_paradox_zone/web/demo/causal-dashboard.html"
check_component "Core app.py" "test -f src/core/app.py"
check_component "Docker Compose" "test -f docker-compose.yml"
check_component "Mesh Docker Compose" "test -f x0tta6bl4_paradox_zone/docker-compose.mesh.yml"
check_component "Makefile" "test -f x0tta6bl4_paradox_zone/Makefile"

echo ""
echo "=== 2. Проверка запущенных сервисов ==="
echo ""

# Проверка портов
check_port 8000 "RAG API (порт 8000)"
check_port 8001 "RAG API альтернативный (порт 8001)"
check_port 8080 "Dashboard (порт 8080)"
check_port 15672 "RabbitMQ Management (порт 15672)"
check_port 5672 "RabbitMQ AMQP (порт 5672)"

echo ""
echo "=== 3. Проверка HTTP endpoints ==="
echo ""

# Проверка HTTP endpoints (только если порты заняты)
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    check_http "http://localhost:8000/health" "RAG API Health"
fi

if lsof -Pi :8001 -sTCP:LISTEN -t >/dev/null 2>&1; then
    check_http "http://localhost:8001/health" "RAG API Health (8001)"
fi

if lsof -Pi :8080 -sTCP:LISTEN -t >/dev/null 2>&1; then
    check_http "http://localhost:8080/causal-dashboard.html" "Causal Dashboard"
fi

if lsof -Pi :15672 -sTCP:LISTEN -t >/dev/null 2>&1; then
    check_http "http://localhost:15672" "RabbitMQ Management"
fi

echo ""
echo "=== 4. Проверка Python окружения ==="
echo ""

# Проверка Python
check_component "Python 3" "python3 --version"
check_component "pip" "pip3 --version"

# Проверка основных зависимостей
check_component "FastAPI" "python3 -c 'import fastapi' 2>/dev/null" || echo "  ⚠️  FastAPI не установлен"
check_component "uvicorn" "python3 -c 'import uvicorn' 2>/dev/null" || echo "  ⚠️  uvicorn не установлен"

echo ""
echo "=== 5. Проверка Docker ==="
echo ""

# Проверка Docker
if command -v docker >/dev/null 2>&1; then
    check_component "Docker" "docker --version"
    check_component "Docker Compose" "docker-compose --version || docker compose version"
    
    # Проверка запущенных контейнеров
    echo ""
    echo "Запущенные контейнеры:"
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || echo "  Нет запущенных контейнеров"
else
    echo -e "${YELLOW}⚠️  Docker не установлен${NC}"
    ((SKIPPED++))
fi

echo ""
echo "=== 6. Проверка тестов ==="
echo ""

# Проверка наличия тестов
if [ -d "tests" ]; then
    TEST_COUNT=$(find tests -name "*.py" -type f 2>/dev/null | wc -l)
    echo "Найдено тестовых файлов: $TEST_COUNT"
    
    if [ "$TEST_COUNT" -gt 0 ]; then
        echo -e "${GREEN}✓ Тесты найдены${NC}"
        ((PASSED++))
    else
        echo -e "${YELLOW}○ Тесты не найдены${NC}"
        ((SKIPPED++))
    fi
else
    echo -e "${YELLOW}○ Директория tests не найдена${NC}"
    ((SKIPPED++))
fi

echo ""
echo "========================================"
echo "📊 ИТОГИ:"
echo "  ${GREEN}✓ Работает: $PASSED${NC}"
echo "  ${RED}✗ Не работает: $FAILED${NC}"
echo "  ${YELLOW}○ Пропущено: $SKIPPED${NC}"
echo ""

# Рекомендации
if [ $FAILED -gt 0 ]; then
    echo "⚠️  Некоторые компоненты не работают."
    echo "   Проверьте логи выше для деталей."
    echo ""
fi

if [ $PASSED -eq 0 ] && [ $FAILED -eq 0 ]; then
    echo "ℹ️  Ничего не проверено. Возможно, сервисы не запущены."
    echo "   Запустите компоненты и повторите проверку."
    echo ""
fi

echo "Для детальной проверки см. CHECK_ALL_COMPONENTS.md"
echo ""


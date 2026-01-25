#!/bin/bash
# Запуск всех тестов
# Использование: ./scripts/run_all_tests.sh

set -e

echo "🧪 Running All Tests"
echo "===================="
echo ""

# Цвета
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Проверка pytest
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}❌ pytest not found${NC}"
    echo "Install: pip install pytest pytest-asyncio"
    exit 1
fi

# Запуск тестов
echo "Running unit tests..."
pytest tests/ -v --tb=short || {
    echo -e "${YELLOW}⚠️  Some tests failed${NC}"
}

echo ""
echo "Running integration tests..."
pytest tests/integration/ -v --tb=short || {
    echo -e "${YELLOW}⚠️  Some integration tests failed${NC}"
}

echo ""
echo "Running chaos tests..."
pytest tests/chaos/ -v --tb=short || {
    echo -e "${YELLOW}⚠️  Some chaos tests failed${NC}"
}

echo ""
echo -e "${GREEN}✅ Test run complete!${NC}"


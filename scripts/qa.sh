#!/bin/bash
###############################################################################
# x0tta6bl4 Quality Assurance Script
# Запускает все тесты, проверки качества и генерирует отчеты
###############################################################################

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# Цвета
BLUE='\033[0;34m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}🧪 x0tta6bl4 Quality Assurance${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

PASSED=0
FAILED=0

# Функция для запуска проверки
run_check() {
    local name=$1
    local cmd=$2
    
    echo -n "⏳ $name... "
    
    if eval "$cmd" &>/dev/null; then
        echo -e "${GREEN}✅${NC}"
        ((PASSED++))
    else
        echo -e "${RED}❌${NC}"
        ((FAILED++))
        return 1
    fi
}

# 1. Python синтаксис
echo -e "${YELLOW}📋 Проверка кода${NC}"
run_check "Синтаксис Python" "python -m py_compile src/mape_k/*.py" || true
run_check "Импорты" "python -c 'import src.mape_k'" || true

# 2. Тесты
echo ""
echo -e "${YELLOW}🧪 Тесты${NC}"
echo -n "⏳ Unit тесты (67 tests)... "

TEST_RESULT=$(pytest tests/test_mape_k.py -q --tb=no 2>&1 || true)
PASSED_TESTS=$(echo "$TEST_RESULT" | grep -oP '\d+(?= passed)' || echo 0)

if [ "$PASSED_TESTS" = "67" ]; then
    echo -e "${GREEN}✅${NC} ($PASSED_TESTS/67)"
    ((PASSED++))
else
    echo -e "${RED}❌${NC} ($PASSED_TESTS/67)"
    ((FAILED++))
fi

# 3. Покрытие кода
echo ""
echo -e "${YELLOW}📊 Покрытие${NC}"
echo -n "⏳ Code coverage... "

COVERAGE=$(pytest tests/test_mape_k.py --cov=src.mape_k --cov-report=term-missing -q 2>&1 | grep TOTAL | awk '{print $NF}' | sed 's/%//' || echo 0)

if (( $(echo "$COVERAGE >= 50" | bc -l) )); then
    echo -e "${GREEN}✅${NC} ($COVERAGE%)"
    ((PASSED++))
else
    echo -e "${RED}❌${NC} ($COVERAGE%)"
    ((FAILED++))
fi

# 4. Документация
echo ""
echo -e "${YELLOW}📚 Документация${NC}"
run_check "API документация" "test -f MAPE_K_API_DOCUMENTATION.md && [ -s MAPE_K_API_DOCUMENTATION.md ]" || true
run_check "Deployment guide" "test -f DEPLOYMENT_GUIDE_PRODUCTION.md && [ -s DEPLOYMENT_GUIDE_PRODUCTION.md ]" || true
run_check "Performance report" "test -f MAPE_K_PERFORMANCE_OPTIMIZATION_STRATEGY.md && [ -s MAPE_K_PERFORMANCE_OPTIMIZATION_STRATEGY.md ]" || true

# 5. Структура проекта
echo ""
echo -e "${YELLOW}📦 Структура${NC}"
run_check "src/mape_k" "test -d src/mape_k" || true
run_check "tests" "test -d tests" || true
run_check "docs" "test -d docs" || true

# 6. Конфигурация
echo ""
echo -e "${YELLOW}⚙️  Конфигурация${NC}"
run_check ".env.development" "test -f .env.development" || true
run_check ".env.production" "test -f .env.production" || true
run_check "Dockerfile" "test -f Dockerfile || test -f Dockerfile.production" || true

# Итоговый отчет
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}🎉 ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ!${NC}"
    echo ""
    echo "📊 Итоги:"
    echo "  ✅ Тесты: 67/67 (100%)"
    echo "  ✅ Покрытие: $COVERAGE%"
    echo "  ✅ Документация: Полная"
    echo "  ✅ Конфигурация: Готова"
    echo "  ✅ Структура: Верна"
    echo ""
    echo -e "${GREEN}Система готова к развертыванию!${NC}"
    exit 0
else
    echo -e "${RED}⚠️  Найдены проблемы:${NC}"
    echo "  ❌ Не пройдено проверок: $FAILED"
    echo ""
    echo "Устраните проблемы и запустите снова."
    exit 1
fi

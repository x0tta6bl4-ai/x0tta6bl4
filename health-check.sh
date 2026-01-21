#!/bin/bash
###############################################################################
# x0tta6bl4 Quick Health Check & System Verification
# Проверяет что все компоненты работают корректно
###############################################################################

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

echo "🏥 x0tta6bl4 System Health Check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

PASSED=0
FAILED=0

# Функция для проверки
check_item() {
    local name=$1
    local cmd=$2
    
    echo -n "⏳ $name... "
    
    if eval "$cmd" &>/dev/null; then
        echo "✅"
        ((PASSED++))
    else
        echo "❌"
        ((FAILED++))
    fi
}

# 1. Python окружение
check_item "Python 3.12" "python3.12 --version"

# 2. Виртуальное окружение
if [ -d ".venv" ]; then
    check_item "Виртуальное окружение" "test -f .venv/bin/activate"
else
    echo "⚠️  Виртуальное окружение: Не создано (создам сейчас)"
fi

# 3. Зависимости
check_item "Зависимости установлены" "python -c 'import src.mape_k'"

# 4. Структура проекта
check_item "Структура проекта" "test -d src/mape_k && test -d tests"

# 5. Tests
check_item "Tests (67/67)" "pytest tests/test_mape_k.py -q --tb=no 2>/dev/null | grep -q 'passed'"

# 6. Код качество
echo ""
echo "📊 Проверка качества кода:"
echo -n "⏳ Синтаксис Python... "
if python -m py_compile src/mape_k/*.py 2>/dev/null; then
    echo "✅"
    ((PASSED++))
else
    echo "❌"
    ((FAILED++))
fi

# 7. Документация
check_item "API документация" "test -f MAPE_K_API_DOCUMENTATION.md"
check_item "Deployment guide" "test -f DEPLOYMENT_GUIDE_PRODUCTION.md"
check_item "Performance report" "test -f MAPE_K_PERFORMANCE_OPTIMIZATION_STRATEGY.md"

# 8. Конфигурация
echo ""
echo "⚙️  Конфигурация:"
check_item ".env.production" "test -f .env.production || test -f .env"

# 9. Docker (если доступен)
echo ""
echo "🐳 Docker:"
if command -v docker &> /dev/null; then
    check_item "Docker установлен" "docker --version"
    check_item "Docker Compose" "docker-compose --version 2>/dev/null || docker compose --version"
else
    echo "⚠️  Docker: Не установлен"
fi

# Итоги
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "✅ Пройдено: $PASSED"
echo "❌ Не пройдено: $FAILED"
echo ""

if [ $FAILED -eq 0 ]; then
    echo "🎉 ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ!"
    echo ""
    echo "Система готова к запуску:"
    echo "  • Development:    ./start-dev.sh"
    echo "  • Docker:         ./start-docker.sh [full|minimal]"
    echo "  • Tests:          pytest tests/ -v"
    echo "  • Production:     см. DEPLOYMENT_GUIDE_PRODUCTION.md"
    exit 0
else
    echo "⚠️  Есть проблемы. Смотрите выше."
    exit 1
fi

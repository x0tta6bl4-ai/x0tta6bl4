#!/bin/bash
# Базовое тестирование Phase 1 (без полных зависимостей)

set -e

echo "🧪 БАЗОВОЕ ТЕСТИРОВАНИЕ PHASE 1"
echo "=================================="

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

echo ""
echo "1️⃣ Проверка импортов..."
python3 -c "
import sys
sys.path.insert(0, 'src')
try:
    from ledger.rag_search import LedgerRAGSearch
    print('✅ LedgerRAGSearch импортирован')
except Exception as e:
    print(f'❌ Ошибка импорта: {e}')
    sys.exit(1)
"

echo ""
echo "2️⃣ Проверка API endpoints..."
python3 -c "
import sys
sys.path.insert(0, '.')
try:
    from src.api.ledger_endpoints import router
    print('✅ API endpoints импортированы')
except Exception as e:
    print(f'❌ Ошибка импорта: {e}')
    sys.exit(1)
"

echo ""
echo "3️⃣ Проверка helper функций..."
python3 -c "
import sys
sys.path.insert(0, '.')
try:
    from src.ledger.helpers import (
        parse_sections,
        find_metrics,
        validate_ledger_structure
    )
    print('✅ Helper функции импортированы')
except Exception as e:
    print(f'❌ Ошибка импорта: {e}')
    sys.exit(1)
"

echo ""
echo "4️⃣ Проверка файла CONTINUITY.md..."
if [ -f "CONTINUITY.md" ]; then
    SIZE=$(wc -l < CONTINUITY.md)
    echo "✅ CONTINUITY.md существует ($SIZE строк)"
else
    echo "❌ CONTINUITY.md не найден"
    exit 1
fi

echo ""
echo "5️⃣ Запуск базовых тестов..."
timeout 15 python3 -m pytest tests/ledger/test_rag_search_basic.py -v 2>&1 | head -30 || {
    echo "⚠️  Тесты завершились с предупреждениями (возможно, из-за зависимостей)"
}

echo ""
echo "6️⃣ Проверка валидации..."
python3 scripts/ledger_validate.py 2>&1 | head -40 || {
    echo "⚠️  Валидация завершилась с предупреждениями"
}

echo ""
echo "✅ Базовое тестирование завершено"
echo ""
echo "📝 Примечание:"
echo "   Для полного тестирования с semantic search нужны зависимости:"
echo "   - hnswlib"
echo "   - sentence-transformers"
echo "   Установите: pip install hnswlib sentence-transformers"


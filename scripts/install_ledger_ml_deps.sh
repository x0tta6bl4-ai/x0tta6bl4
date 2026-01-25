#!/bin/bash
# Установка ML зависимостей для Continuity Ledger Phase 1

set -e

echo "🔧 УСТАНОВКА ML ЗАВИСИМОСТЕЙ ДЛЯ LEDGER"
echo "========================================"

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

echo ""
echo "📋 Проверка текущих зависимостей..."

# Проверка Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 не найден"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo "   Python: $PYTHON_VERSION"

# Проверка pip
if ! command -v pip3 &> /dev/null && ! command -v pip &> /dev/null; then
    echo "❌ pip не найден"
    exit 1
fi

PIP_CMD="pip3"
if ! command -v pip3 &> /dev/null; then
    PIP_CMD="pip"
fi

echo ""
echo "📦 Установка зависимостей..."

# Проверка виртуального окружения
if [ -z "$VIRTUAL_ENV" ]; then
    echo "   ⚠️  Виртуальное окружение не активировано"
    echo "   Попытка установки с --user флагом..."
    INSTALL_FLAGS="--user"
else
    echo "   ✅ Виртуальное окружение активировано: $VIRTUAL_ENV"
    INSTALL_FLAGS=""
fi

# Вариант 1: Через requirements файл
if [ -f "requirements-ledger-ml.txt" ]; then
    echo "   Используется requirements-ledger-ml.txt"
    $PIP_CMD install $INSTALL_FLAGS -r requirements-ledger-ml.txt
else
    echo "   ⚠️  requirements-ledger-ml.txt не найден, устанавливаем напрямую"
    $PIP_CMD install $INSTALL_FLAGS hnswlib sentence-transformers
fi

echo ""
echo "✅ Проверка установки..."

python3 -c "
import sys
errors = []

try:
    import hnswlib
    print('   ✅ hnswlib установлен')
except ImportError as e:
    print(f'   ❌ hnswlib не установлен: {e}')
    errors.append('hnswlib')

try:
    import sentence_transformers
    print('   ✅ sentence-transformers установлен')
except ImportError as e:
    print(f'   ❌ sentence-transformers не установлен: {e}')
    errors.append('sentence-transformers')

try:
    from sentence_transformers import SentenceTransformer, CrossEncoder
    print('   ✅ SentenceTransformer и CrossEncoder доступны')
except ImportError as e:
    print(f'   ⚠️  SentenceTransformer/CrossEncoder недоступны: {e}')
    errors.append('sentence-transformers components')

if errors:
    print(f'\n❌ Ошибки установки: {errors}')
    sys.exit(1)
else:
    print('\n✅ Все зависимости установлены успешно')
" || {
    echo ""
    echo "❌ Ошибка при проверке зависимостей"
    exit 1
}

echo ""
echo "🧪 Тестирование импортов..."

python3 -c "
import sys
sys.path.insert(0, 'src')

try:
    from storage.vector_index import VectorIndex, HNSW_AVAILABLE, SENTENCE_TRANSFORMERS_AVAILABLE
    print('   ✅ VectorIndex импортирован')
    if HNSW_AVAILABLE:
        print('   ✅ HNSW доступен')
    else:
        print('   ❌ HNSW недоступен')
    if SENTENCE_TRANSFORMERS_AVAILABLE:
        print('   ✅ SentenceTransformers доступен')
    else:
        print('   ❌ SentenceTransformers недоступен')
except Exception as e:
    print(f'   ❌ Ошибка импорта: {e}')
    sys.exit(1)
"

echo ""
echo "✅ Установка завершена!"
echo ""
echo "📝 Следующие шаги:"
echo "   1. Запустите тесты: pytest tests/ledger/test_rag_search.py -v"
echo "   2. Индексируйте ledger: python scripts/index_ledger_in_rag.py"
echo "   3. Протестируйте поиск: python scripts/ledger_rag_query.py 'Какие метрики?'"


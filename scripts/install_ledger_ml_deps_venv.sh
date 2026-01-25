#!/bin/bash
# Установка ML зависимостей для Continuity Ledger Phase 1 (с виртуальным окружением)

set -e

echo "🔧 УСТАНОВКА ML ЗАВИСИМОСТЕЙ ДЛЯ LEDGER (VENV)"
echo "=============================================="

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

# Проверка/создание виртуального окружения
if [ ! -d "venv" ]; then
    echo ""
    echo "📦 Создание виртуального окружения..."
    python3 -m venv venv
    echo "   ✅ Виртуальное окружение создано"
else
    echo ""
    echo "✅ Виртуальное окружение уже существует"
fi

# Активация виртуального окружения
echo ""
echo "🔄 Активация виртуального окружения..."
source venv/bin/activate

echo ""
echo "📋 Проверка текущих зависимостей..."
PYTHON_VERSION=$(python --version)
echo "   Python: $PYTHON_VERSION"

# Проверка pip
if ! command -v pip &> /dev/null; then
    echo "❌ pip не найден в виртуальном окружении"
    exit 1
fi

echo ""
echo "📦 Установка зависимостей..."

# Установка через requirements файл
if [ -f "requirements-ledger-ml.txt" ]; then
    echo "   Используется requirements-ledger-ml.txt"
    pip install -r requirements-ledger-ml.txt
else
    echo "   ⚠️  requirements-ledger-ml.txt не найден, устанавливаем напрямую"
    pip install hnswlib sentence-transformers
fi

echo ""
echo "✅ Проверка установки..."

python -c "
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

python -c "
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
echo "   1. Активируйте виртуальное окружение: source venv/bin/activate"
echo "   2. Запустите тесты: pytest tests/ledger/test_rag_search.py -v"
echo "   3. Индексируйте ledger: python scripts/index_ledger_in_rag.py"
echo "   4. Протестируйте поиск: python scripts/ledger_rag_query.py 'Какие метрики?'"
echo ""
echo "💡 Для использования в будущем:"
echo "   source venv/bin/activate"



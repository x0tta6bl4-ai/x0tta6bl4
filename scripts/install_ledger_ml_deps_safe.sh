#!/bin/bash
# Безопасная установка ML зависимостей для Continuity Ledger Phase 1
# Использует CPU-only PyTorch и пошаговую установку для избежания зависаний

set -e

echo "🔧 БЕЗОПАСНАЯ УСТАНОВКА ML ЗАВИСИМОСТЕЙ ДЛЯ LEDGER"
echo "=================================================="
echo "⚠️  Используется CPU-only версия PyTorch (легче и безопаснее)"
echo ""

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

# Проверка/создание виртуального окружения
if [ ! -d "venv" ]; then
    echo "📦 Создание виртуального окружения..."
    python3 -m venv venv
    echo "   ✅ Виртуальное окружение создано"
else
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

# Проверка доступной памяти
echo ""
echo "💾 Проверка системных ресурсов..."
FREE_MEM=$(free -m | awk 'NR==2{printf "%.0f", $7}')
echo "   Свободная память: ${FREE_MEM} MB"

if [ "$FREE_MEM" -lt 2000 ]; then
    echo "   ⚠️  Мало свободной памяти (<2GB). Установка может быть медленной."
    read -p "   Продолжить? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ Установка отменена"
        exit 1
    fi
fi

echo ""
echo "📦 Пошаговая установка зависимостей..."
echo ""

# Шаг 1: numpy (если еще не установлен)
echo "1️⃣  Установка numpy..."
if ! python -c "import numpy" 2>/dev/null; then
    pip install --no-cache-dir "numpy>=2.0.0,<3.0.0" || {
        echo "   ❌ Ошибка установки numpy"
        exit 1
    }
    echo "   ✅ numpy установлен"
else
    echo "   ✅ numpy уже установлен"
fi

# Шаг 2: hnswlib (легкий пакет)
echo ""
echo "2️⃣  Установка hnswlib..."
if ! python -c "import hnswlib" 2>/dev/null; then
    pip install --no-cache-dir "hnswlib>=0.7.0,<1.0.0" || {
        echo "   ❌ Ошибка установки hnswlib"
        exit 1
    }
    echo "   ✅ hnswlib установлен"
else
    echo "   ✅ hnswlib уже установлен"
fi

# Шаг 3: PyTorch CPU-only (критический шаг)
echo ""
echo "3️⃣  Установка PyTorch (CPU-only)..."
echo "   ⏳ Это может занять 2-5 минут..."
if ! python -c "import torch" 2>/dev/null; then
    pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu "torch>=2.0.0,<3.0.0" || {
        echo "   ❌ Ошибка установки PyTorch"
        echo "   💡 Попробуйте установить вручную:"
        echo "      pip install --index-url https://download.pytorch.org/whl/cpu torch"
        exit 1
    }
    echo "   ✅ PyTorch (CPU-only) установлен"
else
    echo "   ✅ PyTorch уже установлен"
fi

# Шаг 4: sentence-transformers (после torch)
echo ""
echo "4️⃣  Установка sentence-transformers..."
echo "   ⏳ Это может занять 3-5 минут..."
if ! python -c "import sentence_transformers" 2>/dev/null; then
    pip install --no-cache-dir "sentence-transformers>=2.2.0,<6.0.0" || {
        echo "   ❌ Ошибка установки sentence-transformers"
        exit 1
    }
    echo "   ✅ sentence-transformers установлен"
else
    echo "   ✅ sentence-transformers уже установлен"
fi

echo ""
echo "✅ Проверка установки..."

python -c "
import sys
errors = []

try:
    import numpy
    print('   ✅ numpy установлен (версия: {})'.format(numpy.__version__))
except ImportError as e:
    print(f'   ❌ numpy не установлен: {e}')
    errors.append('numpy')

try:
    import hnswlib
    print('   ✅ hnswlib установлен')
except ImportError as e:
    print(f'   ❌ hnswlib не установлен: {e}')
    errors.append('hnswlib')

try:
    import torch
    print('   ✅ torch установлен (версия: {}, CPU-only: {})'.format(
        torch.__version__, 
        not torch.cuda.is_available()
    ))
except ImportError as e:
    print(f'   ❌ torch не установлен: {e}')
    errors.append('torch')

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
    print('\n✅ Все зависимости установлены успешно!')
"

echo ""
echo "🧪 Тестирование импортов проекта..."

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
    print(f'   ⚠️  Ошибка импорта (может быть нормально): {e}')
" || echo "   ⚠️  Некоторые импорты недоступны (возможно, нужны другие зависимости проекта)"

echo ""
echo "✅ Установка завершена!"
echo ""
echo "📝 Следующие шаги:"
echo "   1. Активируйте виртуальное окружение: source venv/bin/activate"
echo "   2. Проверьте: python scripts/check_ledger_ml_deps.py"
echo "   3. Индексируйте ledger: python scripts/index_ledger_in_rag.py"
echo "   4. Протестируйте поиск: python scripts/ledger_rag_query.py 'Какие метрики?'"
echo ""
echo "💡 Примечание: Используется CPU-only PyTorch (без GPU)."
echo "   Для GPU поддержки установите torch отдельно с CUDA."


#!/usr/bin/env python3
"""
Проверка ML зависимостей для Continuity Ledger Phase 1

Проверяет наличие и работоспособность всех необходимых ML зависимостей
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def check_dependency(name, import_statement, check_func=None):
    """Проверка одной зависимости"""
    try:
        exec(import_statement)
        if check_func:
            result = check_func()
            if result:
                print(f"   ✅ {name}: установлен и работает")
                return True
            else:
                print(f"   ⚠️  {name}: установлен, но не работает корректно")
                return False
        else:
            print(f"   ✅ {name}: установлен")
            return True
    except ImportError as e:
        print(f"   ❌ {name}: не установлен ({e})")
        return False
    except Exception as e:
        print(f"   ⚠️  {name}: ошибка при проверке ({e})")
        return False


def main():
    """Главная функция проверки"""
    print("=" * 60)
    print("🔍 ПРОВЕРКА ML ЗАВИСИМОСТЕЙ ДЛЯ LEDGER")
    print("=" * 60)

    results = {}

    print("\n📦 Основные зависимости:")

    # numpy
    try:
        import numpy as np

        results["numpy"] = hasattr(np, "__version__")
        if results["numpy"]:
            print(f"   ✅ numpy: установлен (версия {np.__version__})")
        else:
            print(f"   ⚠️  numpy: установлен, но версия не определена")
    except ImportError as e:
        print(f"   ❌ numpy: не установлен ({e})")
        results["numpy"] = False

    # hnswlib
    try:
        import hnswlib

        results["hnswlib"] = True
        print(f"   ✅ hnswlib: установлен")
    except ImportError as e:
        print(f"   ❌ hnswlib: не установлен ({e})")
        results["hnswlib"] = False

    # sentence-transformers
    try:
        import sentence_transformers

        results["sentence-transformers"] = True
        version = getattr(sentence_transformers, "__version__", "unknown")
        print(f"   ✅ sentence-transformers: установлен (версия {version})")
    except ImportError as e:
        print(f"   ❌ sentence-transformers: не установлен ({e})")
        results["sentence-transformers"] = False

    print("\n🔧 Компоненты sentence-transformers:")

    # SentenceTransformer
    results["SentenceTransformer"] = check_dependency(
        "SentenceTransformer", "from sentence_transformers import SentenceTransformer"
    )

    # CrossEncoder
    results["CrossEncoder"] = check_dependency(
        "CrossEncoder", "from sentence_transformers import CrossEncoder"
    )

    print("\n📚 Проверка интеграции с проектом:")

    # VectorIndex
    try:
        sys.path.insert(0, str(PROJECT_ROOT / "src"))
        from storage.vector_index import (HNSW_AVAILABLE,
                                          SENTENCE_TRANSFORMERS_AVAILABLE,
                                          VectorIndex)

        print(f"   ✅ VectorIndex импортирован")
        print(f"   {'✅' if HNSW_AVAILABLE else '❌'} HNSW_AVAILABLE: {HNSW_AVAILABLE}")
        print(
            f"   {'✅' if SENTENCE_TRANSFORMERS_AVAILABLE else '❌'} SENTENCE_TRANSFORMERS_AVAILABLE: {SENTENCE_TRANSFORMERS_AVAILABLE}"
        )

        results["VectorIndex"] = True
        results["HNSW_AVAILABLE"] = HNSW_AVAILABLE
        results["SENTENCE_TRANSFORMERS_AVAILABLE"] = SENTENCE_TRANSFORMERS_AVAILABLE

    except Exception as e:
        print(f"   ❌ Ошибка импорта VectorIndex: {e}")
        results["VectorIndex"] = False

    # RAG Pipeline
    try:
        from rag.pipeline import CROSS_ENCODER_AVAILABLE, RAGPipeline

        print(f"   ✅ RAGPipeline импортирован")
        print(
            f"   {'✅' if CROSS_ENCODER_AVAILABLE else '❌'} CROSS_ENCODER_AVAILABLE: {CROSS_ENCODER_AVAILABLE}"
        )

        results["RAGPipeline"] = True
        results["CROSS_ENCODER_AVAILABLE"] = CROSS_ENCODER_AVAILABLE

    except Exception as e:
        print(f"   ❌ Ошибка импорта RAGPipeline: {e}")
        results["RAGPipeline"] = False

    # LedgerRAGSearch
    try:
        from ledger.rag_search import LedgerRAGSearch

        print(f"   ✅ LedgerRAGSearch импортирован")
        results["LedgerRAGSearch"] = True

    except Exception as e:
        print(f"   ❌ Ошибка импорта LedgerRAGSearch: {e}")
        results["LedgerRAGSearch"] = False

    # Итоговый отчет
    print("\n" + "=" * 60)
    print("📊 ИТОГОВЫЙ ОТЧЕТ:")
    print("=" * 60)

    critical = [
        "hnswlib",
        "sentence-transformers",
        "SentenceTransformer",
        "VectorIndex",
        "RAGPipeline",
        "LedgerRAGSearch",
    ]
    critical_passed = sum(1 for dep in critical if results.get(dep, False))

    print(f"\nКритические зависимости: {critical_passed}/{len(critical)}")

    if critical_passed == len(critical):
        print("✅ Все критические зависимости установлены и работают")
        print("✅ Phase 1 готов к использованию с полным semantic search")
        return 0
    else:
        print("⚠️  Некоторые критические зависимости отсутствуют")
        print("\n📝 Для установки выполните:")
        print("   bash scripts/install_ledger_ml_deps.sh")
        print("   или")
        print("   pip install -r requirements-ledger-ml.txt")
        return 1


if __name__ == "__main__":
    sys.exit(main())

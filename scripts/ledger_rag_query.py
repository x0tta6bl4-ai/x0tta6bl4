#!/usr/bin/env python3
"""
Скрипт для semantic search в ledger через RAG

Использование:
    python scripts/ledger_rag_query.py "Какие метрики у нас хуже targets?"
    python scripts/ledger_rag_query.py "Какие issues нужно решить в первую очередь?"
"""

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import logging

from src.ledger.rag_search import LedgerRAGSearch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def query_ledger(question: str):
    """Semantic search в ledger через RAG"""
    logger.info(f"🔍 Поиск в ledger: {question}")

    # Инициализация LedgerRAGSearch
    ledger_rag = LedgerRAGSearch()

    # Убеждаемся, что ledger проиндексирован
    if not ledger_rag.is_indexed():
        logger.info("Индексирование ledger...")
        await ledger_rag.index_ledger()

    # Выполнение запроса
    result = await ledger_rag.query(question, top_k=5)

    # Вывод результатов
    print("\n" + "=" * 60)
    print("РЕЗУЛЬТАТЫ ПОИСКА")
    print("=" * 60)
    print(f"Запрос: {result.query}")
    print(f"Найдено результатов: {result.total_results}")
    print(f"Время поиска: {result.search_time_ms:.2f}ms")
    print("=" * 60)

    if result.results:
        for i, res in enumerate(result.results[:5], 1):
            print(f"\n[{i}] Раздел: {res.get('section', 'Unknown')}")
            print(f"    Релевантность: {res.get('score', 0):.3f}")
            print(f"    Содержание: {res.get('text', '')[:200]}...")
    else:
        print("❌ Результаты не найдены")

    print("=" * 60)

    return result


def main():
    if len(sys.argv) < 2:
        print("Использование: python scripts/ledger_rag_query.py <question>")
        print("\nПримеры:")
        print(
            '  python scripts/ledger_rag_query.py "Какие метрики у нас хуже targets?"'
        )
        print(
            '  python scripts/ledger_rag_query.py "Какие issues нужно решить в первую очередь?"'
        )
        sys.exit(1)

    question = " ".join(sys.argv[1:])
    result = asyncio.run(query_ledger(question))

    return 0 if result and result.total_results > 0 else 1


if __name__ == "__main__":
    sys.exit(main())

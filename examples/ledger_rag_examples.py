#!/usr/bin/env python3
"""
Примеры использования Ledger RAG Search

Демонстрация semantic search в Continuity Ledger через RAG pipeline
"""

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ledger.rag_search import LedgerRAGSearch
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def example_basic_search():
    """Базовый пример поиска"""
    print("\n" + "=" * 60)
    print("Пример 1: Базовый поиск")
    print("=" * 60)
    
    ledger_rag = LedgerRAGSearch()
    
    # Автоматическое индексирование при первом использовании
    if not ledger_rag.is_indexed():
        print("Индексирование ledger...")
        await ledger_rag.index_ledger()
    
    # Поиск
    result = await ledger_rag.query("Какие метрики у нас хуже targets?")
    
    print(f"\nЗапрос: {result.query}")
    print(f"Найдено результатов: {result.total_results}")
    print(f"Время поиска: {result.search_time_ms:.2f}ms")
    
    if result.results:
        print("\nТоп-3 результата:")
        for i, res in enumerate(result.results[:3], 1):
            print(f"\n[{i}] {res.get('section', 'Unknown')}")
            print(f"    Релевантность: {res.get('score', 0):.3f}")
            print(f"    Текст: {res.get('text', '')[:150]}...")


async def example_natural_language_queries():
    """Примеры natural language queries"""
    print("\n" + "=" * 60)
    print("Пример 2: Natural Language Queries")
    print("=" * 60)
    
    ledger_rag = LedgerRAGSearch()
    
    if not ledger_rag.is_indexed():
        await ledger_rag.index_ledger()
    
    queries = [
        "Какие issues нужно решить в первую очередь?",
        "Что изменилось за последнюю неделю?",
        "Какие компоненты готовы к deployment?",
        "Какие риски есть для staging deployment?",
        "Какие метрики валидированы?",
    ]
    
    for query in queries:
        print(f"\n📝 Запрос: {query}")
        result = await ledger_rag.query(query, top_k=3)
        
        if result.results:
            print(f"   ✅ Найдено: {result.total_results} результатов")
            print(f"   ⏱️  Время: {result.search_time_ms:.2f}ms")
            print(f"   📊 Топ результат: {result.results[0].get('section', 'Unknown')} (score: {result.results[0].get('score', 0):.3f})")
        else:
            print(f"   ❌ Результаты не найдены")


async def example_section_search():
    """Поиск по конкретным разделам"""
    print("\n" + "=" * 60)
    print("Пример 3: Поиск по разделам")
    print("=" * 60)
    
    ledger_rag = LedgerRAGSearch()
    
    if not ledger_rag.is_indexed():
        await ledger_rag.index_ledger()
    
    # Поиск информации о метриках
    result = await ledger_rag.query("технические метрики performance benchmarks", top_k=5)
    
    print(f"\nЗапрос: технические метрики")
    print(f"Найдено: {result.total_results} результатов")
    
    if result.results:
        print("\nРелевантные разделы:")
        for i, res in enumerate(result.results, 1):
            section = res.get('section', 'Unknown')
            score = res.get('score', 0)
            print(f"  {i}. {section} (score: {score:.3f})")


async def example_api_usage():
    """Пример использования через API"""
    print("\n" + "=" * 60)
    print("Пример 4: Использование через API")
    print("=" * 60)
    
    print("""
Для использования через API:

1. Запустите сервер:
   python -m src.core.app

2. Выполните запрос:
   curl -X POST http://localhost:8080/api/v1/ledger/search \\
     -H "Content-Type: application/json" \\
     -d '{"query": "Какие метрики у нас хуже targets?", "top_k": 5}'

3. Или через GET:
   curl "http://localhost:8080/api/v1/ledger/search?q=Какие%20метрики&top_k=5"

4. Проверьте статус:
   curl http://localhost:8080/api/v1/ledger/status

5. Индексирование:
   curl -X POST http://localhost:8080/api/v1/ledger/index
    """)


async def main():
    """Запуск всех примеров"""
    print("\n" + "=" * 60)
    print("🚀 ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ LEDGER RAG SEARCH")
    print("=" * 60)
    
    try:
        await example_basic_search()
        await example_natural_language_queries()
        await example_section_search()
        await example_api_usage()
        
        print("\n" + "=" * 60)
        print("✅ Все примеры выполнены успешно!")
        print("=" * 60)
        
    except Exception as e:
        logger.error(f"Ошибка при выполнении примеров: {e}", exc_info=True)
        print(f"\n❌ Ошибка: {e}")


if __name__ == "__main__":
    asyncio.run(main())


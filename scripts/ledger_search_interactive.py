#!/usr/bin/env python3
"""
Интерактивный поиск в Continuity Ledger

Интерактивная оболочка для semantic search в ledger
"""

import sys
import asyncio
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ledger.rag_search import LedgerRAGSearch
import logging

logging.basicConfig(level=logging.WARNING)  # Уменьшаем verbosity для интерактивного режима
logger = logging.getLogger(__name__)


async def interactive_search():
    """Интерактивный поиск в ledger"""
    print("=" * 60)
    print("🔍 ИНТЕРАКТИВНЫЙ ПОИСК В CONTINUITY LEDGER")
    print("=" * 60)
    print("\nВведите запрос для поиска (или 'quit' для выхода)")
    print("Примеры:")
    print("  - Какие метрики у нас хуже targets?")
    print("  - Какие компоненты готовы к deployment?")
    print("  - Что изменилось за последнюю неделю?")
    print()
    
    ledger_rag = LedgerRAGSearch()
    
    # Индексирование при первом запуске
    if not ledger_rag.is_indexed():
        print("📖 Индексирование ledger...")
        await ledger_rag.index_ledger()
        print("✅ Ledger проиндексирован\n")
    
    while True:
        try:
            query = input("🔍 Запрос: ").strip()
            
            if not query:
                continue
            
            if query.lower() in ['quit', 'exit', 'q']:
                print("\n👋 До свидания!")
                break
            
            print(f"\n🔎 Поиск: '{query}'...")
            result = await ledger_rag.query(query, top_k=5)
            
            print(f"\n✅ Найдено: {result.total_results} результатов ({result.search_time_ms:.2f}ms)")
            
            if result.results:
                print("\n📊 Топ результаты:")
                for i, res in enumerate(result.results, 1):
                    section = res.get('section', 'Unknown')
                    score = res.get('score', 0)
                    text = res.get('text', '')[:200]
                    
                    print(f"\n[{i}] {section} (score: {score:.3f})")
                    print(f"    {text}...")
            else:
                print("❌ Результаты не найдены")
            
            print("\n" + "-" * 60 + "\n")
            
        except KeyboardInterrupt:
            print("\n\n👋 До свидания!")
            break
        except Exception as e:
            print(f"\n❌ Ошибка: {e}\n")


if __name__ == "__main__":
    asyncio.run(interactive_search())


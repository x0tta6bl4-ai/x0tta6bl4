"""
Пример использования мета-когнитивного MAPE-K цикла

Демонстрирует интеграцию мета-когнитивного подхода
с существующими компонентами x0tta6bl4.
"""

import asyncio
import logging
from src.core.meta_cognitive_mape_k import MetaCognitiveMAPEK

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def example_basic_usage():
    """Базовый пример использования"""
    logger.info("=" * 60)
    logger.info("Пример 1: Базовое использование")
    logger.info("=" * 60)
    
    # Создание мета-когнитивного MAPE-K
    meta_mape_k = MetaCognitiveMAPEK(
        node_id="example-node-1"
    )
    
    # Запуск полного цикла
    task = {
        'type': 'anomaly_detection',
        'description': 'Detect and resolve network anomaly',
        'complexity': 0.7
    }
    
    result = await meta_mape_k.run_full_cycle(task)
    
    # Вывод результатов
    logger.info("\n📊 Результаты мета-когнитивного цикла:")
    logger.info(f"  - Выбранный подход: {result.get('meta_plan', {}).get('solution_space', {}).get('selected_approach', 'unknown')}")
    logger.info(f"  - Успех: {result.get('knowledge', {}).get('reasoning_analytics', {}).get('success', False)}")
    logger.info(f"  - Время рассуждения: {result.get('knowledge', {}).get('reasoning_analytics', {}).get('reasoning_time', 0):.2f}s")
    
    if result.get('knowledge', {}).get('meta_insight'):
        meta_insight = result['knowledge']['meta_insight']
        logger.info(f"  - Мета-инсайт: {meta_insight.get('effective_algorithm', 'N/A')}")
        logger.info(f"  - Почему сработало: {meta_insight.get('why_it_worked', 'N/A')}")


async def example_with_integration():
    """Пример с интеграцией существующих компонентов"""
    logger.info("=" * 60)
    logger.info("Пример 2: Интеграция с существующими компонентами")
    logger.info("=" * 60)
    
    # Импорт существующих компонентов
    try:
        from src.core.mape_k_loop import MAPEKLoop
        from src.ml.rag import RAGAnalyzer
        from src.storage.knowledge_storage_v2 import KnowledgeStorageV2
        
        # Создание компонентов
        # Примечание: В реальном использовании эти компоненты должны быть
        # правильно инициализированы с их зависимостями
        knowledge_storage = None  # KnowledgeStorageV2(...)
        rag_analyzer = None  # RAGAnalyzer(...)
        
        # Создание мета-когнитивного MAPE-K с интеграцией
        meta_mape_k = MetaCognitiveMAPEK(
            knowledge_storage=knowledge_storage,
            rag_analyzer=rag_analyzer,
            node_id="example-node-2"
        )
        
        # Запуск цикла
        task = {
            'type': 'performance_optimization',
            'description': 'Optimize system performance',
            'complexity': 0.8
        }
        
        result = await meta_mape_k.run_full_cycle(task)
        
        logger.info("\n📊 Результаты с интеграцией:")
        logger.info(f"  - Статус: {result.get('execution_log', {}).get('execution_result', {}).get('status', 'unknown')}")
        
    except ImportError as e:
        logger.warning(f"⚠️ Некоторые компоненты недоступны: {e}")
        logger.info("Используется упрощенный режим без интеграции")


async def example_continuous_cycles():
    """Пример непрерывных циклов"""
    logger.info("=" * 60)
    logger.info("Пример 3: Непрерывные циклы")
    logger.info("=" * 60)
    
    meta_mape_k = MetaCognitiveMAPEK(
        node_id="example-node-3"
    )
    
    # Запуск нескольких циклов
    tasks = [
        {'type': 'monitoring', 'description': 'Standard monitoring cycle', 'complexity': 0.3},
        {'type': 'anomaly_detection', 'description': 'Detect anomalies', 'complexity': 0.6},
        {'type': 'optimization', 'description': 'System optimization', 'complexity': 0.8}
    ]
    
    results = []
    for i, task in enumerate(tasks, 1):
        logger.info(f"\n🔄 Цикл {i}/{len(tasks)}")
        result = await meta_mape_k.run_full_cycle(task)
        results.append(result)
        
        # Статистика
        logger.info(f"  - Успешных циклов: {meta_mape_k.successful_cycles}")
        logger.info(f"  - Неудачных циклов: {meta_mape_k.failed_cycles}")
        logger.info(f"  - Всего циклов: {meta_mape_k.total_cycles}")
    
    # Итоговая статистика
    logger.info("\n📈 Итоговая статистика:")
    logger.info(f"  - Успешных циклов: {meta_mape_k.successful_cycles}/{meta_mape_k.total_cycles}")
    logger.info(f"  - Процент успеха: {(meta_mape_k.successful_cycles / meta_mape_k.total_cycles * 100):.1f}%" if meta_mape_k.total_cycles > 0 else "N/A")


async def main():
    """Главная функция"""
    logger.info("🚀 Запуск примеров мета-когнитивного MAPE-K")
    logger.info("")
    
    # Пример 1: Базовое использование
    await example_basic_usage()
    
    logger.info("\n" + "=" * 60 + "\n")
    
    # Пример 2: Интеграция с существующими компонентами
    await example_with_integration()
    
    logger.info("\n" + "=" * 60 + "\n")
    
    # Пример 3: Непрерывные циклы
    await example_continuous_cycles()
    
    logger.info("\n" + "=" * 60)
    logger.info("✅ Все примеры завершены")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

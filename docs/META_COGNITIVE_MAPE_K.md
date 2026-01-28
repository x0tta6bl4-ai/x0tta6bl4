# Мета-когнитивный MAPE-K: Руководство по использованию

## Обзор

Мета-когнитивный MAPE-K цикл объединяет мета-когнитивный подход (анализ процесса мышления) с техниками x0tta6bl4 (MAPE-K, RAG, GraphSAGE, Causal Analysis).

**Ключевая инновация:** Система думает о том, как она думает, создавая проверяемый след рассуждений и самокорректирующуюся логику.

## Быстрый старт

### Базовое использование

```python
from src.core.meta_cognitive_mape_k import MetaCognitiveMAPEK
import asyncio

async def main():
    # Создание мета-когнитивного MAPE-K
    meta_mape_k = MetaCognitiveMAPEK(
        node_id="my-node"
    )
    
    # Запуск полного цикла
    task = {
        'type': 'anomaly_detection',
        'description': 'Detect and resolve network anomaly',
        'complexity': 0.7
    }
    
    result = await meta_mape_k.run_full_cycle(task)
    
    # Результаты
    print(f"Выбранный подход: {result['meta_plan']['solution_space']['selected_approach']}")
    print(f"Успех: {result['knowledge']['reasoning_analytics']['success']}")

asyncio.run(main())
```

### Интеграция с существующими компонентами

```python
from src.core.meta_cognitive_mape_k import MetaCognitiveMAPEK
from src.core.mape_k_loop import MAPEKLoop
from src.ml.rag import RAGAnalyzer
from src.storage.knowledge_storage_v2 import KnowledgeStorageV2

# Инициализация компонентов
mape_k_loop = MAPEKLoop(...)
rag_analyzer = RAGAnalyzer(...)
knowledge_storage = KnowledgeStorageV2(...)

# Создание мета-когнитивного MAPE-K с интеграцией
meta_mape_k = MetaCognitiveMAPEK(
    mape_k_loop=mape_k_loop,
    rag_analyzer=rag_analyzer,
    knowledge_storage=knowledge_storage,
    node_id="integrated-node"
)
```

## Архитектура

### Фазы цикла

1. **Мета-планирование (Фаза 0)**
   - Карта пространства решений
   - Планирование пути рассуждения
   - Выделение ресурсов на размышления

2. **Мониторинг (Фаза 1)**
   - Стандартный мониторинг системы
   - Мета-мониторинг процесса мышления

3. **Анализ (Фаза 2)**
   - Анализ проблемы
   - Мета-анализ процесса мышления

4. **Планирование (Фаза 3)**
   - Планирование решения
   - Мета-оптимизация процесса мышления

5. **Выполнение (Фаза 4)**
   - Выполнение плана
   - Фиксация процесса мышления

6. **Знания (Фаза 5)**
   - Накопление знаний о решении
   - Мета-аналитика процесса мышления

### Подходы к рассуждению

- `MAPE_K_ONLY` - Стандартный MAPE-K цикл
- `RAG_SEARCH` - Поиск похожих случаев
- `GRAPHSAGE_PREDICTION` - Предсказание через GraphSAGE
- `CAUSAL_ANALYSIS` - Анализ корневых причин
- `COMBINED_RAG_GRAPHSAGE` - Комбинация RAG + GraphSAGE
- `COMBINED_ALL` - Комбинация всех подходов

## API Reference

### MetaCognitiveMAPEK

#### `__init__()`

```python
MetaCognitiveMAPEK(
    mape_k_loop: Optional[MAPEKLoop] = None,
    rag_analyzer: Optional[RAGAnalyzer] = None,
    graphsage: Optional[GraphSAGEAnomalyDetectorV2] = None,
    causal_engine: Optional[CausalAnalysisEngine] = None,
    knowledge_storage: Optional[KnowledgeStorageV2] = None,
    node_id: str = "default"
)
```

#### `run_full_cycle()`

Запуск полного мета-когнитивного цикла.

```python
async def run_full_cycle(
    task: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]
```

**Параметры:**
- `task`: Описание задачи (опционально)

**Возвращает:**
- Полный результат цикла с мета-аналитикой

#### `meta_planning()`

Мета-планирование: создание карты пространства решений.

```python
async def meta_planning(
    task: Dict[str, Any]
) -> Tuple[SolutionSpace, ReasoningPath]
```

#### `monitor()`

Мониторинг с мета-осознанием.

```python
async def monitor() -> Dict[str, Any]
```

**Возвращает:**
- `system_metrics`: Метрики системы
- `reasoning_metrics`: Метрики процесса мышления

#### `analyze()`

Анализ с мета-рефлексией.

```python
async def analyze(
    metrics: Dict[str, Any]
) -> Dict[str, Any]
```

#### `plan()`

Планирование с мета-оптимизацией.

```python
async def plan(
    analysis: Dict[str, Any]
) -> Dict[str, Any]
```

#### `execute()`

Выполнение с мета-осознанием.

```python
async def execute(
    plan: Dict[str, Any]
) -> Dict[str, Any]
```

#### `knowledge()`

Накопление знаний с мета-аналитикой.

```python
async def knowledge(
    execution_log: Dict[str, Any]
) -> Dict[str, Any]
```

## Примеры использования

### Пример 1: Базовый цикл

```python
meta_mape_k = MetaCognitiveMAPEK(node_id="node-1")
result = await meta_mape_k.run_full_cycle({
    'type': 'monitoring',
    'description': 'Standard monitoring cycle'
})
```

### Пример 2: Непрерывные циклы

```python
meta_mape_k = MetaCognitiveMAPEK(node_id="node-2")

tasks = [
    {'type': 'monitoring', 'complexity': 0.3},
    {'type': 'anomaly_detection', 'complexity': 0.6},
    {'type': 'optimization', 'complexity': 0.8}
]

for task in tasks:
    result = await meta_mape_k.run_full_cycle(task)
    print(f"Успешных циклов: {meta_mape_k.successful_cycles}")
```

### Пример 3: Интеграция с Knowledge Base

```python
from src.storage.knowledge_storage_v2 import KnowledgeStorageV2

knowledge_storage = KnowledgeStorageV2(...)
meta_mape_k = MetaCognitiveMAPEK(
    knowledge_storage=knowledge_storage,
    node_id="node-3"
)

# Запуск цикла с сохранением в Knowledge Base
result = await meta_mape_k.run_full_cycle({
    'type': 'anomaly_detection',
    'description': 'Detect network anomaly'
})

# Результаты автоматически сохраняются в Knowledge Base
```

## Структура результатов

### Полный результат цикла

```python
{
    'meta_plan': {
        'solution_space': {
            'approaches': [...],
            'selected_approach': 'combined_rag_graphsage',
            'success_probabilities': {...}
        },
        'reasoning_path': {
            'first_step': 'combined_rag_graphsage',
            'dead_ends_to_avoid': [...],
            'checkpoints': [...]
        }
    },
    'metrics': {
        'system_metrics': {...},
        'reasoning_metrics': {...}
    },
    'analysis': {
        'system_analysis': {...},
        'reasoning_analysis': {...}
    },
    'plan': {
        'recovery_plan': {...},
        'reasoning_optimization': {...}
    },
    'execution_log': {
        'execution_result': {...},
        'execution_log': [...]
    },
    'knowledge': {
        'incident_record': {...},
        'reasoning_analytics': {
            'algorithm_used': 'combined_rag_graphsage',
            'reasoning_time': 1.23,
            'success': True,
            'meta_insight': {
                'effective_algorithm': 'combined_rag_graphsage',
                'why_it_worked': 'High confidence and low dead ends'
            }
        }
    }
}
```

## Метрики

### Метрики процесса мышления

- `reasoning_time`: Время рассуждения
- `approaches_tried`: Количество попыток подходов
- `dead_ends_encountered`: Количество тупиков
- `confidence_level`: Уровень уверенности
- `knowledge_base_hits`: Попадания в Knowledge Base
- `cache_hit_rate`: Hit rate кэша

### Статистика циклов

- `total_cycles`: Всего циклов
- `successful_cycles`: Успешных циклов
- `failed_cycles`: Неудачных циклов
- `optimization_count`: Количество оптимизаций

## Интеграция с существующими компонентами

### MAPE-K Loop

```python
from src.core.mape_k_loop import MAPEKLoop

mape_k_loop = MAPEKLoop(...)
meta_mape_k = MetaCognitiveMAPEK(mape_k_loop=mape_k_loop)
```

### RAG Analyzer

```python
from src.ml.rag import RAGAnalyzer

rag_analyzer = RAGAnalyzer(...)
meta_mape_k = MetaCognitiveMAPEK(rag_analyzer=rag_analyzer)
```

### Knowledge Storage

```python
from src.storage.knowledge_storage_v2 import KnowledgeStorageV2

knowledge_storage = KnowledgeStorageV2(...)
meta_mape_k = MetaCognitiveMAPEK(knowledge_storage=knowledge_storage)
```

## Тестирование

### Запуск тестов

```bash
pytest tests/unit/core/test_meta_cognitive_mape_k.py -v
```

### Примеры тестов

```python
@pytest.mark.asyncio
async def test_full_cycle():
    meta_mape_k = MetaCognitiveMAPEK(node_id="test")
    result = await meta_mape_k.run_full_cycle({
        'type': 'test',
        'complexity': 0.5
    })
    assert 'meta_plan' in result
    assert 'knowledge' in result
```

## Troubleshooting

### Проблема: Компоненты недоступны

**Решение:** Убедитесь, что все зависимости установлены:
```bash
pip install -r requirements.txt
```

### Проблема: Ошибки при интеграции

**Решение:** Проверьте инициализацию компонентов перед передачей в MetaCognitiveMAPEK.

### Проблема: Низкая эффективность

**Решение:** Используйте Knowledge Base для накопления опыта и оптимизации подходов.

## Дополнительные ресурсы

- [Мета-когнитивная интеграция](../МЕТА_КОГНИТИВНЫЙ_x0tta6bl4_ИНТЕГРАЦИЯ.md)
- [Примеры использования](../../examples/example_meta_cognitive_mape_k.py)
- [Тесты](../../tests/unit/core/test_meta_cognitive_mape_k.py)

## Лицензия

Часть проекта x0tta6bl4.

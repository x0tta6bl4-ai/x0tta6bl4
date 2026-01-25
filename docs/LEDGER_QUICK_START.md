# 🚀 Ledger Quick Start Guide

**Версия:** Continuity Ledger v2.0  
**Дата:** 2026-01-03

---

## 📋 Что такое Continuity Ledger?

Continuity Ledger — это канонический бриф сессии для workspace x0tta6bl4 v3.4, устойчивый к компрессии контекста. Версия 2.0 добавляет AI-powered features:

- ✅ **Semantic Search** — поиск в ledger через natural language queries
- 🚧 **Drift Detection** — автоматическое обнаружение расхождений (в разработке)
- ⏳ **AI Auto-Update** — автоматическое обновление ledger (запланировано)
- ⏳ **Real-time Sync** — синхронизация в реальном времени (запланировано)

---

## 🎯 Быстрый старт

### 1. Индексирование Ledger

```bash
# Через скрипт
python scripts/index_ledger_in_rag.py

# Через API
curl -X POST http://localhost:8080/api/v1/ledger/index
```

### 2. Поиск в Ledger

```bash
# Через скрипт
python scripts/ledger_rag_query.py "Какие метрики у нас хуже targets?"

# Через API (POST)
curl -X POST http://localhost:8080/api/v1/ledger/search \
  -H "Content-Type: application/json" \
  -d '{"query": "Какие метрики?", "top_k": 5}'

# Через API (GET)
curl "http://localhost:8080/api/v1/ledger/search?q=Какие%20метрики&top_k=5"
```

### 3. Проверка статуса

```bash
# Через API
curl http://localhost:8080/api/v1/ledger/status
```

---

## 📚 Примеры использования

### Python API

```python
import asyncio
from src.ledger.rag_search import LedgerRAGSearch

async def main():
    # Инициализация
    ledger_rag = LedgerRAGSearch()
    
    # Индексирование (если нужно)
    if not ledger_rag.is_indexed():
        await ledger_rag.index_ledger()
    
    # Поиск
    result = await ledger_rag.query("Какие метрики у нас хуже targets?")
    
    print(f"Найдено: {result.total_results} результатов")
    for res in result.results[:3]:
        print(f"- {res['section']}: {res['score']:.3f}")

asyncio.run(main())
```

### Запуск примеров

```bash
# Все примеры
python examples/ledger_rag_examples.py

# Конкретный пример
python -c "
import asyncio
from examples.ledger_rag_examples import example_basic_search
asyncio.run(example_basic_search())
"
```

---

## 🔍 Типичные запросы

### Поиск метрик

```bash
python scripts/ledger_rag_query.py "Какие технические метрики валидированы?"
python scripts/ledger_rag_query.py "Какие метрики хуже targets?"
```

### Поиск проблем

```bash
python scripts/ledger_rag_query.py "Какие issues нужно решить в первую очередь?"
python scripts/ledger_rag_query.py "Какие риски есть для staging deployment?"
```

### Поиск компонентов

```bash
python scripts/ledger_rag_query.py "Какие компоненты готовы к deployment?"
python scripts/ledger_rag_query.py "Что изменилось за последнюю неделю?"
```

### Поиск roadmap

```bash
python scripts/ledger_rag_query.py "Когда бета тестирование?"
python scripts/ledger_rag_query.py "Какие планы на Q1 2026?"
```

---

## 🛠️ API Endpoints

### Search Endpoints

- `POST /api/v1/ledger/search` — Semantic search (POST)
- `GET /api/v1/ledger/search` — Semantic search (GET)
- `POST /api/v1/ledger/index` — Индексирование ledger
- `GET /api/v1/ledger/status` — Статус индексирования

### Drift Detection Endpoints (Phase 2)

- `POST /api/v1/ledger/drift/detect` — Обнаружение расхождений
- `GET /api/v1/ledger/drift/status` — Статус drift detector

---

## 📖 Дополнительная документация

- `LEDGER_USAGE_GUIDE.md` — Подробное руководство по использованию
- `LEDGER_UPDATE_PROCESS.md` — Процесс обновления ledger
- `LEDGER_PHASE1_COMPLETE.md` — Отчет о Phase 1
- `LEDGER_IMPLEMENTATION_STATUS.md` — Статус реализации
- `CONTINUITY.md` — Сам ledger (источник истины)

---

## ❓ FAQ

### Как часто нужно индексировать?

Ledger автоматически индексируется при первом поиске. Переиндексирование нужно только после значительных изменений в `CONTINUITY.md`.

### Как работает semantic search?

Используется существующий RAG pipeline проекта:
1. Документ разбивается на chunks
2. Chunks индексируются в векторное хранилище (HNSW)
3. Запрос преобразуется в embedding
4. Выполняется поиск похожих chunks
5. Результаты ранжируются (опционально через CrossEncoder)

### Можно ли использовать без API?

Да, можно использовать напрямую через Python API (`LedgerRAGSearch`).

---

**Последнее обновление:** 2026-01-03


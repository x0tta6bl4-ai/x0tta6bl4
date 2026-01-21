# 📚 Examples: x0tta6bl4 v2.0

Примеры использования компонентов x0tta6bl4 v2.0.

---

## 📋 Доступные примеры

### 1. Knowledge Storage (`example_knowledge_storage.py`)

Демонстрирует:
- Инициализацию Knowledge Storage
- Сохранение инцидентов
- Semantic search
- Получение успешных паттернов
- Интеграцию с MAPE-K

**Запуск:**
```bash
python examples/example_knowledge_storage.py
```

---

### 2. DAO → MAPE-K Integration (`example_dao_mapek.py`)

Демонстрирует:
- Создание threshold proposal
- Голосование через DAO
- Применение изменений порогов
- Использование в MAPE-K цикле

**Запуск:**
```bash
python examples/example_dao_mapek.py
```

---

### 3. PQC Performance (`example_pqc_performance.py`)

Демонстрирует:
- Key caching
- Batch processing
- Performance metrics
- Optimized Mesh Security

**Запуск:**
```bash
python examples/example_pqc_performance.py
```

---

### 4. Complete Integration (`example_complete_integration.py`)

Демонстрирует:
- Полную интеграцию всех компонентов
- DAO → Threshold → MAPE-K
- Knowledge Storage → MAPE-K
- End-to-end workflow

**Запуск:**
```bash
python examples/example_complete_integration.py
```

---

## 🚀 Запуск всех примеров

```bash
make examples
```

или

```bash
for example in examples/example_*.py; do
    echo "Running $example..."
    python "$example"
    echo ""
done
```

---

## 📝 Примечания

- Все примеры используют mock IPFS (для тестирования)
- Для production установите IPFS daemon и используйте `use_real_ipfs=True`
- Примеры создают временные файлы, которые автоматически удаляются

---

**Готово к использованию!** 🚀


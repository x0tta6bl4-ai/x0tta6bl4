# RFC: Shard Routing & Semantic Chunking Protocol (Horizon-2)

## 1. Overview
В децентрализованной архитектуре x0tta6bl4 каждый узел хранит только часть глобального индекса (шард). Этот протокол описывает, как распределяются данные и как выполняется поиск (retrieval) через mesh-сеть.

## 2. Semantic Chunking Strategy
Для оптимизации под Edge-устройства (low memory/CPU) используется **Late Interaction Chunking**:
- **Fixed-size window** (512 tokens) с 10% перекрытием.
- **Contextual enrichment**: каждый чанк включает `doc_id`, `tenant_id` и `security_tag` (SPIFFE ID).
- **Embeddings**: локальная генерация через ONNX (модель `bge-small-en-v1.5` или аналоги).

## 3. Shard Distribution (The Knowledge Plane)
- **Consistent Hashing**: `Hash(tenant_id + chunk_id)` определяет целевой "домашний" узел.
- **Redundancy**: фактор репликации `R=3` (хранение на 3-х ближайших по метрике BATMAN-adv узлах).
- **Metadata Store**: каждый узел ведет локальный SQLite лог своих шардов.

## 4. Shard Routing Protocol (SRP v1)
Поиск выполняется по следующей схеме:
1. **Query Ingress**: Узел-координатор получает запрос и генерирует поисковый вектор.
2. **K-Nearest Discovery**: 
   - Запрос рассылается широковещательно (multicast) в пределах `N` хопов.
   - Или (целевой поиск): опрос узлов, владеющих метаданными конкретных `tenant_id`.
3. **Local Search**: Узлы выполняют ANN-поиск (HNSW/LEANN) в своих шардах.
4. **Gather & Rerank**: Результаты возвращаются координатору для финального ранжирования (Cross-Encoder).

## 5. Security & Zero-Trust Integration
- **Authz**: Поиск возможен только при наличии валидного `X-Agent-Token` с соответствующими правами в DAO.
- **Encryption**: Шарды на диске зашифрованы PQC-ключами текущей ротации.

## 6. Next Steps (Implementation)
- [ ] Scaffold `agent/internal/rag/chunker.go`
- [ ] Scaffold `agent/internal/rag/router.go`
- [ ] Интеграция с `internal/crypto/pqc` для шифрования индексов.

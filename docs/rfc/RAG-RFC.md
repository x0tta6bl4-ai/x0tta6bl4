# RFC: Decentralized RAG Knowledge Plane
**Status:** DEFERRED — Horizon-2
**Created:** 2026-03-06
**Owner:** Architecture agent (1 agent, RFC phase only)
**Start condition:** After closing live verification gaps for v1.1 hardening (see below)

---

## Decision: сейчас / отложить / кому / критерии

| Вопрос | Решение |
|--------|---------|
| Делать сейчас? | **Нет** — распылять команду до закрытия infra/security proof points рискованно |
| Зафиксировать идею? | **Да** — этот документ |
| Приоритет? | Horizon-2, не текущий фронт |
| Кому делегировать (RFC фаза)? | 1 архитектурный агент (knowledge-plane design) |
| Масштабировать на всех агентов? | Только после закрытия критериев старта |

---

## Критерии старта (все должны быть закрыты)

- [ ] Live XDP attach на реальном NIC — `dmesg` + `verify-local.sh --live-attach` exit 0
- [ ] PPS benchmark >= 5M — `RUN_BENCH=1` harness, `benchmark-<ts>.json` с `"pass": true` (не hand-crafted)
- [ ] Keyless cosign + Rekor — `SIGSTORE_ID_TOKEN` в CI, `rekor-cli get` подтверждает hash
- [ ] Live Open5GS UPF session — HTTP log от реального UPF endpoint
- [ ] Алгоритм: `alembic upgrade head --sql` EXIT 0 — **DONE 2026-03-06**
- [ ] Unit suite < 5 failures — **DONE 2026-03-06** (10→0)

Пока хотя бы один пункт инфраструктурного уровня открыт — тема RAG остаётся в Horizon-2.

---

## Что такое Decentralized RAG для x0tta6bl4

На основе имеющихся материалов (ector-index-rag-intelligence):

- **Privacy-first / on-device retrieval** — индексы живут на edge-узлах, не централизованно
- **Hybrid search** — vector + keyword, маршрутизация по shard на mesh-топологии
- **Community-first** — knowledge plane как часть DAO governance (кто индексирует что)
- **Chunking → embeddings → reranking → index management → knowledge tracking**

---

## Пятислойная архитектура (из Gemini RFC v0.1)

1. **Ingestion/Chunking** — семантическая нарезка документов с metadata (source, tenant, ACL, timestamp)
2. **Local Indexing** — гибридный поиск на каждом узле:
   - Sparse: BM25/TF-IDF для лексического recall
   - Dense (мощные узлы): HNSW ANN index
   - Edge (лёгкие узлы): LEANN compact index
3. **Mesh Routing** — knowledge-aware request brokering через существующую multi-path логику (BATMAN-adv aware)
4. **Context Assembly** — federated retrieval + cross-encoder reranking
5. **Generation** — LLM gateway, потребляет только top-k контекст

---

## MVP-схема (для RFC фазы)

```
MeshNode
  └── EdgeIndexShard (hnswlib / faiss-lite)
       ├── chunk_store/   — текстовые чанки + metadata
       ├── embed_model/   — локальная модель (ONNX / llama.cpp)
       └── shard_router   — routing по mesh-топологии (BATMAN-adv aware)

QueryRouter (coordinator node)
  ├── fan-out query → N shards
  ├── gather + rerank (cross-encoder)
  └── return top-K с source attribution

PolicyEngine (zero-trust)
  └── ACL per shard — кто может читать / писать индекс
```

---

## Адресная делегация (когда откроем)

| Роль | Агент | Задача |
|------|-------|--------|
| Knowledge-plane architect | Gemini / Architecture | RFC v1: shard schema, routing protocol, index lifecycle |
| Security / zero-trust | Claude | Policy/ACL для retrieval: SPIFFE-based shard access control |
| Infra / storage | Codex | Shard routing implementation, storage profile для edge-узлов |

---

## Почему не сейчас (summary)

Ближайшая ценность для MVP — **доказуемость платформы**, а не расширение архитектуры.
Текущие production-claims по XDP, PPS, Rekor, 5G UPF ещё помечены `NOT VERIFIED YET`.
Добавление крупного нового knowledge-plane до закрытия этих gaps создаёт organizational noise
и снижает defensibility проекта перед инвесторами / аудиторами.

**Следующий review этого RFC:** после закрытия всех инфраструктурных критериев выше.

# Следующие приоритетные задачи: Mesh-сеть + Federated Learning

**Дата:** 2026-02-23 (Updated)
**Статус:** P0 Complete — W10 In Progress
**Версия:** 3.4.0

---

## ✅ Выполнено (W9)

| Задача | Статус | Тесты |
|--------|--------|-------|
| LoRA + Federated Learning Integration | ✅ Complete | 37/37 passed |
| Batman-adv Health Monitor | ✅ Complete | 51/51 passed |
| Batman-adv MAPE-K Integration | ✅ Complete | Included above |
| ROADMAP.md Update | ✅ Complete | - |

---

## 🔍 Architecture Review Findings (2026-02-23)

### Критические проблемы (P0) — ✅ RESOLVED 2026-02-23

| # | Проблема | Файл | Решение | Статус |
|---|----------|------|---------|--------|
| **#1** | SwarmConsensusManager создаёт новый RaftNode на каждое решение | `consensus_integration.py` | `_initialize_raft()` idempotent + тест `test_raft_node_reused_*` | ✅ |
| **#2** | Отсутствие реальной сетевой коммуникации | `consensus_integration.py` | `ConsensusTransport` интегрирован, `_send_consensus_message` реальная | ✅ |
| **#9** | Тесты не проверяют distributed работу | новый файл | `test_message_flows_between_two_managers` через file-based IPC | ✅ |

**Дополнительно исправлено:**
- `RaftNode.set_callbacks()` — добавлен `send_message` параметр (был `TypeError`)
- `RaftNode.receive_message()` — добавлен диспетчер сообщений (был `AttributeError`)
- `start_election()` — теперь рассылает `request_vote` пирам
- TD-002 memory leak — добавлен `_cleanup_decisions()` с TTL

### Проблемы качества кода (P1)

| # | Проблема | Файл | Решение |
|---|----------|------|---------|
| **#5** | Busy-waiting в Paxos `_wait_for_quorum()` | `paxos.py:278` | Заменить polling на `asyncio.Event` |
| **#6** | Отсутствие валидации входных данных | `consensus.py`, `intelligence.py` | Добавить assertions |
| **#7** | Memory leak в `_instances` и `_decisions` | `paxos.py:132`, `consensus.py:203` | Добавить TTL-based cleanup |

### Проблемы производительности (P1-P2)

| # | Проблема | Файл | Решение |
|---|----------|------|---------|
| **#13** | O(n²) message complexity в broadcast | `paxos.py:180`, `pbft.py:175` | Документировать limit ≤20 nodes |
| **#14** | Synchronous JSON serialization | `paxos.py:72` | Заменить json на orjson |
| **#15** | Нет batching для proposals | `intelligence.py:531` | Использовать MultiPaxos |

---

## 🎯 Приоритетные задачи (W10-W12) — Updated

### P0: Fix Swarm Consensus Architecture — ✅ DONE (2026-02-23)

**Выполнено:**
- `src/swarm/consensus.py` — `RaftNode.receive_message()`, `send_message` callback, election broadcast
- `src/swarm/consensus_integration.py` — `ConsensusTransport` wired, TTL cleanup, bug fixes
- `tests/unit/swarm/test_consensus_transport_integration_unit.py` — 33 tests (все зелёные)

---

### P1: Swarm Intelligence Phase 2 (Kimi K2.5)

**Цель:** Завершить Phase 2 из 3 для swarm intelligence

**Статус:** ⚠️ Требует исправления P0 issues

**Задачи:**
1. ~~Интеграция Kimi K2.5 модели для swarm координации~~ → Отложено в Phase 3
2. Распределенное принятие решений через consensus
3. Swarm learning с агрегацией знаний

**Файлы:**
- `src/swarm/intelligence.py` (EXISTS — needs fixes)
- `src/swarm/kimi_integration.py` (DEFERRED)
- `tests/test_swarm_intelligence.py` (EXISTS — needs integration tests)

**Критерии успеха:**
- Swarm из 5+ узлов принимает согласованные решения
- Latency принятия решений < 100ms
- 95%+ consensus success rate

**Известные проблемы:**
- KimiK25Integration — заглушка, всегда возвращает первый вариант
- MAPE-K дублируется с `libx0t/network/batman/mape_k_integration.py`

---

### P1: Mesh-FL Integration Layer

**Цель:** Объединить Batman-adv mesh с Federated LoRA training

**Задачи:**
1. Распределение FL задач через mesh топологию
2. Адаптивная агрегация на основе link quality
3. Prioritized updates от узлов с лучшим connectivity

**Файлы:**
- `src/federated_learning/mesh_fl_integration.py` (NEW)
- `src/federated_learning/topology_aware_aggregator.py` (NEW)
- `tests/test_mesh_fl_integration.py` (NEW)

**Критерии успеха:**
- FL training работает на Batman-adv mesh
- Link quality влияет на weight aggregation
- Устойчивость к node churn (20% nodes leaving)

---

### P2: Multi-Arch Docker Builds

**Цель:** Поддержка arm64 и amd64 для развертывания

**Задачи:**
1. Обновить Dockerfile для multi-stage builds
2. Настроить buildx для multi-arch
3. Опубликовать в registry

**Файлы:**
- `docker/Dockerfile.api` (UPDATE)
- `docker/Dockerfile.worker` (UPDATE)
- `.github/workflows/docker-build.yml` (NEW)

**Критерии успеха:**
- Образы работают на arm64 (Raspberry Pi, Apple Silicon)
- Образы работают на amd64 (x86_64 servers)
- Size < 500MB per image

---

### P2: Dependabot Automation

**Цель:** Автоматическое обновление зависимостей

**Задачи:**
1. Настроить dependabot.yml
2. Добавить auto-merge для patch versions
3. Настроить security updates

**Файлы:**
- `.github/dependabot.yml` (NEW)
- `.github/workflows/auto-merge.yml` (NEW)

---

## 📊 Метрики успеха — Updated

| Метрика | Current | Target | Срок | Примечание |
|---------|---------|--------|------|------------|
| Test Coverage | 74.5% | 80% | W12 | - |
| Unit Tests | 225+ | 300+ | W12 | - |
| Integration Tests | 0 | 10+ | W10 | NEW: distributed consensus tests |
| P1 Tasks Complete | 9/10 | 10/10 | W10 | - |
| Mesh Nodes FL Training | 0 | 5+ | W11 | - |
| Consensus Latency | N/A | <100ms | W10 | ⚠️ Self-reported, needs real measurement |
| P0 Issues Fixed | 3/3 | 3/3 | W10 | ✅ DONE |

---

## 🔄 Зависимости — Updated

```
P0: Fix Swarm Consensus Architecture
    └── Blocks: Swarm Intelligence Phase 2
    
Swarm Intelligence Phase 2
    └── Requires: Consensus (⚠️ needs fix), Coordination (✅)
    
Mesh-FL Integration
    └── Requires: Batman-adv (✅), LoRA+FL (✅), Consensus (⚠️)
    
Multi-Arch Builds
    └── Requires: Dockerfiles (✅)
    
Dependabot
    └── Requires: GitHub Actions (✅)
```

---

## 📅 Timeline — Updated

| Неделя | Задачи |
|--------|--------|
| W10 (Feb 23 - Mar 1) | **P0: Fix Swarm Consensus** + Swarm Intelligence Phase 2 |
| W11 (Mar 2 - Mar 8) | Mesh-FL Integration Layer |
| W12 (Mar 9 - Mar 15) | Multi-Arch, Dependabot |

---

## 🚀 Следующий шаг — Updated

**1. Выполнить P0 fixes:**

```bash
# Запустить integration tests
pytest tests/integration/test_distributed_consensus.py -v -s

# Проверить transport layer
python -c "
from src.coordination.consensus_transport import ConsensusTransport
import asyncio

async def test():
    t = ConsensusTransport(node_id='test-node')
    await t.start()
    print('Transport started successfully')
    await t.stop()

asyncio.run(test())
"
```

**2. После P0 — Swarm Intelligence Phase 2:**

```python
# Ожидаемый интерфейс (после fixes)
from src.swarm.intelligence import SwarmIntelligence
from src.coordination.consensus_transport import ConsensusTransport

transport = ConsensusTransport(node_id="node-001")
swarm = SwarmIntelligence(
    node_id="node-001",
    peers={"node-002", "node-003"},
    consensus_algorithm="raft",
    transport=transport,  # NEW: real transport
)

await swarm.initialize()

decision = await swarm.make_decision(
    context={"action": "heal_node", "target": "node-005"},
    timeout_ms=100,
)
```

---

## 📝 Technical Debt Register

| ID | Описание | Effort | Priority |
|----|----------|--------|----------|
| TD-001 | Busy-waiting в Paxos | Low | P1 |
| TD-002 | Memory leak в consensus | Medium | ✅ Resolved |
| TD-003 | Missing input validation | Low | P1 |
| TD-004 | Inconsistent error handling | Medium | P2 |
| TD-005 | Missing Paxos/PBFT unit tests | High | P1 |
| TD-006 | Self-reported latency in tests | Low | P2 |
| TD-007 | KimiK25Integration placeholder | Low | P3 |
| TD-008 | MAPE-K duplication | Medium | P2 |

---

*Создано: 2026-02-22*  
*Updated: 2026-02-23 — Added Architecture Review Findings*

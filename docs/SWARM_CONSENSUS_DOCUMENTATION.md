# Swarm Consensus Module Documentation

## Overview

Модуль Swarm Consensus реализует распределённые алгоритмы консенсуса для координации ИИ-агентов в децентрализованной среде. Поддерживает несколько алгоритмов консенсуса для различных сценариев использования.

## Архитектура

```
src/swarm/
├── consensus.py           # Базовый ConsensusEngine и RaftNode
├── paxos.py              # Реализация Paxos и Multi-Paxos
├── pbft.py               # Byzantine Fault Tolerant консенсус
├── consensus_integration.py  # Унифицированный интерфейс
└── __init__.py           # Экспорт всех компонентов
```

## Компоненты

### 1. ConsensusEngine (`consensus.py`)

Базовый движок консенсуса с поддержкой 7 алгоритмов:

```python
from src.swarm import ConsensusEngine, ConsensusAlgorithm

engine = ConsensusEngine()

# Создание голосов
votes = [
    Vote(voter_id="agent-1", choice="option-a", weight=1.0),
    Vote(voter_id="agent-2", choice="option-b", weight=1.5),
]

# Достижение консенсуса
result = engine.reach_consensus(
    votes=votes,
    algorithm=ConsensusAlgorithm.WEIGHTED,
)

if result.success:
    print(f"Winner: {result.decision.value}")
```

**Поддерживаемые алгоритмы:**
- `SIMPLE_MAJORITY` - Простое большинство (>50%)
- `SUPERMAJORITY` - Супербольшинство (2/3)
- `UNANIMOUS` - Единогласие (100%)
- `WEIGHTED` - Взвешенное голосование
- `RAFT` - Leader-based консенсус
- `PAXOS` - Распределённый консенсус
- `BYZANTINE` - Устойчивость к византийским сбоям

### 2. RaftNode (`consensus.py`)

Реализация алгоритма Raft для leader-based решений:

```python
from src.swarm import RaftNode

raft = RaftNode(
    node_id="node-1",
    peers={"node-2", "node-3"},
    election_timeout=5.0,
)

# Запуск выбора лидера
await raft.start_election()

# Проверка состояния
if raft.is_leader():
    decision = await raft.propose("value")
```

**Состояния Raft:**
- `FOLLOWER` - Следует за лидером
- `CANDIDATE` - Кандидат на лидерство
- `LEADER` - Лидер кластера

### 3. PaxosNode (`paxos.py`)

Полная реализация алгоритма Paxos:

```python
from src.swarm import PaxosNode, ProposalNumber

# Создание узла
paxos = PaxosNode(
    node_id="proposer-1",
    peers={"acceptor-1", "acceptor-2", "acceptor-3"},
    quorum_size=2,  # Большинство из 3
)

# Предложение значения
success, value = await paxos.propose(
    value="decision-value",
    instance_id="instance-1",
)

if success:
    print(f"Committed: {value}")
```

**Фазы Paxos:**
1. **Phase 1 (Prepare/Promise)** - Proposer отправляет Prepare, Acceptors отвечают Promise
2. **Phase 2 (Accept/Accepted)** - Proposer отправляет Accept, Acceptors отвечают Accepted
3. **Commit** - Значение зафиксировано

### 4. MultiPaxos (`paxos.py`)

Оптимизированный Paxos для последовательности решений:

```python
from src.swarm import MultiPaxos

multipaxos = MultiPaxos(
    node_id="leader",
    peers={"replica-1", "replica-2"},
    leader_id="leader",  # Стабильный лидер
)

# Propose skips Phase 1 for subsequent proposals
success, value = await multipaxos.propose("value-1")
success, value = await multipaxos.propose("value-2")

# Получение лога
log = multipaxos.get_log()  # [(instance_id, value), ...]
```

### 5. PBFTNode (`pbft.py`)

Practical Byzantine Fault Tolerance для византийских сценариев:

```python
from src.swarm import PBFTNode

# 4 узла могут tolerate 1 Byzantine node
pbft = PBFTNode(
    node_id="replica-1",
    peers={"replica-2", "replica-3", "replica-4"},
    f=1,  # Max Byzantine nodes
)

# Отправка запроса
success, result = await pbft.request({
    "operation": "transfer",
    "amount": 100,
})
```

**Фазы PBFT:**
1. **Pre-Prepare** - Primary отправляет запрос с sequence number
2. **Prepare** - Реплики верифицируют и отправляют prepare
3. **Commit** - После 2f+1 prepares, реплики отправляют commit
4. **Execute** - После 2f+1 commits, реплики выполняют операцию

**Гарантии PBFT:**
- Safety: Все честные узлы выполняют одну и ту же операцию
- Liveness: Система продолжает работать при f < n/3 Byzantine узлов

### 6. SwarmConsensusManager (`consensus_integration.py`)

Унифицированный интерфейс для всех алгоритмов:

```python
from src.swarm import (
    SwarmConsensusManager,
    ConsensusMode,
    AgentInfo,
)

# Создание менеджера
manager = SwarmConsensusManager(
    node_id="agent-1",
    agents={
        "agent-1": AgentInfo(
            agent_id="agent-1",
            name="Gemini",
            capabilities={"code", "research"},
            weight=1.0,
        ),
        "agent-2": AgentInfo(
            agent_id="agent-2",
            name="Claude",
            capabilities={"code", "analysis"},
            weight=1.2,
        ),
    },
    default_mode=ConsensusMode.SIMPLE,
)

# Принятие решения
decision = await manager.decide(
    topic="architecture-choice",
    proposals=["microservices", "monolith", "serverless"],
    mode=ConsensusMode.WEIGHTED,
)

print(f"Winner: {decision.winner}")
print(f"Duration: {decision.duration_ms}ms")
```

## Режимы консенсуса

| Режим | Алгоритм | Использование | Byzantine Tolerance |
|-------|----------|---------------|---------------------|
| `SIMPLE` | Simple Majority | Быстрые решения | Нет |
| `RAFT` | Raft | Leader-based, лог репликация | Нет |
| `PAXOS` | Paxos | Распределённый консенсус | Нет |
| `MULTIPAXOS` | Multi-Paxos | Последовательность решений | Нет |
| `PBFT` | PBFT | Критические операции | Да (f < n/3) |
| `WEIGHTED` | Weighted Voting | Учёт возможностей агентов | Нет |

## Выбор алгоритма

```python
def select_algorithm(
    num_agents: int,
    requires_byzantine_tolerance: bool,
    is_sequential: bool,
    performance_critical: bool,
) -> ConsensusMode:
    """
    Рекомендации по выбору алгоритма.
    """
    if requires_byzantine_tolerance:
        return ConsensusMode.PBFT
    
    if is_sequential and performance_critical:
        return ConsensusMode.MULTIPAXOS
    
    if num_agents <= 5 and performance_critical:
        return ConsensusMode.SIMPLE
    
    if num_agents > 10:
        return ConsensusMode.RAFT
    
    return ConsensusMode.PAXOS
```

## Интеграция с SwarmOrchestrator

```python
from src.swarm import SwarmOrchestrator, SwarmConsensusManager

# Создание swarm
orchestrator = SwarmOrchestrator(config)

# Интеграция с consensus
consensus = SwarmConsensusManager(
    node_id="orchestrator",
    agents={
        agent.id: AgentInfo(
            agent_id=agent.id,
            name=agent.name,
            capabilities=agent.capabilities,
        )
        for agent in orchestrator.agents
    },
)

# Использование для распределённых решений
async def make_swarm_decision(topic: str, options: list):
    decision = await consensus.decide(topic, options)
    
    if decision.success:
        await orchestrator.broadcast({
            "type": "decision",
            "topic": topic,
            "result": decision.winner,
        })
    
    return decision
```

## Метрики и мониторинг

```python
# Получение статистики
stats = manager.get_stats()

# {
#     "total_decisions": 150,
#     "successful": 145,
#     "failed": 5,
#     "success_rate": 0.967,
#     "mode_usage": {
#         "simple": 80,
#         "weighted": 40,
#         "pbft": 30,
#     },
#     "avg_duration_ms": 45.2,
#     "agents": 4,
# }
```

## Тестирование

```bash
# Запуск тестов
pytest tests/test_swarm_consensus.py -v

# С покрытием
pytest tests/test_swarm_consensus.py --cov=src/swarm --cov-report=html
```

## Производительность

| Алгоритм | Latency (3 nodes) | Throughput | Byzantine Tolerance |
|----------|-------------------|------------|---------------------|
| Simple | ~5ms | 1000+ ops/s | Нет |
| Raft | ~20ms | 500 ops/s | Нет |
| Paxos | ~30ms | 400 ops/s | Нет |
| MultiPaxos | ~15ms | 600 ops/s | Нет |
| PBFT | ~50ms | 200 ops/s | Да (f=1) |

## Best Practices

1. **Выбор алгоритма:**
   - Используйте `SIMPLE` для быстрых некритичных решений
   - Используйте `RAFT` для leader-based сценариев
   - Используйте `PBFT` для критических операций с недоверенными узлами

2. **Настройка quorum:**
   - Стандартный quorum = majority (n/2 + 1)
   - Для критичных решений используйте supermajority (2n/3 + 1)

3. **Обработка сбоев:**
   - Реализуйте timeout для всех операций
   - Используйте retry с exponential backoff
   - Мониторьте health всех узлов

4. **Масштабирование:**
   - При >10 узлах используйте Raft или MultiPaxos
   - При >50 узлах рассмотрите иерархический консенсус

## Changelog

### Phase 2 (2026-02-21)
- Добавлен PaxosNode с полной реализацией Paxos
- Добавлен MultiPaxos для последовательности решений
- Добавлен PBFTNode для Byzantine fault tolerance
- Добавлен SwarmConsensusManager для унифицированного интерфейса
- Добавлены комплексные тесты для всех алгоритмов
- Обновлён __init__.py с экспортом новых компонентов

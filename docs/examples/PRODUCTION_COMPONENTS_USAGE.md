# 📚 Production Components Usage Examples

**Версия:** 1.0  
**Дата:** 2026-01-XX  
**Статус:** ✅ **PRODUCTION-READY**

---

## 📋 Обзор

Примеры использования новых production-ready компонентов, добавленных в Q1 2026.

---

## 🔒 Zero Trust Enforcement

### Базовое использование

```python
from src.security.zero_trust.enforcement import get_zero_trust_enforcer

# Получить enforcer
enforcer = get_zero_trust_enforcer()

# Проверить доступ peer
result = enforcer.enforce(
    peer_spiffe_id="spiffe://x0tta6bl4.mesh/workload/api",
    resource="/api/v1/health",
    action="read"
)

if result.allowed:
    print(f"✅ Access granted. Trust score: {result.trust_score}")
else:
    print(f"❌ Access denied. Reason: {result.reason}")
```

### Интеграция в FastAPI

```python
from fastapi import FastAPI, Request, HTTPException
from src.security.zero_trust.enforcement import get_zero_trust_enforcer

app = FastAPI()
enforcer = get_zero_trust_enforcer()

@app.middleware("http")
async def zero_trust_middleware(request: Request, call_next):
    # Извлечь SPIFFE ID из заголовков
    peer_spiffe_id = request.headers.get("X-SPIFFE-ID")
    if not peer_spiffe_id:
        raise HTTPException(status_code=403, detail="Missing SPIFFE ID")
    
    # Проверить доступ
    result = enforcer.enforce(
        peer_spiffe_id=peer_spiffe_id,
        resource=request.url.path
    )
    
    if not result.allowed:
        raise HTTPException(status_code=403, detail=result.reason)
    
    response = await call_next(request)
    return response
```

### Получение статистики

```python
stats = enforcer.get_enforcement_stats()
print(f"Total requests: {stats['total_requests']}")
print(f"Allow rate: {stats['allow_rate']*100:.1f}%")
print(f"Deny rate: {stats['deny_rate']*100:.1f}%")
print(f"Tracked peers: {stats['tracked_peers']}")
```

---

## 🗳️ Raft Consensus

### Базовое использование

```python
from src.consensus.raft_production import get_production_raft_node

# Создать production node
node = get_production_raft_node(
    node_id="node-1",
    peers=["node-2", "node-3", "node-4"],
    storage_path="/var/lib/x0tta6bl4/raft/node-1"
)

# Append entry (только если leader)
success = node.append_entry({"command": "set", "key": "foo", "value": "bar"})

# Get status
status = node.get_status()
print(f"State: {status['state']}")
print(f"Term: {status['term']}")
print(f"Commit Index: {status['commit_index']}")
```

### Создание snapshot

```python
# Создать snapshot
snapshot_data = {
    "state": {"key1": "value1", "key2": "value2"},
    "metadata": {"version": "1.0"}
}

success = node.create_snapshot(
    last_included_index=100,
    snapshot_data=snapshot_data
)
```

### Регистрация callback для применения команд

```python
def apply_command(entry):
    """Apply committed log entry to state machine"""
    command = entry.command
    if command["command"] == "set":
        state_machine[command["key"]] = command["value"]
    elif command["command"] == "delete":
        del state_machine[command["key"]]

# Register callback
node.raft_node.register_apply_callback(apply_command)
```

---

## 🔄 CRDT Sync

### Базовое использование

```python
from src.data_sync.crdt_optimizations import get_crdt_optimizer
from src.data_sync.crdt_sync import LWWRegister, Counter, ORSet

# Создать optimizer
optimizer = get_crdt_optimizer("node-1")

# Register CRDTs
lww = LWWRegister()
lww.set("initial-value", "node-1")
optimizer.register_crdt("shared-key", lww)

counter = Counter()
counter.increment("node-1", 10)
optimizer.register_crdt("shared-counter", counter)

# Sync with peer
peer_state = {
    "shared-key": peer_lww,
    "shared-counter": peer_counter
}

local_deltas = optimizer.sync_with_peer("node-2", peer_state)
print(f"Synced with node-2. Sent {len(local_deltas)} deltas")
```

### Batch apply deltas

```python
# Получить deltas от peer
peer_deltas = {
    "shared-key": [
        CRDTDelta(
            key="shared-key",
            operation="set",
            value="new-value",
            timestamp=datetime.now(),
            node_id="node-2",
            checksum="abc123"
        )
    ]
}

# Применить batch
applied = optimizer.batch_apply_deltas(peer_deltas)
print(f"Applied {applied} deltas")
```

### Получение метрик

```python
metrics = optimizer.get_metrics()
print(f"Total syncs: {metrics['total_syncs']}")
print(f"Success rate: {metrics['success_rate']*100:.1f}%")
print(f"Avg sync duration: {metrics['avg_sync_duration_ms']:.2f}ms")
print(f"Bytes sent: {metrics['bytes_sent']:,}")
print(f"Conflicts resolved: {metrics['conflicts_resolved']}")
```

---

## 🔧 Recovery Actions

### Базовое использование

```python
from src.self_healing.recovery_actions import RecoveryActionExecutor

# Создать executor
executor = RecoveryActionExecutor(node_id="node-1")

# Restart service
success = await executor.restart_service(
    service_name="api-service",
    namespace="default"
)

# Scale up deployment
success = await executor.scale_up(
    deployment_name="api-deployment",
    replicas=5,
    namespace="default"
)

# Switch route
success = await executor.switch_route(
    old_route="route-1",
    new_route="route-2"
)

# Clear cache
success = await executor.clear_cache(
    service_name="api-service",
    cache_type="all"
)

# Failover
success = await executor.failover(
    service_name="api-service",
    primary_region="us-east-1",
    fallback_region="eu-west-1"
)

# Quarantine node
success = await executor.quarantine_node("problematic-node")
```

### Динамическое выполнение

```python
# Выполнить действие динамически
success = await executor.execute_action(
    "Restart service",
    service_name="api-service",
    namespace="default"
)

success = await executor.execute_action(
    "Scale up",
    deployment_name="api-deployment",
    replicas=5,
    namespace="default"
)
```

### Интеграция с MAPE-K

```python
from src.self_healing.mape_k import MAPEKExecutor
from src.self_healing.recovery_actions import RecoveryActionExecutor

# MAPE-K executor использует RecoveryActionExecutor
executor = MAPEKExecutor(node_id="node-1")

# MAPE-K автоматически использует recovery actions
await executor.execute("Restart service", service_name="api-service")
```

---

## 🔄 Комплексные примеры

### Полный Zero Trust + Raft + CRDT flow

```python
from src.security.zero_trust.enforcement import get_zero_trust_enforcer
from src.consensus.raft_production import get_production_raft_node
from src.data_sync.crdt_optimizations import get_crdt_optimizer

# Initialize components
enforcer = get_zero_trust_enforcer()
raft_node = get_production_raft_node("node-1", ["node-2", "node-3"])
crdt_optimizer = get_crdt_optimizer("node-1")

# 1. Zero Trust check
peer_id = "spiffe://x0tta6bl4.mesh/workload/api"
result = enforcer.enforce(peer_id, "/api/v1/data")

if result.allowed:
    # 2. Raft consensus (if leader)
    if raft_node.get_status()["state"] == "leader":
        raft_node.append_entry({
            "command": "update",
            "key": "data",
            "value": "new-value"
        })
    
    # 3. CRDT sync
    crdt_optimizer.sync_with_peer("node-2", peer_crdt_state)
```

### MAPE-K с Recovery Actions

```python
from src.self_healing.mape_k_integrated import IntegratedMAPEKCycle
from src.self_healing.recovery_actions import RecoveryActionExecutor

# Integrated MAPE-K использует RecoveryActionExecutor
mapek = IntegratedMAPEKCycle(node_id="node-1")

# Run cycle with metrics
metrics = {
    "cpu_percent": 85.0,
    "memory_percent": 80.0,
    "error_rate": 0.05
}

result = await mapek.run_cycle(metrics)

# Recovery actions автоматически выполняются
if result["action_executed"]:
    print(f"✅ Recovery action executed: {result['action']}")
```

---

## 📊 Мониторинг и метрики

### Экспорт метрик в Prometheus

```python
from prometheus_client import Gauge, Counter

# Zero Trust metrics
zero_trust_requests = Counter(
    'zero_trust_requests_total',
    'Total Zero Trust enforcement requests',
    ['peer_id', 'result']
)

zero_trust_trust_score = Gauge(
    'zero_trust_trust_score',
    'Trust score for peer',
    ['peer_id']
)

# Raft metrics
raft_term = Gauge('raft_term', 'Current Raft term', ['node_id'])
raft_state = Gauge('raft_state', 'Raft node state', ['node_id', 'state'])

# CRDT metrics
crdt_sync_duration = Gauge(
    'crdt_sync_duration_seconds',
    'CRDT sync duration',
    ['node_id', 'peer_id']
)
```

---

## ✅ Best Practices

1. **Используйте get_* функции** - они обеспечивают singleton pattern
2. **Обрабатывайте ошибки** - все методы могут выбрасывать исключения
3. **Мониторьте метрики** - используйте встроенные метрики для observability
4. **Тестируйте в staging** - проверяйте все компоненты перед production
5. **Документируйте изменения** - ведите changelog для всех изменений

---

**Последнее обновление:** 2026-01-XX  
**Версия:** 1.0  
**Статус:** ✅ Production-ready


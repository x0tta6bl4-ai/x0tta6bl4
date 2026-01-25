# ⚙️ Configuration Guide for Production Components

**Версия:** 1.0  
**Дата:** 2026-01-XX  
**Статус:** ✅ **PRODUCTION-READY**

---

## 📋 Обзор

Руководство по конфигурации новых production-ready компонентов, добавленных в Q1 2026.

---

## 🔒 Zero Trust Enforcement

### Конфигурационный файл: `config/zero_trust.yaml`

**Основные параметры:**

```yaml
zero_trust:
  trust_scoring:
    initial_score: 0.5  # Начальный trust score для новых peers
    thresholds:
      untrusted: 0.2
      low: 0.4
      medium: 0.7
      high: 0.9
      trusted: 1.0
    adjustments:
      successful_access: 0.05   # Награда за успешный доступ
      failed_access: -0.1       # Штраф за неудачный доступ
```

**Использование:**

```python
from src.security.zero_trust.enforcement import get_zero_trust_enforcer

# Enforcer автоматически использует конфигурацию
enforcer = get_zero_trust_enforcer()

# Проверка доступа
result = enforcer.enforce(
    peer_spiffe_id="spiffe://x0tta6bl4.mesh/workload/api",
    resource="/api/v1/health"
)
```

**Environment Variables:**
```bash
ZERO_TRUST_CONFIG_PATH=/path/to/zero_trust.yaml
ZERO_TRUST_INITIAL_SCORE=0.5
ZERO_TRUST_AUTO_ISOLATE=true
```

---

## 🗳️ Raft Consensus

### Конфигурационный файл: `config/raft_production.yaml`

**Основные параметры:**

```yaml
raft:
  node:
    node_id: "${NODE_ID:-node-1}"
    peers: ["node-2", "node-3", "node-4", "node-5"]
    storage:
      path: "/var/lib/x0tta6bl4/raft/${NODE_ID}"
      backup:
        enabled: true
        interval_hours: 24
  algorithm:
    election_timeout:
      min: 150
      max: 300
    heartbeat_interval: 50
```

**Использование:**

```python
from src.consensus.raft_production import get_production_raft_node

node = get_production_raft_node(
    node_id="node-1",
    peers=["node-2", "node-3"],
    storage_path="/var/lib/x0tta6bl4/raft/node-1"
)

# Append entry
success = node.append_entry({"command": "update", "key": "value"})

# Get status
status = node.get_status()
```

**Environment Variables:**
```bash
RAFT_NODE_ID=node-1
RAFT_PEERS=node-2,node-3,node-4
RAFT_STORAGE_PATH=/var/lib/x0tta6bl4/raft
RAFT_ELECTION_TIMEOUT_MIN=150
RAFT_ELECTION_TIMEOUT_MAX=300
RAFT_HEARTBEAT_INTERVAL=50
```

---

## 🔄 CRDT Sync

### Конфигурационный файл: `config/crdt_sync.yaml`

**Основные параметры:**

```yaml
crdt_sync:
  optimization:
    delta_sync: true
    compression: true
    compression_algorithm: "gzip"
    batch_size: 100
  performance:
    sync_interval: 5
    max_parallel_peers: 5
```

**Использование:**

```python
from src.data_sync.crdt_optimizations import get_crdt_optimizer
from src.data_sync.crdt_sync import LWWRegister

optimizer = get_crdt_optimizer("node-1")

# Register CRDT
lww = LWWRegister()
lww.set("value", "node-1")
optimizer.register_crdt("key", lww)

# Sync with peer
peer_state = {"key": peer_lww}
deltas = optimizer.sync_with_peer("node-2", peer_state)
```

**Environment Variables:**
```bash
CRDT_NODE_ID=node-1
CRDT_DELTA_SYNC=true
CRDT_COMPRESSION=true
CRDT_SYNC_INTERVAL=5
CRDT_MAX_PARALLEL_PEERS=5
```

---

## 🔧 Recovery Actions

### Конфигурационный файл: `config/recovery_actions.yaml`

**Основные параметры:**

```yaml
recovery_actions:
  node:
    node_id: "${NODE_ID:-default-node}"
  timeouts:
    restart_service: 60
    scale_up: 120
    failover: 180
  kubernetes:
    default_namespace: "default"
    wait_for_rollout: true
```

**Использование:**

```python
from src.self_healing.recovery_actions import RecoveryActionExecutor

executor = RecoveryActionExecutor(node_id="node-1")

# Restart service
await executor.restart_service("api-service", "default")

# Scale up
await executor.scale_up("api-deployment", replicas=5, namespace="default")

# Failover
await executor.failover(
    "api-service",
    "us-east-1",
    "eu-west-1"
)
```

**Environment Variables:**
```bash
RECOVERY_NODE_ID=node-1
RECOVERY_KUBECTL_PATH=/usr/bin/kubectl
RECOVERY_DEFAULT_NAMESPACE=default
RECOVERY_RESTART_TIMEOUT=60
RECOVERY_SCALE_TIMEOUT=120
```

---

## 🔄 Загрузка конфигурации

### Python

```python
import yaml
from pathlib import Path

def load_config(config_name: str) -> dict:
    """Load configuration from YAML file"""
    config_path = Path(f"config/{config_name}.yaml")
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f)
    return {}

# Load configurations
zero_trust_config = load_config("zero_trust")
raft_config = load_config("raft_production")
crdt_config = load_config("crdt_sync")
recovery_config = load_config("recovery_actions")
```

### Environment Variables Override

Все конфигурации могут быть переопределены через environment variables:

```bash
# Zero Trust
export ZERO_TRUST_INITIAL_SCORE=0.6
export ZERO_TRUST_AUTO_ISOLATE=true

# Raft
export RAFT_ELECTION_TIMEOUT_MIN=200
export RAFT_ELECTION_TIMEOUT_MAX=400

# CRDT
export CRDT_SYNC_INTERVAL=10
export CRDT_COMPRESSION=true

# Recovery
export RECOVERY_RESTART_TIMEOUT=90
export RECOVERY_SCALE_TIMEOUT=180
```

---

## 📊 Валидация конфигурации

### Скрипт проверки

```bash
# Проверить все конфигурации
python3 -c "
import yaml
from pathlib import Path

configs = ['zero_trust', 'raft_production', 'crdt_sync', 'recovery_actions']
for config in configs:
    path = Path(f'config/{config}.yaml')
    if path.exists():
        with open(path) as f:
            yaml.safe_load(f)
        print(f'✅ {config}.yaml is valid')
    else:
        print(f'❌ {config}.yaml not found')
"
```

---

## 🔧 Production Deployment

### Kubernetes ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: x0tta6bl4-config
data:
  zero_trust.yaml: |
    # Zero Trust configuration
    zero_trust:
      trust_scoring:
        initial_score: 0.5
  raft_production.yaml: |
    # Raft configuration
    raft:
      node:
        node_id: "${NODE_ID}"
  crdt_sync.yaml: |
    # CRDT configuration
    crdt_sync:
      optimization:
        delta_sync: true
  recovery_actions.yaml: |
    # Recovery configuration
    recovery_actions:
      node:
        node_id: "${NODE_ID}"
```

---

## ✅ Best Practices

1. **Используйте environment variables для production** - не храните секреты в YAML
2. **Валидируйте конфигурацию при старте** - проверяйте все параметры
3. **Используйте defaults** - предоставляйте разумные значения по умолчанию
4. **Документируйте изменения** - ведите changelog для конфигураций
5. **Тестируйте конфигурации** - проверяйте в staging перед production

---

**Последнее обновление:** 2026-01-XX  
**Версия:** 1.0  
**Статус:** ✅ Production-ready


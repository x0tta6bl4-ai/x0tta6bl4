# 🔥 HOTFIX: PQC Containment Plan (0-24 часа)

**Дата**: 2025-12-25  
**Критичность**: 🔴 **CRITICAL**  
**Статус**: В ПРОЦЕССЕ

---

## 📍 Где используется SimplifiedNTRU

**Ответ на вопрос**: SimplifiedNTRU используется в **внутреннем протоколе обмена ключами** для mesh network, НЕ в mTLS handshake и НЕ в WireGuard.

### Точки использования:

1. **`src/core/app.py:36`** → `PQMeshSecurity` → `HybridEncryption` → `SimplifiedNTRU`
   - Используется для key exchange между mesh узлами
   - **Критично**: Это часть control-plane безопасности

2. **`src/security/post_quantum.py:409`** → `PQMeshSecurity` класс
   - Используется для установки secure channels между peers
   - Используется для шифрования mesh сообщений

3. **`src/security/post_quantum.py:273`** → `QuantumSafeKeyExchange`
   - Используется для key exchange протокола
   - Использует `HybridEncryption` → `SimplifiedNTRU`

### НЕ используется в:
- ❌ mTLS handshake (используется SPIFFE/SPIRE)
- ❌ WireGuard (не интегрирован)
- ❌ TLS handshake (есть отдельный `hybrid_tls.py` с реальным PQC)

---

## 🚨 PHASE 1: CONTAINMENT (0-24 часа)

### Задача 1.1: Запретить SimplifiedNTRU в production

**Файл**: `src/security/post_quantum.py`

```python
# Добавить compile-time guard
import os

PRODUCTION_MODE = os.getenv("X0TTA6BL4_PRODUCTION", "false").lower() == "true"
ALLOW_MOCK_PQC = os.getenv("X0TTA6BL4_ALLOW_MOCK_PQC", "false").lower() == "true"

class SimplifiedNTRU:
    def __init__(self, params: NTRUParameters = None):
        if PRODUCTION_MODE and not ALLOW_MOCK_PQC:
            raise RuntimeError(
                "🔴 SimplifiedNTRU запрещён в production! "
                "Используйте LibOQSBackend из post_quantum_liboqs.py"
            )
        # ... rest of code
```

### Задача 1.2: Заменить PQMeshSecurity на PQMeshSecurityLibOQS

**Файл**: `src/core/app.py`

```python
# БЫЛО:
from src.security.post_quantum import PQMeshSecurity
security = PQMeshSecurity(node_id)

# СТАЛО:
try:
    from src.security.post_quantum_liboqs import PQMeshSecurityLibOQS
    security = PQMeshSecurityLibOQS(node_id)
    logger.info("✅ Using real PQC (liboqs)")
except ImportError:
    logger.error("🔴 liboqs not available - PQC security disabled!")
    raise RuntimeError("liboqs-python required for production")
```

### Задача 1.3: Добавить fallback с алертами

**Файл**: `src/security/pqc_fallback.py` (новый)

```python
"""
PQC Fallback Handler with Alerting
"""
import logging
from typing import Optional, Tuple
from prometheus_client import Counter, Histogram

logger = logging.getLogger(__name__)

# Prometheus metrics
pqc_fallback_total = Counter(
    'pqc_fallback_total',
    'Total PQC fallback events',
    ['reason']
)

pqc_handshake_success_rate = Counter(
    'pqc_handshake_success_total',
    'Total successful PQC handshakes'
)

pqc_handshake_failure_total = Counter(
    'pqc_handshake_failure_total',
    'Total failed PQC handshakes',
    ['reason']
)

pqc_handshake_p95_latency = Histogram(
    'pqc_handshake_latency_seconds',
    'PQC handshake latency',
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0]
)

class PQCFallbackHandler:
    """
    Handles PQC fallback with strict TTL and alerting.
    """
    FALLBACK_TTL = 3600  # 1 hour max fallback
    _fallback_start_time: Optional[float] = None
    _fallback_reason: Optional[str] = None
    
    @classmethod
    def enable_fallback(cls, reason: str):
        """Enable fallback mode with alerting."""
        import time
        cls._fallback_start_time = time.time()
        cls._fallback_reason = reason
        
        pqc_fallback_total.labels(reason=reason).inc()
        
        logger.critical(
            f"🔴 PQC FALLBACK ENABLED: {reason}. "
            f"System running in INSECURE mode! "
            f"TTL: {cls.FALLBACK_TTL}s"
        )
        
        # Send alert (integrate with your alerting system)
        # send_alert("PQC_FALLBACK_ENABLED", reason=reason)
    
    @classmethod
    def check_fallback_ttl(cls) -> bool:
        """Check if fallback TTL expired."""
        if cls._fallback_start_time is None:
            return False
        
        import time
        elapsed = time.time() - cls._fallback_start_time
        
        if elapsed > cls.FALLBACK_TTL:
            logger.critical(
                f"🔴 PQC FALLBACK TTL EXPIRED ({elapsed:.0f}s > {cls.FALLBACK_TTL}s). "
                f"Shutting down for security!"
            )
            # In production, this should trigger graceful shutdown
            # raise SystemExit("PQC fallback TTL expired")
            return True
        
        return False
    
    @classmethod
    def is_fallback_enabled(cls) -> bool:
        """Check if fallback is currently enabled."""
        return cls._fallback_start_time is not None
```

### Задача 1.4: Добавить метрики и алерты

**Файл**: `src/monitoring/pqc_metrics.py` (новый)

```python
"""
PQC Handshake Metrics and SLI/SLO
"""
from prometheus_client import Counter, Histogram, Gauge
import time

# SLI/SLO Metrics
pqc_handshake_success_rate = Counter(
    'pqc_handshake_success_total',
    'Total successful PQC handshakes'
)

pqc_handshake_failure_total = Counter(
    'pqc_handshake_failure_total',
    'Total failed PQC handshakes',
    ['reason']  # 'timeout', 'invalid_key', 'liboqs_error', etc.
)

pqc_handshake_p95_latency = Histogram(
    'pqc_handshake_latency_seconds',
    'PQC handshake latency (p95 target: <0.1s)',
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0]
)

pqc_fallback_rate = Gauge(
    'pqc_fallback_enabled',
    'PQC fallback enabled (1=yes, 0=no)'
)

key_rotation_success_rate = Counter(
    'pqc_key_rotation_success_total',
    'Total successful PQC key rotations'
)

key_rotation_failure_total = Counter(
    'pqc_key_rotation_failure_total',
    'Total failed PQC key rotations',
    ['reason']
)

# SLO Targets
PQC_HANDSHAKE_SUCCESS_RATE_SLO = 0.99  # 99% success rate
PQC_HANDSHAKE_P95_LATENCY_SLO = 0.1   # 100ms p95 latency
PQC_FALLBACK_RATE_SLO = 0.0            # 0% fallback (zero tolerance)

def record_handshake_success(latency: float):
    """Record successful PQC handshake."""
    pqc_handshake_success_rate.inc()
    pqc_handshake_p95_latency.observe(latency)
    
    # Check SLO violation
    if latency > PQC_HANDSHAKE_P95_LATENCY_SLO:
        logger.warning(
            f"⚠️ PQC handshake latency SLO violation: {latency:.3f}s > {PQC_HANDSHAKE_P95_LATENCY_SLO}s"
        )

def record_handshake_failure(reason: str):
    """Record failed PQC handshake."""
    pqc_handshake_failure_total.labels(reason=reason).inc()
    
    # Alert on any failure (zero tolerance)
    logger.error(f"🔴 PQC handshake failure: {reason}")
    # send_alert("PQC_HANDSHAKE_FAILURE", reason=reason)
```

---

## ✅ КРИТЕРИИ DONE (0-24 часа)

- [ ] SimplifiedNTRU запрещён в production (compile-time guard)
- [ ] `app.py` использует `PQMeshSecurityLibOQS` вместо `PQMeshSecurity`
- [ ] Fallback handler с TTL и алертами реализован
- [ ] Метрики PQC handshake добавлены (success_rate, latency, fallback_rate)
- [ ] Алерт на любой `pqc_handshake_failure_total > 0`
- [ ] Тесты пройдены (unit + integration)
- [ ] Документация обновлена

---

## 🧪 СИНТЕТИЧЕСКИЕ ПРОВЕРКИ

### Тест 1: Принудительный fallback

```python
# tests/integration/test_pqc_fallback.py
def test_forced_fallback():
    """Test that system correctly falls back when PQC disabled."""
    # Disable liboqs
    os.environ['X0TTA6BL4_DISABLE_PQC'] = 'true'
    
    # System should:
    # 1. Enable fallback mode
    # 2. Send alert
    # 3. Continue operating (with reduced security)
    # 4. Shutdown after TTL expires
    
    assert PQCFallbackHandler.is_fallback_enabled()
    assert pqc_fallback_total.labels(reason='forced')._value.get() > 0
```

### Тест 2: Split-brain simulation

```python
# tests/integration/test_split_brain.py
def test_split_brain_governance():
    """Test governance/control-plane behavior during partition."""
    # Simulate network partition
    # 1. Split network into two partitions
    # 2. Each partition should:
    #    - Detect partition (quorum validation)
    #    - Continue operating independently
    #    - Merge when partition heals
    #    - Reject conflicting governance decisions
```

---

## 📊 МЕТРИКИ ДЛЯ МОНИТОРИНГА

### SLI/SLO Targets

| Метрика | SLI | SLO Target | Alert Threshold |
|---------|-----|------------|----------------|
| `pqc_handshake_success_rate` | Success / Total | ≥ 99% | < 99% |
| `pqc_handshake_p95_latency` | p95 latency | < 100ms | > 100ms |
| `pqc_fallback_rate` | Fallback enabled | 0% | > 0% |
| `key_rotation_success_rate` | Success / Total | ≥ 99% | < 99% |

### Prometheus Queries

```promql
# PQC Handshake Success Rate
rate(pqc_handshake_success_total[5m]) / 
  (rate(pqc_handshake_success_total[5m]) + rate(pqc_handshake_failure_total[5m]))

# PQC Handshake p95 Latency
histogram_quantile(0.95, rate(pqc_handshake_latency_seconds_bucket[5m]))

# PQC Fallback Rate
pqc_fallback_enabled

# Alert: Any PQC failure
rate(pqc_handshake_failure_total[5m]) > 0
```

---

## 🚀 СЛЕДУЮЩИЕ ФАЗЫ

### Phase 2: Stabilization (24-72 часа)
- Подключить реальную PQC (hybrid KEM)
- Прогнать тест-векторы
- Негативные тесты (broken KEM, key desync, downgrade-attempt)

### Phase 3: Hardening (1-2 недели)
- Byzantine protection для control-plane
- Signed gossip + anti-replay
- Quorum validation для критических событий
- Policy-as-code в CI/CD

---

**Статус**: 🔄 В ПРОЦЕССЕ (0-24 часа containment)


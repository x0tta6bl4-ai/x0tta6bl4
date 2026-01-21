# 📦 Required vs Optional Dependencies

**Дата:** 2026-01-03  
**Версия:** x0tta6bl4 v3.4  
**Цель:** Четкое разделение required и optional dependencies

---

## 🔴 Required Dependencies (MANDATORY)

Эти зависимости **обязательны** для работы системы. Без них система не запустится или будет работать некорректно.

### Core Dependencies
```python
fastapi>=0.119.1          # Web framework
uvicorn==0.38.0           # ASGI server
pydantic==2.12.3          # Data validation
python-dotenv==1.1.1      # Environment variables
httpx==0.28.1             # HTTP client
requests==2.32.4          # HTTP library
cryptography==46.0.3      # Cryptographic primitives
```

### Security Dependencies
```python
liboqs-python==0.14.1     # Post-Quantum Cryptography (MANDATORY in production)
py-spiffe>=0.2.0          # SPIFFE/SPIRE integration
python-jose[cryptography]==3.4.0  # JWT handling
PyJWT==2.10.1             # JWT tokens
bcrypt==5.0.0             # Password hashing
```

### Data & Storage
```python
redis==5.0.1              # Caching and state
orjson==3.11.3            # Fast JSON
pyyaml==6.0.3             # YAML parsing
```

### Utilities
```python
click==8.3.0              # CLI framework
psutil==7.1.1             # System utilities
structlog==25.4.0         # Structured logging
python-dateutil==2.9.0.post0  # Date handling
pytz==2025.2              # Timezone handling
```

**Статус:** ✅ **Все required dependencies должны быть установлены**

---

## 🟡 Optional Dependencies (GRACEFUL DEGRADATION)

Эти зависимости **опциональны**. Система может работать без них, но с ограниченной функциональностью.

### Post-Quantum Cryptography
```python
liboqs-python==0.14.1     # OPTIONAL: Falls back to SimplifiedNTRU (INSECURE)
```
**Поведение при отсутствии:**
- ⚠️ Система переходит в **degraded mode**
- ⚠️ Используется SimplifiedNTRU (INSECURE - только для тестирования)
- ⚠️ Логируется CRITICAL warning
- ❌ В production mode система **НЕ ЗАПУСТИТСЯ** без liboqs

**Health Check:** `LIBOQS_AVAILABLE` flag

---

### SPIFFE/SPIRE
```python
py-spiffe>=0.2.0          # OPTIONAL: Falls back to basic auth
```
**Поведение при отсутствии:**
- ⚠️ Система переходит в **degraded mode**
- ⚠️ Используется basic authentication
- ⚠️ Логируется WARNING
- ✅ Система продолжает работать

**Health Check:** `SPIFFE_AVAILABLE` flag

---

### eBPF & Cilium
```python
# No Python package - requires kernel support and Cilium deployment
```
**Поведение при отсутствии:**
- ⚠️ eBPF observability недоступна
- ⚠️ Cilium integration отключена
- ⚠️ Логируется WARNING
- ✅ Система продолжает работать с традиционным мониторингом

**Health Check:** `EBPF_AVAILABLE` flag (проверка kernel capabilities)

---

### Machine Learning
```python
torch>=2.0.0              # OPTIONAL: For ML models
transformers>=4.30.0      # OPTIONAL: For language models
sentence-transformers>=2.2.0  # OPTIONAL: For RAG embeddings
hnswlib>=0.7.0            # OPTIONAL: For vector search
```
**Поведение при отсутствии:**
- ⚠️ RAG Pipeline недоступен
- ⚠️ LoRA Fine-tuning недоступен
- ⚠️ GraphSAGE может работать в degraded mode
- ⚠️ Логируется WARNING
- ✅ Core система продолжает работать

**Health Check:** `TORCH_AVAILABLE`, `HNSW_AVAILABLE` flags

---

### Federated Learning
```python
# Uses torch (optional dependency)
```
**Поведение при отсутствии:**
- ⚠️ Federated Learning недоступен
- ⚠️ Логируется WARNING
- ✅ Core система продолжает работать

**Health Check:** `FEDERATED_LEARNING_AVAILABLE` flag

---

### OpenTelemetry
```python
opentelemetry-api         # OPTIONAL: For distributed tracing
opentelemetry-sdk         # OPTIONAL: For tracing SDK
opentelemetry-exporter-jaeger  # OPTIONAL: Jaeger exporter
opentelemetry-exporter-zipkin  # OPTIONAL: Zipkin exporter
opentelemetry-exporter-otlp    # OPTIONAL: OTLP exporter
```
**Поведение при отсутствии:**
- ⚠️ Distributed tracing недоступен
- ⚠️ Логируется WARNING
- ✅ Система продолжает работать с базовым логированием

**Health Check:** `OPENTELEMETRY_AVAILABLE` flag

---

### Blockchain & Web3
```python
web3==6.20.0              # OPTIONAL: For blockchain integration
ipfshttpclient>=0.8.0     # OPTIONAL: For IPFS storage
```
**Поведение при отсутствии:**
- ⚠️ DAO blockchain features недоступны
- ⚠️ IPFS storage недоступен
- ⚠️ Логируется WARNING
- ✅ Core DAO governance продолжает работать (без blockchain)

**Health Check:** `WEB3_AVAILABLE`, `IPFS_AVAILABLE` flags

---

### Monitoring
```python
prometheus-client==0.19.0  # OPTIONAL: For Prometheus metrics
```
**Поведение при отсутствии:**
- ⚠️ Prometheus metrics недоступны
- ⚠️ Логируется WARNING
- ✅ Система продолжает работать с базовым мониторингом

**Health Check:** `PROMETHEUS_AVAILABLE` flag

---

## 🔍 Health Checks Implementation

### Runtime Health Checks

Все optional dependencies должны иметь health checks:

```python
# Example: liboqs health check
if not LIBOQS_AVAILABLE:
    if PRODUCTION_MODE:
        logger.critical("🔴 PRODUCTION MODE: LibOQS REQUIRED!")
        raise RuntimeError("LibOQS not available in production")
    else:
        logger.warning("⚠️ LibOQS not available - using degraded mode")
```

### Health Check Endpoints

```python
# GET /health/dependencies
{
    "liboqs": {
        "available": true,
        "version": "0.14.1",
        "status": "healthy"
    },
    "spiffe": {
        "available": true,
        "version": "0.2.0",
        "status": "healthy"
    },
    "ebpf": {
        "available": false,
        "reason": "kernel not supported",
        "status": "degraded"
    }
}
```

---

## 📋 Dependency Files Structure

### `requirements.txt` (Required)
Все mandatory dependencies с фиксированными версиями.

### `optional-requirements.txt` (Optional)
Все optional dependencies с версиями и описанием graceful degradation.

### `requirements-dev.txt` (Development)
Development dependencies (testing, linting, etc.)

---

## ⚠️ Production Mode Behavior

В **PRODUCTION MODE** (`X0TTA6BL4_PRODUCTION=true`):

1. **liboqs-python** становится **MANDATORY**
   - Система не запустится без liboqs
   - Fail-fast при отсутствии

2. **SPIFFE/SPIRE** рекомендуется как **MANDATORY**
   - Система может работать без него, но с WARNING
   - Логируется как security risk

3. **eBPF** рекомендуется для observability
   - Система работает без него, но с ограниченной observability

4. **ML dependencies** опциональны
   - Система работает без них, но без AI/ML features

---

## 🎯 Recommendations

### Для Development
- Установить все optional dependencies для полной функциональности
- Тестировать graceful degradation scenarios

### Для Staging
- Установить все optional dependencies
- Тестировать production-like scenarios

### Для Production
- **MANDATORY:** liboqs-python
- **RECOMMENDED:** SPIFFE/SPIRE, eBPF, OpenTelemetry
- **OPTIONAL:** ML dependencies (если не используются)

---

## 📊 Dependency Status Dashboard

| Dependency | Type | Production | Health Check | Status |
|------------|------|------------|--------------|--------|
| liboqs-python | Required (Production) | MANDATORY | ✅ | ✅ Implemented |
| py-spiffe | Recommended | RECOMMENDED | ✅ | ✅ Implemented |
| torch | Optional | OPTIONAL | ✅ | ✅ Implemented |
| opentelemetry | Recommended | RECOMMENDED | ✅ | ✅ Implemented |
| web3 | Optional | OPTIONAL | ✅ | ✅ Implemented |
| eBPF | Recommended | RECOMMENDED | ⚠️ | ⚠️ Kernel check needed |

---

**Дата:** 2026-01-03  
**Версия:** x0tta6bl4 v3.4  
**Статус:** ✅ **DOCUMENTED** | ⚠️ **IMPLEMENTATION IN PROGRESS**


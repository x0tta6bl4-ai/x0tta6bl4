# 📦 Installation Guide - x0tta6bl4 v3.4

**Дата:** 2026-01-03  
**Версия:** x0tta6bl4 v3.4

---

## 🚀 Быстрый Старт

### Минимальная Установка (Core Only)

```bash
# 1. Клонировать репозиторий
git clone <repository-url>
cd x0tta6bl4

# 2. Установить core dependencies
pip install -r requirements-core.txt

# 3. Запустить (в development mode)
python3 -m src.core.app
```

### Полная Установка (С Optional Dependencies)

```bash
# 1. Установить core dependencies
pip install -r requirements-core.txt

# 2. Установить optional dependencies
pip install -r requirements-optional.txt

# 3. Для production - установить production dependencies
export X0TTA6BL4_PRODUCTION=true
pip install -r requirements-production.txt
```

---

## 📋 Структура Dependencies

### requirements-core.txt
**Обязательные зависимости** - система не запустится без них.

Включает:
- FastAPI, uvicorn (web framework)
- cryptography (базовая криптография)
- redis (кэширование)
- numpy, psutil (утилиты)

### requirements-production.txt
**Требуемые в production mode** (`X0TTA6BL4_PRODUCTION=true`).

Включает:
- `liboqs-python` - Post-Quantum Cryptography (MANDATORY)
- `py-spiffe` - Zero Trust Identity (RECOMMENDED)

**⚠️ ВАЖНО:** В production mode система **НЕ ЗАПУСТИТСЯ** без `liboqs-python`.

### requirements-optional.txt
**Опциональные зависимости** - система работает без них в graceful degradation mode.

Включает:
- `torch`, `sentence-transformers`, `hnswlib` - ML/AI features
- `opentelemetry` - Distributed tracing
- `web3`, `ipfshttpclient` - Blockchain features
- `prometheus-client` - Metrics
- `flwr` - Federated Learning

---

## 🔍 Проверка Установки

### Health Check

```bash
# Запустить health check script
python3 scripts/check_dependencies.py

# Или через API (если сервер запущен)
curl http://localhost:8000/health/dependencies
```

### Проверка Критических Зависимостей

```bash
# Проверить liboqs (required in production)
python3 -c "from oqs import KeyEncapsulation; print('✅ liboqs available')"

# Проверить SPIFFE (recommended)
python3 -c "import spiffe; print('✅ SPIFFE available')"

# Проверить torch (optional)
python3 -c "import torch; print('✅ torch available')"
```

---

## 🐳 Docker Installation

### Development

```bash
docker build -t x0tta6bl4:dev -f Dockerfile .
docker run -p 8000:8000 x0tta6bl4:dev
```

### Production

```bash
docker build -t x0tta6bl4:prod -f Dockerfile --build-arg PRODUCTION=true .
docker run -p 8000:8000 -e X0TTA6BL4_PRODUCTION=true x0tta6bl4:prod
```

---

## ☸️ Kubernetes Installation

### Prerequisites

- Kubernetes cluster (1.20+)
- kubectl configured
- Helm 3.x

### Installation

```bash
# 1. Install core dependencies
helm install x0tta6bl4 ./helm/x0tta6bl4 \
  --set production.enabled=true \
  --set dependencies.liboqs=true \
  --set dependencies.spiffe=true

# 2. Check status
kubectl get pods -l app=x0tta6bl4
kubectl get svc x0tta6bl4
```

---

## 🔧 Environment Variables

### Required

```bash
X0TTA6BL4_VERSION=3.4.0
```

### Production Mode

```bash
X0TTA6BL4_PRODUCTION=true  # Enables strict dependency checks
```

### Optional

```bash
ENVIRONMENT=production  # or staging, development
LOG_LEVEL=INFO
```

---

## ⚠️ Troubleshooting

### liboqs-python Installation Issues

```bash
# On Ubuntu/Debian
sudo apt-get install build-essential cmake libssl-dev
pip install liboqs-python

# On macOS
brew install cmake openssl
pip install liboqs-python
```

### SPIFFE/SPIRE Issues

```bash
# Ensure SPIRE Server is running
# Check SPIRE Agent status
spire-agent healthcheck
```

### eBPF Issues

```bash
# Check kernel support
uname -r  # Should be 4.18+
ls /sys/fs/bpf  # Should exist

# Check bpftool
bpftool version
```

---

## 📊 Dependency Status

После установки проверьте статус зависимостей:

```bash
# Health check
python3 scripts/check_dependencies.py

# Expected output:
# {
#   "overall_status": "healthy",
#   "dependencies": {
#     "liboqs": {"status": "available", ...},
#     "spiffe": {"status": "available", ...},
#     ...
#   }
# }
```

---

## 🎯 Next Steps

После установки:

1. ✅ Проверьте health: `curl http://localhost:8000/health`
2. ✅ Проверьте dependencies: `curl http://localhost:8000/health/dependencies`
3. 📖 Прочитайте [PRODUCTION_READINESS_CHECKLIST.md](PRODUCTION_READINESS_CHECKLIST.md)
4. 🚀 Начните с [AUDIT_INTEGRATION_PLAN.md](AUDIT_INTEGRATION_PLAN.md)

---

**Дата:** 2026-01-03  
**Версия:** x0tta6bl4 v3.4


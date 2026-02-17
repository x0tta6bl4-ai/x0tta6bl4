# x0tta6bl4

[![CI](https://github.com/x0tta6bl4/x0tta6bl4/actions/workflows/ci.yml/badge.svg)](https://github.com/x0tta6bl4/x0tta6bl4/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-71.15%25-green)](./tests/)
[![Security](https://img.shields.io/badge/security-0%20CVE-brightgreen)]()
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/)
[![PQC](https://img.shields.io/badge/PQC-NIST%20FIPS%20203%2F204-green)]()

**Self-Healing Mesh Network** с MAPE-K архитектурой, постквантовой криптографией и Zero Trust идентификацией.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     x0tta6bl4 Self-Healing Mesh Network                     │
│                                                                             │
│   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐    │
│   │  MAPE-K     │   │    PQC      │   │   eBPF      │   │  SPIFFE/    │    │
│   │ Self-Healing│   │  ML-KEM/DSA │   │    XDP      │   │   SPIRE     │    │
│   │   (MTTR<3m) │   │ (NIST FIPS) │   │ SipHash MAC │   │ Zero Trust  │    │
│   └──────┬──────┘   └──────┬──────┘   └──────┬──────┘   └──────┬──────┘    │
│          │                 │                 │                 │            │
│          └─────────────────┴─────────────────┴─────────────────┘            │
│                                     │                                       │
│                    ┌────────────────┴────────────────┐                      │
│                    │      ConsciousnessEngine        │                      │
│                    │   (GraphSAGE + LocalLLM)        │                      │
│                    └────────────────┬────────────────┘                      │
│                                     │                                       │
│                    ┌────────────────┴────────────────┐                      │
│                    │         CRDT Layer               │                      │
│                    │  LWWRegister, ORSet, GCounter    │                      │
│                    └─────────────────────────────────┘                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 🎯 Ключевые возможности

| Компонент | Описание | Статус |
|-----------|----------|--------|
| 🧠 **MAPE-K Loop** | Self-healing архитектура: Monitor → Analyze → Plan → Execute → Knowledge | ✅ Production |
| 🔐 **PQC Crypto** | ML-KEM-768 + ML-DSA-65 (NIST FIPS 203/204) + AES-256-GCM | ✅ Production |
| ⚡ **eBPF XDP** | Kernel-space packet processing, SipHash-2-4 MAC verification | ✅ Production |
| 🆔 **SPIFFE/SPIRE** | Zero Trust идентификация workloads, mTLS | ✅ Production |
| 🔄 **CRDT** | Conflict-free Replicated Data Types: LWWRegister, ORSet, LWWMap, GCounter, PNCounter | ✅ Production |
| 🤖 **ConsciousnessEngine** | GraphSAGE anomaly detection + LocalLLM decision making | ✅ Active |
| 🌐 **Mesh Network** | Yggdrasil-based децентрализованная сеть | ✅ Production |
| 🏛️ **DAO Governance** | Quadratic voting, децентрализованное управление | ✅ Production |

## 📊 Метрики качества

| Метрика | Значение | Цель |
|---------|----------|------|
| Test Coverage | **71.15%** | >70% ✅ |
| CVE Vulnerabilities | **0** | 0 ✅ |
| Hardcoded Secrets | **0** | 0 ✅ |
| MTTR (Mean Time To Recovery) | **<3 min** | <3.14 min ✅ |

## 🚀 Quick Start

### Требования

- Python 3.12+
- Linux kernel 5.10+ (для eBPF XDP)
- Docker & Docker Compose (опционально)
- liboqs (для PQC)

### Установка

```bash
# Клонировать репозиторий
git clone https://github.com/x0tta6bl4/x0tta6bl4.git
cd x0tta6bl4

# Создать виртуальное окружение
python3 -m venv .venv
source .venv/bin/activate

# Установить зависимости
pip install -r requirements.txt

# Установить pre-commit hooks
pre-commit install
```

### Запуск

```bash
# Запуск API сервера
uvicorn src.core.app:app --host 0.0.0.0 --port 8080 --reload

# Или с Docker Compose (включая SPIRE)
docker-compose up -d

# Проверка здоровья
curl http://localhost:8080/health
```

### Инициализация PQC ключей

```python
from src.security.pqc import PQCKeyExchange, PQCDigitalSignature, is_liboqs_available

# Проверка доступности liboqs
if is_liboqs_available():
    # Key Encapsulation (ML-KEM-768)
    kem = PQCKeyExchange()
    keypair = kem.generate_keypair()
    ciphertext, shared_secret = kem.encapsulate(keypair.public_key)
    
    # Digital Signatures (ML-DSA-65)
    dsa = PQCDigitalSignature()
    sig_keypair = dsa.generate_keypair()
    signature = dsa.sign(b"message", sig_keypair.secret_key)
```

### Использование CRDT

```python
from src.data_sync.crdt import LWWRegister, ORSet, GCounter, PNCounter, LWWMap

# LWW Register (Last-Writer-Wins)
register = LWWRegister(node_id="node-1", value="initial")
register.set("new value", "node-1")

# OR-Set (Observed-Remove Set)
orset = ORSet()
orset.add("element-1", "node-1")
orset.add("element-2", "node-2")
orset.remove("element-1")

# G-Counter (Grow-only Counter)
gcounter = GCounter()
gcounter.increment("node-1", 5)
gcounter.increment("node-2", 3)
print(f"Total: {gcounter.value()}")  # 8

# PN-Counter (Positive-Negative Counter)
pncounter = PNCounter()
pncounter.increment("node-1", 10)
pncounter.decrement("node-1", 3)
print(f"Value: {pncounter.value()}")  # 7
```

## 🏗️ Архитектура

### MAPE-K Self-Healing Loop

```
┌─────────────────────────────────────────────────────────────────┐
│                      MAPE-K Loop                                │
│                                                                 │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐ │
│   │ MONITOR  │───►│ ANALYZE  │───►│   PLAN   │───►│ EXECUTE  │ │
│   │          │    │          │    │          │    │          │ │
│   │ Metrics  │    │ GraphSAGE│    │ Directives│   │ Actions  │ │
│   │ eBPF     │    │ Anomaly  │    │ Healing  │    │ Recovery │ │
│   │ Mesh     │    │ Detect   │    │ Scaling  │    │ Isolate  │ │
│   └──────────┘    └──────────┘    └──────────┘    └──────────┘ │
│         ▲                                            │         │
│         └────────────────────────────────────────────┘         │
│                          KNOWLEDGE                             │
│                    (Learning & History)                        │
└─────────────────────────────────────────────────────────────────┘
```

### ConsciousnessEngine States

| State | φ-ratio | Поведение системы |
|-------|---------|-------------------|
| EUPHORIC | > 1.4 | Peak performance, proactive optimization |
| HARMONIC | > 1.0 | Stable operation, normal monitoring |
| CONTEMPLATIVE | > 0.8 | Degraded, increased monitoring |
| MYSTICAL | < 0.8 | Critical, emergency self-healing |

### PQC Cryptography Stack

```
┌─────────────────────────────────────────────────────────────────┐
│                    PQC Cryptography                             │
│                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │   ML-KEM-768    │  │   ML-DSA-65     │  │   AES-256-GCM   │ │
│  │  (Key Encap.)   │  │  (Signatures)   │  │  (Symmetric)    │ │
│  │  NIST FIPS 203  │  │  NIST FIPS 204  │  │                 │ │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘ │
│           │                    │                    │          │
│           └────────────────────┴────────────────────┘          │
│                              │                                  │
│                    ┌─────────┴─────────┐                       │
│                    │   Hybrid Schemes  │                       │
│                    │ X25519+ML-KEM     │                       │
│                    │ Ed25519+ML-DSA    │                       │
│                    └───────────────────┘                       │
└─────────────────────────────────────────────────────────────────┘
```

## 📁 Структура проекта

```
x0tta6bl4/
├── src/
│   ├── core/                    # Ядро системы
│   │   ├── mape_k_loop.py       # MAPE-K self-healing loop
│   │   ├── consciousness.py     # ConsciousnessEngine
│   │   └── app.py               # FastAPI application
│   ├── security/
│   │   ├── pqc/                 # Post-Quantum Cryptography
│   │   │   ├── kem.py           # ML-KEM-768
│   │   │   ├── dsa.py           # ML-DSA-65
│   │   │   └── hybrid.py        # Hybrid schemes
│   │   ├── spiffe/              # SPIFFE/SPIRE integration
│   │   └── zero_trust/          # Zero Trust validation
│   ├── network/
│   │   ├── ebpf/                # eBPF XDP programs
│   │   │   ├── pqc_xdp_loader.py
│   │   │   └── telemetry/
│   │   └── routing/             # Mesh routing
│   ├── data_sync/
│   │   ├── crdt.py              # CRDT implementations
│   │   └── crdt_sync.py         # Synchronization
│   ├── self_healing/            # Self-healing components
│   ├── mesh/                    # Mesh network
│   └── dao/                     # DAO governance
├── docs/                        # Документация
├── tests/                       # Тесты (71.15% coverage)
├── helm/                        # Kubernetes Helm charts
├── docker/                      # Docker configurations
└── monitoring/                  # Prometheus/Grafana
```

## 📚 Документация

| Документ | Описание |
|----------|----------|
| [START_HERE.md](START_HERE.md) | Единая точка входа |
| [docs/](docs/) | Полная документация |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Как внести вклад |
| [SECURITY.md](SECURITY.md) | Политика безопасности |
| [CHANGELOG.md](CHANGELOG.md) | История изменений |

## 🛡️ Безопасность

### Security Features

- **Post-Quantum Cryptography**: Защита от квантовых атак (ML-KEM-768, ML-DSA-65)
- **Zero Trust Architecture**: SPIFFE/SPIRE идентификация всех workloads
- **eBPF XDP Firewall**: Kernel-space packet filtering с SipHash-2-4 MAC
- **mTLS**: Mutual TLS для всех внутренних соединений
- **No Hardcoded Secrets**: 0 hardcoded secrets (проверено detect-secrets)

### Сообщение об уязвимостях

См. [SECURITY.md](SECURITY.md) для информации о том, как сообщать об уязвимостях.

## 🧪 Тестирование

```bash
# Запуск всех тестов
pytest tests/ -v

# С покрытием
pytest tests/ --cov=src --cov-report=html

# Mutation testing
mutmut run

# eBPF tests (требует root)
sudo pytest tests/ebpf/ -v
```

## 📊 Мониторинг

```bash
# Prometheus
open http://localhost:9090

# Grafana
open http://localhost:3000

# Health check
curl http://localhost:8080/health
```

## 🤝 Contributing

Мы приветствуем вклад! См. [CONTRIBUTING.md](CONTRIBUTING.md) для:
- Code style guidelines
- Процесса Pull Request
- Тестирования
- Code of Conduct

## 📄 Лицензия

Apache License 2.0 — см. [LICENSE](LICENSE) файл.

## 🔗 Ссылки

- **Документация:** https://docs.x0tta6bl4.net
- **SPIFFE/SPIRE:** https://spiffe.io
- **NIST PQC:** https://csrc.nist.gov/projects/post-quantum-cryptography

---

**⚠️ Важно:** Это экспериментальное ПО для исследовательских целей. Используйте на свой страх и риск.

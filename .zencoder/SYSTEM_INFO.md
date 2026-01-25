# System Information & Disk Analysis

**Дата анализа**: January 14, 2026, 00:54 UTC+1  
**ОС**: Linux 6.14.0-37-generic (Ubuntu)  
**Рабочая директория**: `/mnt/AC74CC2974CBF3DC`

## Дисковое пространство

### Основные Диски

| Диск | Размер | Используется | Доступно | Использование % | Точка монтирования |
|------|--------|--------------|----------|-----------------|-------------------|
| **`/dev/sdb1`** | 466 GB | 220 GB | 247 GB | 48% | `/mnt/AC74CC2974CBF3DC` ⭐ |
| **`/dev/mapper/ubuntu--vg-ubuntu--lv`** | 107 GB | 90 GB | 12 GB | 89% | `/` (System) ⚠️ |
| **`/dev/sda2`** | 2.0 GB | 98 MB | 1.7 GB | 6% | `/boot` |
| **`/dev/sda1`** | 1.1 GB | 6.2 MB | 1.1 GB | 1% | `/boot/efi` |

### Статус

- ✅ **Основной диск проекта** (`/dev/sdb1`): 247 GB свободного пространства (48% использования) – **достаточно**
- ⚠️ **Системный диск** (`/`): 12 GB свободного (89% использования) – **критично, требуется очистка**
- ✅ **Память RAM**: 6.8 GB доступно в `/dev/shm`

### Рекомендации по дискам

1. **СРОЧНО**: Освободить ~20-30 GB на системном диске `/`
   - Удалить неиспользуемые Docker образы: `docker system prune -a --volumes`
   - Очистить кэш пакетов: `apt-get clean && apt-get autoclean`
   - Проверить `/tmp` и `/var/log`

2. **Проект диск** (`/dev/sdb1`): Хороший статус, мониторить
   - Динамично растёт (ML модели, embeddings, данные)
   - Рекомендуется архивирование старых артефактов

## Проект x0tta6bl4 - Обзор

### Статус Проекта

- **Версия**: 3.3.0 (Python), 1.0.0 (Smart Contracts)
- **Язык**: Python 3.10+ (основной), Solidity 0.8.20 (контракты), Node.js (Hardhat)
- **Статус разработки**: Integration Phase (60% production-ready)
- **Тесты**: 96% pass rate (97/101), coverage ≥75%

### Основные компоненты

✅ **Завершены**:
- MAPE-K Self-Healing Loop (M→A→P→E→K)
- Post-Quantum Cryptography (NIST ML-KEM-768/ML-DSA-65 via liboqs)
- eBPF Networking & XDP programs
- Batman-adv Mesh Network
- Federated Learning (FL coordinator + Byzantine-robust aggregators)
- DAO Governance (quadratic voting, token bridge)
- Web Security (bcrypt, XSS protection, CORS hardening)

🔴 **Критичные TODO (P0)** – блокируют production:
- SPIFFE/SPIRE integration (identity fabric)
- mTLS validation (TLS 1.3, SVID verification)
- eBPF CI/CD compilation (.c → .o pipeline)
- Staging Kubernetes deployment
- Security scanning in CI (bandit, safety)

⚙️ **Partial** – нужна доработка:
- GraphSAGE anomaly detection (prototype, integration needed)
- RAG pipeline (basic impl, HNSW optimization)
- LoRA fine-tuning (adapter scaffold, training loop)

### Ключевые файлы

- **`pyproject.toml`**: Python dependencies, pytest config, version 3.3.0
- **`Dockerfile`**: Multi-stage build, liboqs v0.10.0, Python 3.11-slim
- **`Makefile`**: 50+ команд для development, testing, deployment
- **`docker-compose.quick.yml`**: Staging stack (API, DB, Redis, Prometheus, Grafana)
- **`src/core/app.py`**: Main FastAPI application (1362 lines)
- **`src/self_healing/mape_k.py`**: MAPE-K autonomic loop

### Зависимости (41 основные)

**Фреймворк**: fastapi, uvicorn, pydantic, starlette  
**Security**: cryptography, liboqs-python, bcrypt, spiffe  
**ML/AI**: torch, torch-geometric, transformers, sentence-transformers  
**Networking**: aiohttp, asyncio-mqtt, networkx  
**Observability**: prometheus-client, opentelemetry-*  
**Other**: redis, web3, aioipfs, bcc (eBPF), flwr (FL)

### Commands для быстрого старта

```bash
# Установка
pip install -e ".[all]"           # Все зависимости
make install                       # Via Makefile

# Тестирование
make test                          # Health checks
pytest tests/ -v                   # Run all tests
pytest -m unit                     # Unit tests only

# Development
make up                            # Start staging stack
make logs                          # Follow API logs
make format                        # Code formatting

# Docker
docker compose -f staging/docker-compose.quick.yml up  # Full stack

# API
python -m src.core.app             # Run production
uvicorn src.core.app:app --reload  # Dev mode
```

## Структура проекта в `/mnt/AC74CC2974CBF3DC`

```
.
├── src/                    # 40+ Python modules (30,000+ LOC)
│   ├── core/               # FastAPI app, health checks
│   ├── self_healing/       # MAPE-K loop
│   ├── security/           # SPIFFE, mTLS, PQC, Zero-Trust
│   ├── network/            # Batman-adv, eBPF, mesh topology
│   ├── ml/                 # GraphSAGE, RAG, LoRA
│   ├── dao/                # DAO contracts, governance
│   ├── federated_learning/ # FL coordinator
│   └── monitoring/         # Prometheus, OpenTelemetry
├── tests/                  # 50+ test files (unit, integration, security, chaos)
├── docs/                   # 50+ documentation files
├── deploy/                 # Deployment scripts, docker-compose configs
├── infra/                  # Kubernetes, Helm, Terraform manifests
├── pyproject.toml          # Python dependencies, pytest config
├── Dockerfile              # Multi-stage production build
├── Makefile                # Development commands
└── .zencoder/              # Zencoder rules and analysis
    ├── repo.md             # Repository information (THIS FILE)
    ├── language-preference.md
    └── technical-debt-analysis.md
```

## Development Workflow

### Linting & Testing
```bash
flake8 src/ --max-line-length=120
mypy src/ --ignore-missing-imports
black src/                    # Format code
pytest tests/ --cov=src       # Run with coverage (≥75% enforced)
```

### Building & Deployment
```bash
# Local development
pip install -e ".[dev,ml,monitoring]"
python -m src.core.app

# Docker staging
docker compose -f staging/docker-compose.quick.yml up

# Production
docker build -f Dockerfile.prod -t x0tta6bl4:latest .

# Kubernetes
make k8s-staging              # Setup K3s/minikube
kubectl apply -k infra/k8s/overlays/staging/
```

### Smart Contracts
```bash
cd src/dao/contracts
npm install
npm run compile              # Hardhat 2.19.0
npm run test
npm run deploy:polygon       # Deploy to Polygon mainnet
```

## Critical Notes

⚠️ **System disk full**: Системный диск 89% заполнен, требуется срочная очистка  
⚠️ **P0 blockers**: SPIFFE/SPIRE, mTLS, eBPF CI/CD – блокируют production  
✅ **Test coverage**: 96% pass rate, solid quality  
✅ **Documentation**: Comprehensive (50+ files)  
✅ **Code organization**: Domain-driven, well-structured  

## Timeline

- **Текущий статус**: 60% production-ready
- **Target**: Jan 31, 2026 – P0 tasks completion
- **Deployment**: Post-P0 completion (Feb 2026)

---

**Дата обновления**: January 14, 2026  
**Источник**: Automated repository analysis via Zencoder


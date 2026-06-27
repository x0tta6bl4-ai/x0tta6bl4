# x0tta6bl4 🔐 Quantum-Resistant Mesh VPN

[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![CodeQL](https://img.shields.io/badge/CodeQL-0%20alerts-brightgreen)](.github/workflows/codeql.yml)
![Status](https://img.shields.io/badge/status-production--ready-green)
![PQC](https://img.shields.io/badge/PQC-ML--KEM--768-blue)
![ZTCR](https://img.shields.io/badge/ZTCR-29%2F29%20tests-brightgreen)
![CVEs](https://img.shields.io/badge/CVEs-20%20patched-brightgreen)

**Post-quantum cryptography · eBPF/XDP dataplane · Autonomous self-healing**
Independent engineering project by [x0tta6bl4](https://github.com/x0tta6bl4-ai).
*AI-assisted: see [AI-DECLARATION.md](AI-DECLARATION.md) and [system prompts](/.prompts/).*

---

## Infrastructure (Live)

| Component | Location | Status | Notes |
|-----------|----------|--------|-------|
| **NL VPS** (89.125.1.107) | Netherlands | ✅ Production | SPIRE, mesh-node x2, Ghost VPN, x-ui |
| **Docker Compose** | Local | ✅ Running | mesh-node-a/b + bridge → NL |
| **k3d K8s Cluster** | Local | ✅ Running | 3 nodes (k3s v1.31.5), mesh consensus |
| **SPIRE Server** | NL + Docker | ✅ Active | Trust domain: x0tta6bl4.mesh |
| **Health Monitor** | Cronjob | ✅ Every 5min | 10 services + 2 mesh nodes checked |
| **CVE Monitor** | Cronjob | ✅ Daily 6:00 | Dependabot tracking, auto-patch |
| **GitMark RAG** | Cronjob | ✅ Daily 5:00 | Codebase knowledge base rebuild |

### Mesh Network Topology

```
k3d K8s (localhost)
  └─ mesh-k8s-1 ↔ mesh-k8s-2 ↔ mesh-k8s-3

Docker (localhost)
  └─ node-a ↔ node-b ↔ bridge → NL:9100

NL VPS (89.125.1.107)
  └─ spire-server → nl-node-1 ↔ nl-node-2
```

---

## Security

| Check | Status |
|-------|--------|
| **Subprocess safety** | ✅ `safe_run` — 54 allowed commands |
| **Bandit scan** | ✅ 0 HIGH, 0 CRITICAL |
| **CodeQL** | ✅ 0 open alerts |
| **Dependabot** | ✅ Auto-patching, 33 alerts remaining |
| **CVEs patched** | ✅ 20 (yt-dlp, starlette, PyJWT, python-multipart, cryptography) |
| **ZTCR** | ✅ 29/29 chaos tests passed |
| **SPIRE mTLS** | ✅ Production on NL VPS |

---

## Components

| Component | Lines | Description |
|-----------|-------|-------------|
| Post-Quantum Crypto | ~3,500 | ML-KEM-768 + ML-DSA-65 via liboqs, hybrid TLS 1.3 |
| MAPE-K Self-Healing | ~1,900 | Full loop: Monitor → Analyze → Plan → Execute → Knowledge |
| MaaS API | ~5,000 | FastAPI REST API, 46 route handlers |
| Anti-Censorship | ~2,000 | 6 mechanisms: Ghost Protocol, Geneva, StegoMesh |
| eBPF/XDP | ~1,500 | Kernel-level packet processing |
| Ghost Transport | ~2,000 | Experimental VPN, Docker-ready |
| ML Stack | ~1,000 | micro_tensor, MeshGNN, LoRA (pure NumPy) |
| Swarm | ~1,500 | PBFT consensus, AnomalyConsensusManager |
| **AI Skills** | ~40 | 40 Hermes skills for automation |

> **Total:** ~805K+ lines Python, 1,300 lines Go

### Benchmarks (r8169 NIC, Intel i5)

| Metric | Value | Conditions |
|--------|-------|------------|
| XDP TX | 142,000 PPS | pktgen → XDP_TX |
| XDP RX | 49,000 PPS | XDP_DROP raw |
| PQC Handshake | <50 ms | ML-KEM-768 + ML-DSA-65 |
| MAPE-K MTTD | <20 s | Actual detection |
| MAPE-K MTTR | ~3 min | Autonomous recovery |

---

## Honest Assessment

**What this is:** Full-stack DePIN platform demonstrating systems engineering across cryptography, kernel networking, distributed systems, and DevOps automation. 805K+ lines, 2,288+ commits, solo developer with AI agents.

**What this is NOT:**

| Claim | Status |
|-------|--------|
| 99.97% uptime SLA | ❌ No evidence |
| 1M PPS throughput | ❌ 142k PPS on consumer hardware |
| Formally audited crypto | ❌ liboqs integration, no formal audit |
| DAO / community | ❌ Solo project |
| Commercial service | ❌ Research project |

---

## Quick Start

```bash
git clone https://github.com/x0tta6bl4-ai/x0tta6bl4.git
cd x0tta6bl4
uv sync
```

### Local mesh (Docker)

```bash
docker compose -f deploy/docker-compose/compose.yaml up -d
curl -s http://localhost:9100/health
```

### Kubernetes (k3d)

```bash
k3d cluster create x0tta6bl4 --agents 2
kubectl apply -f k8s/mesh/
```

### Run tests

```bash
python3 -m pytest tests/unit/self_healing/ -v
python3 scripts/benchmark_pqc.py
```

---

## Skills (40 AI-automation skills)

| Category | Count | Examples |
|----------|:-----:|----------|
| Architecture & Analysis | 6 | depin-architecture, loop-designer |
| Code Quality & Tech Debt | 8 | tech-debt-elimination, git-hygiene |
| Infrastructure & Deploy | 8 | remote-deploy, mesh-local-deploy |
| ML/AI | 2 | mesh-gnn, depin-architecture |
| Job Search & Visibility | 5 | job-search-strategy, honest-audit |
| Meta & Automation | 3 | loop-designer, context-saver |

---

## Technologies

**Languages:** Python 3.12, Go, Solidity, eBPF/C
**Crypto:** liboqs, ML-KEM-768, ML-DSA-65, SPIRE/SPIFFE
**Networking:** eBPF/XDP, AF_XDP, WireGuard, Yggdrasil IPv6
**Infrastructure:** Docker, Kubernetes (k3d), SPIRE, FastAPI
**Security:** CodeQL, Dependabot, Bandit, ZTCR chaos testing

---

## Contact

- Issues: [GitHub Issues](https://github.com/x0tta6bl4-ai/x0tta6bl4/issues)
- Telegram: [@x0tta6bl4_ai](https://t.me/x0tta6bl4_ai)
- Email: x0tta6bl4.ai@gmail.com

---

## x0tta6bl4 — Пост-квантовая self-healing mesh-сеть

### О проекте

x0tta6bl4 — платформа для mesh-сетей с постквантовой криптографией (ML-KEM-768 / ML-DSA-65 через liboqs), eBPF/XDP dataplane и автономным самовосстановлением MAPE-K. Разрабатывается с 2025 года одним человеком с AI-агентами.

### Инфраструктура (работает)

| Компонент | Расположение | Статус |
|-----------|-------------|--------|
| **NL VPS** (89.125.1.107) | Нидерланды | ✅ Production |
| **Docker Compose** | Локально | ✅ Running |
| **K8s (k3d)** | Локально | ✅ Running |
| **SPIRE** | NL + Docker | ✅ Active |
| **Health Monitor** | Cronjob | ✅ Каждые 5 минут |
| **CVE Monitor** | Cronjob | ✅ Ежедневно |

### Mesh-сеть

```
k3d K8s → mesh-k8s-1 ↔ mesh-k8s-2 ↔ mesh-k8s-3
Docker   → node-a ↔ node-b ↔ bridge → NL:9100
NL VPS   → spire-server → nl-node-1 ↔ nl-node-2
```

### Безопасность

- 20 CVE исправлено
- 29/29 chaos-тестов пройдено
- 54 команды в allowlist
- SPIRE mTLS на production
- Health monitoring каждые 5 минут

### Контакты

- Telegram: [@x0tta6bl4_ai](https://t.me/x0tta6bl4_ai)
- Email: x0tta6bl4.ai@gmail.com

*Independent engineering project. Verified by machines, not marketing.*

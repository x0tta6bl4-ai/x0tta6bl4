# x0tta6bl4 — Self-Healing Mesh Networking Platform

[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![CodeQL](https://img.shields.io/badge/CodeQL-0%20alerts-brightgreen)](.github/workflows/codeql.yml)
![Status](https://img.shields.io/badge/status-experimental-yellow)

**Post-quantum cryptography · eBPF/XDP kernel dataplane · Autonomous self-healing**  
Independent engineering project by [x0tta6bl4](https://github.com/x0tta6bl4-ai).  
*AI-assisted: see [AI-DECLARATION.md](AI-DECLARATION.md).*

---

## About

x0tta6bl4 is a mesh networking platform with post-quantum cryptography (ML-KEM/ML-DSA via liboqs), eBPF/XDP dataplane, and MAPE-K self-healing. Built since 2025 by a solo developer with AI agents in spare time.

---

## Implemented Components

| Component | Lines | Description |
|-----------|-------|-------------|
| Post-Quantum Crypto (PQC) | ~3,500 | ML-KEM-768/1024 + ML-DSA-65/87 via liboqs, hybrid TLS 1.3, SPIRE/SPIFFE mTLS |
| MAPE-K Self-Healing | ~1,900 | Full control loop (Monitor → Analyze → Plan → Execute → Knowledge) |
| MaaS API | ~5,000 | Mesh-as-a-Service REST API, FastAPI, 46 route handlers |
| Anti-Censorship | ~2,000 | DPI bypass, traffic obfuscation, protocol camouflage |
| eBPF/XDP Dataplane | ~1,500 | Kernel-level packet processing, AF_XDP ring buffers |
| Ghost Transport (VPN) | ~2,000 | Experimental STL-encapsulated transport, Docker-ready |
| Billing & Access Control | ~1,200 | Subscription tiers, token-gated access, usage metering |

> **Total source:** ~357,000 lines of Python (excluding comments and blanks), 1,300 lines Go.

### Benchmarks (r8169 NIC, Intel i5)

| Metric | Value | Conditions |
|--------|-------|------------|
| XDP TX Throughput | 142,000 PPS | pktgen → XDP_TX |
| XDP RX Throughput | 49,000 PPS | XDP_DROP raw |
| PQC Handshake | <50 ms | ML-KEM-768 + ML-DSA-65, localhost |
| MAPE-K MTTD | <20 s | Actual detection time |
| MAPE-K MTTR | ~3 min | Autonomous recovery |
| Dependencies | 72 (was 342) | After cleanup |

---

## Honest Assessment

**What this is:** An independent research project demonstrating full-stack systems engineering — cryptographic integration, kernel networking, distributed systems, DevOps automation. The code compiles and tests pass.

**What this is NOT:**

| Claim | Status |
|-------|--------|
| 99.97% uptime SLA | ❌ No evidence |
| 1M PPS throughput | ❌ 142k PPS on consumer hardware |
| Formally audited cryptography | ❌ liboqs integration, no audit |
| DAO / community governance | ❌ Solo project |
| Official commercial service | ❌ Experimental research project |
| Production deployment | ❌ Retired 2026-06 |

---

## Quick Start

```bash
git clone https://github.com/x0tta6bl4-ai/x0tta6bl4.git
cd x0tta6bl4
uv sync
```

### Local stack (Docker)
```bash
docker compose up ghost-vpn-server ghost-vpn-redis -d
docker compose up mesh-node-a mesh-node-b -d
```

### Run tests
```bash
python3 -m pytest tests/unit/consensus/ -q --no-cov
python3 -m pytest tests/unit/security/ -q --no-cov
```

### Want to collaborate?
Reach out directly — see [CONTRIBUTING.md](CONTRIBUTING.md) for contact details and current needs.

---

## Contact

- Issues: [GitHub Issues](https://github.com/x0tta6bl4-ai/x0tta6bl4/issues)
- Telegram: [@x0tta6bl4_ai](https://t.me/x0tta6bl4_ai)
- Email: x0tta6bl4.ai@gmail.com

---

---

# x0tta6bl4 — Само-восстанавливающаяся mesh-сеть

[![Лицензия](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![CodeQL](https://img.shields.io/badge/CodeQL-0%20alerts-brightgreen)](.github/workflows/codeql.yml)

---

## О проекте

x0tta6bl4 — платформа для mesh-сетей с постквантовой криптографией (ML-KEM/ML-DSA через liboqs), eBPF/XDP dataplane и автономным самовосстановлением MAPE-K. Разрабатывается с 2025 года одним человеком с AI-агентами в свободное время.

---

## Реализованные компоненты

| Компонент | Строк | Описание |
|-----------|-------|----------|
| PQC | ~3,500 | ML-KEM-768/1024 + ML-DSA-65/87 через liboqs, гибридный TLS 1.3 |
| MAPE-K | ~1,900 | Полный цикл: мониторинг → анализ → план → восстановление |
| MaaS API | ~5,000 | REST API для управления mesh-узлами, FastAPI |
| eBPF/XDP | ~1,500 | Обработка пакетов на уровне ядра Linux |
| Ghost Transport | ~2,000 | Экспериментальный транспорт, Docker-ready |

## Быстрый старт

```bash
git clone https://github.com/x0tta6bl4-ai/x0tta6bl4.git
cd x0tta6bl4
uv sync
```

### Локальный запуск (Docker)
```bash
docker compose up ghost-vpn-server ghost-vpn-redis -d
docker compose up mesh-node-a mesh-node-b -d
```

---

## Контакты

- Issues: баги и предложения
- Telegram: [@x0tta6bl4_ai](https://t.me/x0tta6bl4_ai)
- Email: x0tta6bl4.ai@gmail.com

---

*Independent engineering project. Verified by machines, not marketing.*
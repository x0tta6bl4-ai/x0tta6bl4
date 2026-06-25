# x0tta6bl4 — Self-Healing Mesh Networking Platform

[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![CodeQL](https://img.shields.io/badge/CodeQL-0%20alerts-brightgreen)](.github/workflows/codeql.yml)
![Status](https://img.shields.io/badge/status-experimental-yellow)

**Post-quantum cryptography · eBPF/XDP kernel dataplane · Autonomous self-healing**  
Independent engineering project by [x0tta6bl4](https://github.com/x0tta6bl4-ai).  
*AI-assisted: see [AI-DECLARATION.md](AI-DECLARATION.md).*

---

## About

Built since early 2025 by a solo developer in Crimea — a sanctions-restricted region with no access to Stripe, AWS, Google Play, or international payment systems. Zero budget. Zero grants. Zero investors.

This is not a startup. It's a survival infrastructure project.

Every component — post-quantum cryptography (ML-KEM/ML-DSA via liboqs), eBPF/XDP kernel dataplane, autonomous MAPE-K self-healing loop — exists because conventional infrastructure (cloud, certificates, payment gateways) is either blocked or unaffordable. The only payment method available is USDC on Base mainnet.

~357,000 lines of Python, 1.5 years, one person.

**What works today:** PQC stack (ML-KEM-768/1024 + ML-DSA-65/87), MAPE-K control loop, Raft consensus (36/36 tests), Ghost-VPN transport (Docker, healthy), eBPF programs (previously attached, benchmarks documented).

**What doesn't yet:** Production deployment (previous VPS retired), MaaS API behind a live endpoint, DAO/token circulation.

Target audience: people in restricted regions who need mesh networking that doesn't depend on corporate cloud providers, bank cards, or government permission.

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
- Telegram: [@x0tta6bl4](https://t.me/x0tta6bl4)
- Email: x0tta6bl4.ai@gmail.com

---

---

# x0tta6bl4 — Само-восстанавливающаяся mesh-сеть

[![Лицензия](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![CodeQL](https://img.shields.io/badge/CodeQL-0%20alerts-brightgreen)](.github/workflows/codeql.yml)

---

## О проекте

Разрабатывается с начала 2025 года одним человеком в Крыму — регион под санкциями, где нет доступа к Stripe, AWS, Google Play и международным платёжным системам. Zero budget. Никаких грантов. Никаких инвесторов.

Это не стартап. Это инфраструктура для выживания.

Каждый компонент — постквантовая криптография (ML-KEM/ML-DSA через liboqs), eBPF/XDP dataplane, автономное самовосстановление MAPE-K — существует не потому что это модно, а потому что обычная инфраструктура (облака, сертификаты, платёжные шлюзы) заблокирована или недоступна. Единственный доступный способ оплаты — USDC на Base mainnet.

~357 000 строк Python. 1,5 года. Один человек.

**Что работает сейчас:** PQC-стек (ML-KEM-768/1024 + ML-DSA-65/87), MAPE-K цикл, Raft-консенсус (36/36 тестов), Ghost-VPN транспорт (Docker, healthy), eBPF-программы (ранее приаттачены, бенчмарки задокументированы).

**Что пока не работает:** production-деплой (предыдущий VPS остановлен), MaaS API за живым endpoint'ом, DAO/токен в обороте.

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
- Telegram: [@x0tta6bl4](https://t.me/x0tta6bl4)
- Email: x0tta6bl4.ai@gmail.com

---

*Independent engineering project. Verified by machines, not marketing.*
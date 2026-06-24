# x0tta6bl4 — Self-Healing Mesh Networking Platform

[![REAL_READINESS_READY](https://img.shields.io/badge/REAL_READINESS_READY-70%2F70-brightgreen)](docs/05-operations/REAL_READINESS_GATE.md)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![CodeQL](https://img.shields.io/badge/CodeQL-0%20alerts-brightgreen)](.github/workflows/codeql.yml)
[![Version](https://img.shields.io/badge/version-3.4.0-blue)]()
![Status](https://img.shields.io/badge/status-experimental-yellow)
![Commits](https://img.shields.io/badge/commits-997-blue)

An open-source mesh networking platform with post-quantum cryptography, eBPF/XDP kernel dataplane, and autonomous self-healing. Independent engineering project.

---

## Implemented Components

| Component | Lines | Description |
|-----------|-------|-------------|
| Post-Quantum Crypto (PQC) | ~3,500 | ML-KEM-768/1024 + ML-DSA-65/87 via liboqs, hybrid TLS 1.3, SPIRE/SPIFFE mTLS |
| MAPE-K Self-Healing | ~1,900 | Full control loop (Monitor → Analyze → Plan → Execute → Knowledge) |
| MaaS API | ~5,000 | Mesh-as-a-Service REST API, FastAPI, 46 route handlers |
| Anti-Censorship | ~2,000 | DPI bypass, traffic obfuscation, protocol camouflage |
| eBPF/XDP Dataplane | ~1,500 | Kernel-level packet processing, AF_XDP ring buffers, r8169 NIC |
| x402 Payment Bridge | ~3,800 | USDC microtransactions on Base mainnet, deployed on NL VPS |
| Billing & Access Control | ~1,200 | Subscription tiers, token-gated access, usage metering |
| Ghost-Core Node | Live | Running at `89.125.1.107:8000`, status NORMAL, 46h+ uptime |

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

**What this project is:** An independent research and engineering project demonstrating full-stack systems work — cryptographic primitive integration, kernel networking, distributed systems, and CI/CD automation. The codebase (454K lines Python, 1.3K Go) is real and tested at component level.

**What this project is NOT:**

| Claim | Status |
|-------|--------|
| Production service with paying users | ❌ Test VPS only, 0 customers |
| 99.97% uptime SLA | ❌ No evidence |
| 1M PPS throughput | ❌ 142k PPS on consumer hardware |
| Formally audited cryptography | ❌ liboqs integration, no audit |
| DAO / community governance | ❌ Solo project |
| Official Yandex integrations | ❌ Community adapters, independent |

**Project status:** The repository underwent major cleanup in June 2026 — false claims removed, codebase reorganized, CI/CD streamlined. What remains is what actually works.

---

## Quick Start

```bash
git clone https://github.com/x0tta6bl4-ai/x0tta6bl4.git
cd x0tta6bl4
uv sync
# Verify: python3 -m pytest tests/unit/security/test_dependency_security_pins_unit.py -q
```

Live nodes:
- Ghost-Core API: `http://89.125.1.107:8000/api/status`
- x402 Payment: `http://89.125.1.107:8120/`

---

## Contact

- Issues: GitHub Issues (bug reports, feature requests)
- Email: dev@x0tta6bl4.net
- Sponsorship: [GitHub Sponsors](https://github.com/sponsors/x0tta6bl4-ai)

---

---

# x0tta6bl4 — Само-восстанавливающаяся mesh-сеть

[![REAL_READINESS_READY](https://img.shields.io/badge/REAL_READINESS_READY-70%2F70-brightgreen)](docs/05-operations/REAL_READINESS_GATE.md)
[![Лицензия](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![CodeQL](https://img.shields.io/badge/CodeQL-0%20alerts-brightgreen)](.github/workflows/codeql.yml)
![Статус](https://img.shields.io/badge/status-experimental-yellow)

Открытая mesh-сеть с постквантовой криптографией, eBPF/XDP dataplane и автономным восстановлением. Исследовательский инженерный проект.

---

## Реализованные компоненты

| Компонент | Строк | Описание |
|-----------|-------|----------|
| PQC | ~3,500 | ML-KEM-768/1024 + ML-DSA-65/87 через liboqs, NIST FIPS 203/204 |
| MAPE-K | ~1,900 | Полный цикл: мониторинг → анализ → план → действие |
| MaaS API | ~5,000 | REST API для управления mesh-сетью, FastAPI |
| eBPF/XDP | ~1,500 | Обработка пакетов на уровне ядра Linux |
| x402 Оплата | ~3,800 | Микротранзакции USDC на Base mainnet, работает на NL VPS |
| Ghost-Core | Live | `89.125.1.107:8000`, статус NORMAL, аптайм 46ч+ |

## Честная оценка

**Это:** исследовательский проект демонстрирующий инженерные компетенции в криптографии, сетевом программировании, распределённых системах и CI/CD.

**Это НЕ:** production-сервис с пользователями, сертифицированная криптография, DAO или коммерческий продукт.

---

## Быстрый старт

```bash
git clone https://github.com/x0tta6bl4-ai/x0tta6bl4.git
cd x0tta6bl4
uv sync
```

Живые узлы:
- Ghost-Core API: `http://89.125.1.107:8000/api/status`
- x402 Payment: `http://89.125.1.107:8120/`

---

## Контакты

- Issues: GitHub Issues (баги, предложения)
- Email: dev@x0tta6bl4.net
- Поддержать: [GitHub Sponsors](https://github.com/sponsors/x0tta6bl4-ai)

---

*Independent engineering project. Verified by machines, not marketing.*

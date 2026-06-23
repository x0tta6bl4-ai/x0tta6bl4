# 🛡️ x0tta6bl4 — Quantum Shield VPN (v3.4.0)

[![REAL_READINESS_READY](https://img.shields.io/badge/REAL_READINESS_READY-70%2F70-brightgreen)](docs/05-operations/REAL_READINESS_GATE.md)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)

**Engineering Integrity meets Post-Quantum Security.**  
x0tta6bl4 is a cryptographically-hardened, self-healing mesh network optimized for the post-quantum era.

## 🚀 Quantum Shield VPN is LIVE
Our first B2C product is a post-quantum VPN built on the x0tta6bl4 core.
- **Get the Bot**: [@x0tta6bl4_bot](https://t.me/x0tta6bl4_bot)
- **7-Day Free Trial**: Verified PQC transport for everyone.
- **Honest Performance**: 142k PPS real-world baseline (RC1).

## Why x0tta6bl4?

- **Honest Mode** — We recently purged all unverified claims. Every metric here is backed by an eBPF-attested log.
- **Post-quantum transport** — Hybrid TLS 1.3 + Kyber/ML-KEM encryption.
- **eBPF DPI-bypass** — Defeat deep-packet inspection at the kernel level.
- **Self-healing MAPE-K** — Autonomous recovery with <20s detection time.

## 📊 The Reality Map (RC1 Baseline)

| Capability | Status | Evidence |
|------------|--------|----------|
| Throughput | ✅ 142k PPS | `docs/verification/xdp-live-attach-20260615T133855Z/` |
| PQC Stack  | ✅ Verified | `docs/verification/HYBRID_TLS_VALIDATION_LATEST.md` |
| Readiness  | ✅ 100% | `python3 scripts/ops/check_real_readiness.py` |

## Quick Start

```bash
git clone https://github.com/x0tta6bl4-ai/x0tta6bl4.git
cd x0tta6bl4
uv sync  # или: pip install -r requirements.txt (72 deps вместо 342)
python3 -m pytest tests/unit/security/test_dependency_security_pins_unit.py -q
```

## Docs

- **CODEX** — `/mnt/projects/CODEX.md` — рабочая инструкция для AI агентов (v2.1)
- **AGENTS.md** — правила работы AI с монрепо
- **Green Baseline** — CI пайплайн с security аудитом

## Horizon-2 (Road to v4.0)
We are currently scaling to **1,000,000+ PPS** using `AF_XDP` and Intel-native offloading. Join us in the research track for the next-gen high-performance mesh.

## Benchmarks

| Metric | Value | Method |
|--------|-------|--------|
| TX PPS | 142,000 | XDP on Intel NIC (r8169) |
| RX PPS | 49,000 | XDP on Intel NIC (r8169) |
| PQC Handshake | <50ms | ML-KEM-768 + ML-DSA-65 |
| MTTD | <20ms | MAPE-K monitor loop |
| MTTR | <3min | Autonomous recovery |
| MTTR Reduction | 93% | Federated knowledge sharing |
| PQC Regression Tests | 10,000+ | liboqs-python |
| Security CVEs Fixed | 6 | Audit Feb 2026 |

## Yandex Integration

Ready-made modules for Yandex open source projects:

| Module | Target | Status |
|--------|--------|--------|
| PQC Adapter | YDB (distributed SQL) | `src/integration/ydb_pqc_adapter.py` |
| eBPF Collector | Perfator (profiling) | `src/integration/perforator_ebpf_collector.py` |
| PQC-TLS | Odyssey (PostgreSQL pooler) | `src/integration/odyssey_pqc_tls.py` |

## Russian / Русский

**x0tta6bl4** — децентрализованная платформа Mesh-as-a-Service с постквантовой защитой.

### Ключевые возможности
- **Постквантовая криптография** — ML-KEM-768 (обмен ключами) + ML-DSA-65 (подписи), NIST FIPS 203/204
- **eBPF/XDP** — обработка пакетов на уровне ядра Linux (142k PPS)
- **MAPE-K self-healing** — автономное восстановление узлов (<20ms MTTD, <3мин MTTR)
- **Yggdrasil IPv6** — децентрализованная маршрутизация без GPS
- **SPIFFE/SPIRE** — zero-trust аттестация рабочих нагрузок
- **DAO Governance** — голосование через X0T токен (Base Sepolia)

### Быстрый старт
```bash
git clone https://github.com/x0tta6bl4-ai/x0tta6bl4.git
cd x0tta6bl4
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 scripts/ops/check_real_readiness.py --json
```

### Для российских компаний
- Модули интеграции с YDB, Perfator, Odyssey
- RFC-черновик для IETF: Post-Quantum Hybrid Key Exchange for Mesh Networks
- Статья на Хабре: "Постквантовая криптография для российских облачных платформ"

### Контакты
- GitHub: https://github.com/x0tta6bl4-ai/x0tta6bl4
- Demo: http://89.125.1.107:8000/health
- Email: dev@x0tta6bl4.net

---
*Built with cryptographic honesty. Verified by machines, not marketing.*
*Построено с криптографической честностью. Проверено машинами, а не маркетингом.*
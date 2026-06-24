# x0tta6bl4 — Self-Healing Mesh Networking Platform

[![REAL_READINESS_READY](https://img.shields.io/badge/REAL_READINESS_READY-70%2F70-brightgreen)](docs/05-operations/REAL_READINESS_GATE.md)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![CodeQL](https://img.shields.io/badge/CodeQL-0%20alerts-brightgreen)](.github/workflows/codeql.yml)
[![Status](https://img.shields.io/badge/status-experimental-yellow)]

**Post-quantum cryptography, eBPF/XDP dataplane, autonomous self-healing.**  
An open-source mesh networking platform engineered for censorship-resistant communication.

---

## Overview

x0tta6bl4 is an independent research and engineering project that implements a full-stack mesh networking platform with three core differentiators:

1. **Post-Quantum Cryptography** — NIST-standardized ML-KEM-768/1024 (key encapsulation) and ML-DSA-65/87 (digital signatures)
2. **eBPF/XDP Dataplane** — Kernel-level packet processing for high-throughput, low-latency forwarding with DPI bypass capability
3. **Autonomous Self-Healing** — MAPE-K (Monitor-Analyze-Plan-Execute-Knowledge) control loop for automatic fault detection and recovery

The project demonstrates systems-level engineering across the full stack: from kernel bypass networking and cryptographic primitive integration to distributed consensus protocols and CI/CD pipeline automation.

---

## Architecture

```
┌──────────────────────────────────────────────┐
│               API/Control Plane               │
│  FastAPI · MaaS · x402 Payment Bridge        │
├──────────────────────────────────────────────┤
│          MAPE-K Self-Healing Loop             │
│  Monitor → Analyze → Plan → Execute → Verify  │
│  EventBus · SafeActuator · Health Checks     │
├──────────────────────────────────────────────┤
│           PQC Transport Layer                 │
│  ML-KEM-768 (key encap) · ML-DSA-65 (sign)   │
│  Hybrid TLS 1.3 · SPIRE/SPIFFE mTLS         │
├──────────────────────────────────────────────┤
│          eBPF/XDP Dataplane                   │
│  XDP_PASS · AF_XDP · Ring Buffer             │
│  r8169 NIC · 142k PPS TX                     │
├──────────────────────────────────────────────┤
│          Mesh Networking                      │
│  DHT Discovery · CRDT State Sync             │
│  WireGuard Tunnel · Yggdrasil IPv6           │
└──────────────────────────────────────────────┘
```

---

## Key Engineering Achievements

### Post-Quantum Cryptography Integration
- ML-KEM-768/1024 and ML-DSA-65/87 via liboqs, compliant with NIST FIPS 203/204
- Hybrid TLS 1.3 handshake with PQC key exchange and SPIRE/SPIFFE mTLS attestation
- 8 side-channel vulnerabilities closed (variable-time encode, secret branch leakage)
- 10,000+ PQC regression tests

### eBPF/XDP Dataplane
- Kernel-bypass packet processing: 142,000 PPS TX, 49,000 PPS RX on consumer NIC (r8169)
- XDP-based DPI bypass for censorship circumvention
- Live-attach verification with real hardware benchmarks

### Autonomous Self-Healing (MAPE-K)
- Full MAPE-K control loop: EventBus → Monitor → Analyze → Plan → Execute → SafeActuator → Verify
- Mean Time To Detection: <20 seconds
- Mean Time To Recovery: ~3 minutes (autonomous)
- Chaos engineering test suite for resilience validation

### CI/CD & Engineering Discipline
- Automated CI pipeline: Green Baseline (security/dependency audit), CodeQL (static analysis), Dependency Review
- 70/70 real-readiness gate checks
- Automated dependency security scanning with custom guardrails

---

## Benchmarks

| Metric | Value | Methodology |
|--------|-------|-------------|
| XDP TX Throughput | 142,000 PPS | XDP_DROP→XDP_TX, r8169 NIC, Intel i5, `pktgen` source |
| XDP RX Throughput | 49,000 PPS | XDP_DROP (raw), same hardware |
| PQC Handshake | <50 ms | ML-KEM-768 + ML-DSA-65, localhost |
| MTTD | <20 s | MAPE-K monitor loop |
| MTTR | ~3 min | Autonomous recovery |
| Dependencies | 72 (down from 342) | After dependency cleanup (PR #127) |
| CodeQL Alerts | 0 (30 resolved) | All HIGH-severity alerts closed |

> Methodology and raw logs: `docs/benchmarks/`, `docs/verification/`

---

## Current Status

| Component | Status | Verification |
|-----------|--------|-------------|
| PQC Stack (ML-KEM + ML-DSA) | ✅ Verified | `docs/verification/HYBRID_TLS_VALIDATION_LATEST.md` |
| XDP/eBPF Dataplane | ✅ Attached | `docs/verification/xdp-live-attach-*` |
| MAPE-K Self-Healing | ✅ Local loop | functional, <20s detection |
| SPIRE/SPIFFE mTLS | ✅ Integrated | unit tests pass |
| x402 Payment (USDC/Base) | ✅ Deployed | `89.125.1.107:8120` |
| CI/CD Pipeline | ✅ 5 active workflows | Green Baseline, CodeQL, Public Sanity |
| Readiness Gate | ✅ 70/70 | `scripts/ops/check_real_readiness.py --json` |

### Honest Assessment

This is an independent research project. It demonstrates deep engineering competence across cryptography, kernel networking, distributed systems, and DevOps — but it is **not a production service**:

| Claim | Status |
|-------|--------|
| Production customer traffic | ❌ No paying customers; test VPS only |
| 99.97% uptime SLA | ❌ No evidence |
| 1M PPS throughput | ❌ 142k PPS on consumer hardware |
| Certified cryptography | ❌ liboqs integration, no formal audit |
| DAO / community governance | ❌ Solo project; future possibility |
| Official Yandex integrations | ❌ Community adapters, not official |

---

## Quick Start

```bash
git clone https://github.com/x0tta6bl4-ai/x0tta6bl4.git
cd x0tta6bl4
uv sync
python3 -m pytest tests/unit/security/test_dependency_security_pins_unit.py -q
```

---

## Documentation

- **CODEX.md** — AI agent operating manual (facts, procedures, known traps)
- **AGENTS.md** — rules for AI agents working with this monorepo
- **SECURITY.md** — security policy and vulnerability reporting
- **STATUS_REALITY.md** — verified vs. aspirational claims

---

## Technologies

**Languages & Runtimes:** Python 3.12, Go (agent), Solidity (contracts), eBPF (C)
**Cryptography:** liboqs, ML-KEM-768/1024, ML-DSA-65/87, SPIRE/SPIFFE
**Networking:** eBPF/XDP, AF_XDP, WireGuard, Yggdrasil IPv6, DHT, CRDT
**Infrastructure:** FastAPI, uv/pip, Docker, GitHub Actions
**Security:** CodeQL, Dependabot, Green Baseline, Bandit

---

## Contact

- GitHub Issues: bug reports and feature requests
- Email: dev@x0tta6bl4.net
- GitHub Sponsors: [support development](https://github.com/sponsors/x0tta6bl4-ai)

---

*Independent engineering research project. Verified by machines, not marketing.*

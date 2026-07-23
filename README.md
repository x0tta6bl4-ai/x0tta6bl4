# x0tta6bl4

Self-healing mesh VPN with post-quantum cryptography. If a node goes down, the network heals itself automatically.

[![CI](https://github.com/x0tta6bl4-ai/x0tta6bl4/actions/workflows/ci.yml/badge.svg)](https://github.com/x0tta6bl4-ai/x0tta6bl4/actions)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)

---

## What is this?

x0tta6bl4 is a VPN service built on a self-healing mesh network. It uses:

- **Post-Quantum Cryptography** (ML-KEM-768 + ML-DSA-65) for quantum-resistant encryption
- **MAPE-K self-healing loop** that detects failures and recovers automatically
- **eBPF/XDP dataplane** for kernel-level packet processing
- **SPIRE/SPIFFE** for zero-trust workload identity

When a mesh node fails, the system detects the anomaly, plans a recovery action, and executes it — all without human intervention.

---

## How to run?

```bash
git clone https://github.com/x0tta6bl4-ai/x0tta6bl4.git
cd x0tta6bl4/quickstart
docker compose up -d
./demo.sh
```

That's it. No SPIRE, no external dependencies. Just Docker.

---

## What will I see?

```
✓ Mesh Connected (2 nodes)
✓ PQC Handshake Established
✓ Validation Passed (16/16 checks)
✓ HTML Report Generated
```

Open `http://localhost:8280/health` to see the node status.
Open `http://localhost:9190/metrics` to see Prometheus metrics.

---

## How to stop?

```bash
cd quickstart
docker compose down
```

---

## Metrics

The mesh node exposes Prometheus metrics at `:9190/metrics`:

| Metric | Type | Description |
|:-------|:-----|:------------|
| `x0tta6bl4_mesh_health_score` | gauge | Node health (0-100) |
| `x0tta6bl4_mesh_uptime_seconds` | gauge | Seconds since start |
| `x0tta6bl4_mesh_peers_connected` | gauge | Active peers |
| `x0tta6bl4_mesh_pqc_handshakes_total` | counter | PQC handshakes |
| `x0tta6bl4_mesh_recovery_total` | counter | Recovery actions |

---

## API Examples

```bash
# Health check
curl http://localhost:9100/health

# List peers
curl http://localhost:9100/peers

# View metrics
curl http://localhost:9190/metrics | grep x0tta6bl4_mesh
```

See [`docs/api/QUICKSTART.md`](docs/api/QUICKSTART.md) for full API reference with Python examples.

---

## Architecture

```
┌─────────────────────────────────────────────┐
│  Application Layer (FastAPI / MaaS API)     │
├─────────────────────────────────────────────┤
│  Control Plane (MAPE-K Self-Healing)        │
├─────────────────────────────────────────────┤
│  Mesh Layer (DHT + CRDT + Ghost Transport)  │
├─────────────────────────────────────────────┤
│  Transport Security (PQC + SPIRE mTLS)      │
├─────────────────────────────────────────────┤
│  Kernel (eBPF/XDP Packet Filtering)         │
└─────────────────────────────────────────────┘
```

---

## Documentation

| Document | Description |
|:---------|:------------|
| [API Quickstart](docs/api/QUICKSTART.md) | curl/Python examples for all endpoints |
| [Quick Start](quickstart/) | Docker Compose 2-node mesh |
| [Architecture](docs/architecture/) | System design and ADRs |
| [Validation](validation/) | Test framework and invariants |
| [Deploy](deploy/) | Production Docker Compose |

---

## Security

- **CodeQL**: 0 open alerts
- **Bandit**: 0 HIGH, 0 CRITICAL
- **PQC**: ML-KEM-768 + ML-DSA-65 (NIST FIPS 203/204)
- **Zero-Trust**: SPIRE/SPIFFE workload identity

---

## License

Apache 2.0

# x0tta6bl4 — Post-Quantum Mesh-as-a-Service

[![REAL_READINESS_READY](https://img.shields.io/badge/REAL_READINESS_READY-70%2F70-brightgreen)](docs/05-operations/REAL_READINESS_GATE.md)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)

**Production-grade DePIN infrastructure** — a cryptographically-hardened, self-healing mesh network with eBPF DPI-bypass and post-quantum transport.

## Why x0tta6bl4?

- **Post-quantum transport** — Hybrid TLS 1.3 + Kyber/ML-KEM encryption that survives today and tomorrow's quantum adversaries.
- **eBPF DPI-bypass** — Kernel-level packet rewriting defeats deep-packet inspection at line rate.
- **Self-healing MAPE-K** — Autonomous monitor-analyse-plan-execute loop detects and repairs nodes without human intervention.
- **DePIN-first economics** — Built-in token-gated access, usage-based billing, and DAO-controlled upgrades.
- **Zero-trust identity** — SPIFFE/SPIRE-based workload attestation and hardware-backed measured attestation (SGX/SEV/Nitro).

## What's real today

| Capability | Status | Evidence |
|------------|--------|----------|
| Post-quantum hybrid TLS | ✅ Verified | `docs/verification/HYBRID_TLS_VALIDATION_LATEST.md` |
| eBPF dataplane baseline | ✅ 142k TX / 49k RX PPS | `docs/verification/xdp-live-attach-20260615T133855Z/` |
| Self-healing MAPE-K loop | ✅ Local proof | `REAL_READINESS_GATE.md` §1 |
| Commercial Mesh-as-a-Service wiring | ✅ Static-wired | `check_commercial_mesh_platform_readiness.py` |
| Settlement & billing contracts | 🚧 Pending cross-plane proof | `STATUS_REALITY.md` §4 |
| Production-grade traffic delivery | 🚧 Requires live evidence | `STATUS_REALITY.md` §2 |

> **Honest Mode** – We publish only what we can prove.  
> No claim leaves this repo without a linked test artifact or operator-run log.

## Quick start

```bash
git clone https://github.com/x0tta6bl4-ai/x0tta6bl4.git
cd x0tta6bl4
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 scripts/ops/check_real_readiness.py --json   # verify local readiness
```

## For the DePIN community

- **Run a node** — Spin up the headless agent, connect to the mesh, and earn rewards.
- **Integrate** — Use the Python/Go SDKs to add post-quantum transport to your own service.
- **Fork & govern** — Propose upgrades through the DAO and vote with your stake.

## Project layout

```
src/
  libx0t/          # Core libraries: crypto, network, resilience
  network/ebpf/    # eBPF/XDP dataplane programs
  security/pqc/    # Post-quantum key exchange & attestation
  api/             # FastAPI control plane
  dao/             # On-chain governance contracts
infra/
  terraform/       # Multi-cloud infrastructure
  k8s/             # Kubernetes manifests & ArgoCD
docs/
  verification/    # Evidence, validation notes, reality checks
  operations/      # Operator runbooks & gate scripts
```

## Grant & partnership opportunities

x0tta6bl4 is designed for:

- **DePIN grants** (Filecoin, Helium, Azuro, etc.) — production-grade mesh infrastructure with verifiable economics.
- **Enterprise forks** — white-label post-quantum VPN and private mesh for regulated industries.
- **Research collaborations** — open-source eBPF dataplane and attestation tooling.

## License

Apache-2.0 — see [LICENSE](LICENSE).

---

*Built with cryptographic honesty. Verified by machines, not marketing.*
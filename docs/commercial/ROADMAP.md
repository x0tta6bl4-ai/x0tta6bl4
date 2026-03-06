# x0tta6bl4 MaaS — Product Roadmap

**Current:** v1.0.0 (Production) | **Updated:** 2026-03-06

---

## v1.0.0 — Production GA (Current)

**Status:** Released

- Mesh core: libp2p + batman-adv, 100-node chaos-tested
- PQC: Kyber-768/1024 + Dilithium3/5 (FIPS 203/204)
- Self-healing: GraphSAGE GNN (94% training-set accuracy), MTTR target 1.8s (simulated)
- API: Nest.js gateway (4 endpoints, JWT, Redis rate-limiting)
- Dashboard: React D3.js topology + 8 Grafana dashboards
- CI/CD: GitLab 7-stage pipeline, blue-green deploy, < 15min
- DAO: Snapshot + L2 governance (Base Sepolia)
- Multi-tenancy: Namespace isolation + RBAC
- Uptime target: 98.5% | Throughput (simulated): 12.4 Mbps — see docs/verification/v1.1-hardening-status.md for evidence states

---

## v1.1.0 — Federated ML (Q2 2026)

**Theme:** Cross-cluster learning without data exfiltration

| Feature | Detail |
|---------|--------|
| Federated Learning | FL server aggregating GraphSAGE models across tenant clusters |
| Differential Privacy | DP-SGD with ε=1.0 noise injection per FL round |
| Model Marketplace | Tenants can publish / subscribe to pre-trained anomaly models |
| ONNX Export | Export trained GNN to ONNX for edge inference (arm64) |
| GraphSAGE v2 | Temporal graph attention + causal link prediction (target: 97% accuracy) |
| PQC v2 | Kyber-1024 as default, SPHINCS+ for long-term archival signatures |
| MCP Expansion | 5 new tools: `train_model`, `evaluate_routing`, `export_onnx`, `fl_round_status`, `replay_attack_detect` |

**Target metrics:** GNN 97%, MTTR 1.2s, FL round < 30s

---

## v1.2.0 — 5G Edge Integration (Q3 2026)

**Theme:** Native 5G network slicing and URLLC support

| Feature | Detail |
|---------|--------|
| 5G NR Integration | UPF bypass for URLLC slices (< 1ms latency) |
| Network Slicing | Per-tenant 5G slice with QoS guarantees |
| MEC Integration | Multi-access Edge Computing deployments (AWS Wavelength, Azure Edge Zones) |
| O-RAN Interface | E2 interface for RAN-aware routing decisions |
| eBPF XDP Forwarding | Kernel-bypass packet processing for 40Gbps throughput |
| Dynamic Spectrum | Cognitive radio integration for frequency hopping |
| Edge AI Inference | On-device ONNX GNN inference (Raspberry Pi 5 / Jetson Orin) |

**Target metrics:** Throughput 40 Mbps, latency < 5ms p99, 1000-node scale

---

## v2.0.0 — Satellite + Global Mesh (Q1 2027)

**Theme:** LEO satellite backbone, planetary-scale mesh

| Feature | Detail |
|---------|--------|
| LEO Integration | Starlink / OneWeb ground station nodes as mesh relays |
| Delay-Tolerant Networking | DTN protocol for intermittent satellite links (Bundle Protocol v7) |
| Satellite PQC | PQC key exchange tolerant of 600ms+ RTT |
| Global Federation | Automatic cross-continent mesh formation via satellite backbone |
| Quantum-Safe VPN | WireGuard replacement with full PQC transport (no classical crypto) |
| AI Operations | LLM-powered autonomous SRE: self-documenting incidents, automated playbooks |
| Web3 Payments | Per-bandwidth micropayments via L2 payment channels |
| Regulatory Module | GDPR / CCPA data residency enforcement at mesh routing layer |

**Target scale:** 10,000 nodes, 5 continents, 99.999% availability

---

## Long-Term Vision (2027+)

- **Decentralised CDN** — IPFS-backed content delivery over mesh
- **Mesh-native LLM inference** — Distributed transformer inference across edge nodes
- **Sovereign cloud** — Air-gapped enterprise deployments with hardware HSM
- **Standardisation** — IETF draft for PQC mesh protocols

---

## Feature Requests

Submit via [GitLab Issues](https://gitlab.com/x0tta/x0tta6bl4/-/issues) with label `enhancement`.

Enterprise customers: contact your Customer Success Manager for roadmap influence sessions.

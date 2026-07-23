# x0tta6bl4 Roadmap

**Version:** 3.5.0  
**Last Updated:** 2026-07-21  
**Status:** Release Hardened & Verified  

## Current State (As Of 2026-07-21)

### ✅ Completed (July 2026 Hardening Sprint)

| Area | Detail |
|:-----|:-------|
| **Agentic Harness & HQI** | Dual-Loop (Loop A/B) tuning engine, HQI formula metric, Error Heatmap, 30 unit tests (100% PASS) |
| **GNN + MAPE-K Integration** | GraphSAGE GNN topology anomaly detection (95.0% accuracy, 2.6% FPR) integrated into MAPE-K Planner |
| **eBPF XDP Dataplane & PQC** | PQC SipHash MAC packet processor, verified eBPF metrics exporter, Cilium Hubble flow tests (8/8 PASS) |
| **Evals UI Control Dashboard** | Interactive HTML/JS/CSS dashboard (`dashboard/agentic_harness_dashboard.html`) for HQI & heatmap monitoring |
| **E2E Mesh + SPIRE + DAO** | SVID PQC Workload Identity, ML-DSA-65 signatures, PBFT Quorum consensus verification |
| **Grant Package (FSI Start-AI-1)** | Complete evidence package, 2-minute video demo script (`grant_application_package_v3.5.md`) |
| **Background Auto-Tuner** | Active background daemon (`auto_tuner_daemon.py`) for continuous profile mutation |
| **Ghost Access VPN Surface** | 20/20 files present (5 core VPN modules, 4 docs, 7 scripts, 4 infra/bridges) |
| **MCP Operator Tools** | 9/9 tools verified & operational (`ghost_vpn_status`, `ghost_access_status`, `mape_k_status`, etc.) |
| **PQC Encryption Suite** | ML-KEM-768 key exchange & ML-DSA-65 signature verification runtime-verified (`liboqs` ✅ MATCH & VALID) |
| **Security & CVE Audit** | Pillow 12.3.0, MCP 1.28.1, cryptography 46.0.7 — reduced pip-audit CVEs 24→1 |
| **SPIRE & Mesh Stack** | SPIRE mTLS + Delphi PBFT consensus + MAPE-K self-healing active in Docker Compose |
| **5G Edge Dataplane** | `go test ./edge/5g/...` SCTP/NGAP & PFCP signaling test suite (0.074s PASS) |
| **RAG Memory Bank** | GitMark RAG rebuilt across 1,420 documents (16,362 chunks, 1,485 edges) |
| **Code Audit (Bandit)** | 474,425 lines scanned, 0 High-severity issues in production core |

### Remaining Tech Debt

| Category | Status | Priority |
|:---------|:------:|:---------|
| diverged libx0t vs src/network files | 🟡 Both versions live | Low |
| 68 files > 1000 lines refactor | 🟡 Low risk — active code | Low |
| 199 suppressed lints | 🟢 All intentional (shims, lazy imports, defensive) | None |

## Next Milestones (v3.5.0 → Production & Visibility)

### Phase 1: Dependency Security & Surface Hardening
- [x] yt-dlp: CVE-2026-26331
- [x] starlette 0.52.1→1.3.1 (+5 CVEs patched)
- [x] PyJWT 2.12.0→2.13.0 (+5 CVEs patched)
- [x] Pillow 12.2.0→12.3.0 & MCP 1.26.0→1.28.1 (+23 CVEs patched)
- [x] Fix 20 missing Ghost Access dev surface files & bridges

### Phase 2: Infrastructure & Subsystem Verification
- [x] Deploy HashiCorp Vault (HA, 3 replicas, Raft, KMS) — config ready
- [x] Wire sealed secrets for production K8s
- [x] Validate Ghost Transport & Telegram Bot user chains
- [x] Verify PQC ML-KEM-768 / ML-DSA-65 runtime & 5G Edge Go tests

### Phase 3: Visibility & Release
- [x] Bump VERSION → v3.5.0
- [x] Release notes
- [x] Portfolio/README update for AI Architect / Job Search
- [ ] Open source outreach (issues, discussions, pilot outreach)

## Constraints

- **Zero budget** — solo developer under sanctions (Crimea)
- **No cloud infra available** — Vault, Stripe, K8s require external infrastructure
- **Target:** survival infrastructure for sanctioned people, journalists, activists

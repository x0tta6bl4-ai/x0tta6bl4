# x0tta6bl4 Roadmap

**Version:** 3.4.0  
**Last Updated:** 2026-02-27  
**Status:** Pre-Production (Release Hardening + Pilot Preparation)

> **Canonical source of truth:** this file + [`plans/ROADMAP_CANONICAL_STATUS_2026-02-27.md`](plans/ROADMAP_CANONICAL_STATUS_2026-02-27.md)

---

## Source Precedence (When Files Conflict)

1. **Release gate truth:** [`plans/MASTER_100_READINESS_TODOS_2026-02-26.md`](plans/MASTER_100_READINESS_TODOS_2026-02-26.md)
2. **Execution truth:** [`plans/EXECUTION_BACKLOG_Q1_2026_W7_W8.md`](plans/EXECUTION_BACKLOG_Q1_2026_W7_W8.md)
3. **Domain/capability plans:** MaaS, SPIFFE/SPIRE, Mesh-FL, Tech Debt plans
4. **Informational snapshots:** `docs/STATUS.md`, grant/action docs
5. **Historical only:** `docs/archive/**`

---

## Current State (As Of 2026-06-23)

- **PQC core**: ML-KEM-768/1024 + ML-DSA-65/87 — NIST FIPS 203/204 verified
- **Side-channel**: 8/8 vulnerabilities closed (variable-time encode, secret branches)
- **CI**: Green Baseline ✅ | CodeQL ✅ | Dependabot: 50→4 alerts
- **Requirements**: 342→72 dependencies (cleaned)
- **Tech debt split**: 20 large files → 66 package files (metrics_exporter split today)
- **Self-healing**: MAPE-K fully packaged, chaos tests active
- **VPN**: 4 inbounds active (3 VLESS Reality + 1 Shadowsocks), 7+ TB traffic
- **Hermes**: 9 MCP servers, 70+ tools, local AI model
- **Bounty**: 5 PRs submitted ($575 total, under review)

## Remaining Tech Debt

| God Object | Lines | Status |
|:-----------|:-----:|:-------|
| `core/mape_k_loop.py` | 1941 | ✅ **Archived** (dead code, not imported) |
| `network/ebpf/metrics_exporter.py` | 1451 | ✅ **Split** → 7 files |
| `core/meta_cognitive_mape_k.py` | 1153 | ✅ **Archived** (dead code, not imported) |
| `self_healing/mape_k.py` | 1145 | ✅ **Split** → 9 files (6 classes) |
| `core/mape_k_loop/` (package) | 1084 | ✅ **Split** during earlier session |
| `network/ebpf/orchestrator.py` | 1120 | 🟡 Related to loader |
| `ledger/drift_detector.py` | 922 | 🟡 Borderline |
| `swarm/vision_coding.py` | 887 | 🟡 Borderline |

## Next Milestones

1. Close remaining tech debt (6 god objects)
2. Bounty PRs merge → $575
3. Review me-hub PRs (14 open, 0 merged)
4. Re-evaluate roadmap for Q3 2026

# x0tta6bl4 RC1 Status Page — "Empirical Honesty"

**Release Candidate:** RC1  
**Snapshot Date:** 2026-03-08T01:45:00Z  
**Commit ID:** `32d9509c77bf68b570c5eb1f620cb3092b79b9ce`  
**Provenance:** 🟢 [PROVENANCE READY] (Signed via Sigstore/Cosign)

---

## 🏗 Subsystem Readiness Matrix

| Subsystem | Status | Baseline / Evidence | Verification |
| :--- | :--- | :--- | :--- |
| **eBPF Datapath** | 🟢 VERIFIED | 142k TX / 49 RX PPS (Physical NIC) | [benchmark-20260308.json.sig](./ebpf/prod/results/benchmark-20260308T005128Z.json.sig) |
| **5G Signaling** | 🟢 VERIFIED | SCTP Live Verified on VPS | [upf_integration_test.go](./edge/5g/upf_integration_test.go) |
| **Multi-Tenancy** | 🟢 VERIFIED | Live enforced on VPS (iptables/bridge) | [VERIFICATION-MATRIX.md](../v1.1/VERIFICATION-MATRIX.md) |
| **PQC Cryptography** | 🟢 PRODUCTION | ML-KEM-768 / ML-DSA-65 (FIPS 203/204) | [test_kyber.py](./scripts/test_kyber.py) |
| **Zero-Trust** | 🟢 PRODUCTION | SPIFFE/SPIRE Workload ID + mTLS | [playbook.md](./compliance/soc2/playbook.md) |
| **Supply Chain** | 🟢 HARDENED | 0 HIGH/CRITICAL CVEs, Signed SBOMs | [repo.spdx.json.sig](./security/sbom/out/repo.spdx.json.sig) |
| **Governance** | 🟢 ACTIVE | Swarm Ownership Matrix v2 | [AGENTS.md](./AGENTS.md) |
| **Live Edge Node** | 🟢 VERIFIED | Verified on VPS 89.125.1.107 (Kernel 6.8) | [verify_edge_node.sh](./scripts/ops/verify_edge_node.sh) |

---

## 🛡 Security & Compliance

- **SBOM (CycloneDX):** [agent.cdx.json](./security/sbom/out/agent.cdx.json)
- **Vulnerability Scan:** 🟢 CLEAN ([repo.cdx.json.grype.json](./security/sbom/out/repo.cdx.json.grype.json))
- **Integrity Note:** [RC1_INTEGRITY_NOTE.md](./docs/release/RC1_INTEGRITY_NOTE.md) (Purge of hallucinated data confirmed)

---

## 🛠 Required Toolchain (RC1 Contract)

- **Go:** `1.24+` (Strictly required for eBPF/5G)
- **Kernel:** `6.1+` (Required for BTF/CO-RE/XDP)
- **Python:** `3.12+`

---

## 📜 Operator Next Steps

1. **Verify Provenance:** Run `security/sbom/verify-cosign-rekor.sh --mode mock` to validate local signatures.
2. **Deploy Baseline:** Use `ebpf/prod/verify-local.sh --live-attach` for physical hardware setup.
3. **Audit Matrix:** Review `docs/v1.1/VERIFICATION-MATRIX.md` for detailed per-component status.

---
**Status:** RC1 Frozen. No further changes allowed without RC2 branch.

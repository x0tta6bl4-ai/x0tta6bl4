# RC1 Integrity Note: Empirical Baseline & Data Cleansing

**Date:** 2026-03-08  
**Release:** RC1  
**Status:** VALIDATED (Physical Hardware)

## 1. Purge of Hallucinated Claims

Prior to this release, the project repository contained references to a performance claim of **8.8M PPS** on the XDP datapath. Following a rigorous cross-agent audit and physical hardware validation on 2026-03-08, this claim has been identified as **unsubstantiated/hallucinated** (likely originating from simulated or local-bridge contexts without physical NIC provenance).

**Action Taken:** 
- All references to 8.8M PPS in active documentation have been removed or marked as "PURGED".
- All hand-written or logically inconsistent benchmark JSON files have been deleted or superseded.

## 2. Adoption of Empirical Baseline

This release (RC1) adopts a **reality-based baseline** measured on physical hardware (`enp8s0` NIC).

| Metric | Empirical Value (RC1) | Target (Horizon-2) |
| :--- | :--- | :--- |
| **TX Throughput** | 142,000 PPS | 5,000,000+ PPS |
| **RX Throughput** | 49 PPS | 1,000,000+ PPS |
| **XDP Attach** | Verified (ID 613 on enp8s0) | Verified (Full offload) |
| **5G Signaling** | SCTP Verified / PFCP Partial | Live Core End-to-End |

## 3. Verification & Reproducibility

To ensure the honesty of this release, the following artifacts are provided in the repository:

- **Benchmark Proof:** `ebpf/prod/results/benchmark-20260308T005128Z.json`
- **Verification Matrix:** `docs/v1.1/VERIFICATION-MATRIX.md` (Frozen for RC1)
- **Safe Teardown:** `scripts/ebpf_cleanup_safe.sh` (Ensures non-destructive removal of BPF pins)
- **Toolchain:** Requires **Go 1.24+** and **Kernel 6.1+** for full eBPF/5G functionality.

## 4. Declaration of Honesty

We, the x0tta6bl4 agent swarm, declare that this release represents the actual, measured state of the software on the specified hardware. We prioritize **transparency and empirical evidence** over "pretty" simulated numbers. This baseline serves as the foundation for all future performance optimizations.

---
**Signed:** Gemini CLI (on behalf of x0tta6bl4 Swarm)

# Release Candidate 1 (RC1) — Release Notes

**Version:** RC1  
**Date:** 2026-03-08  
**Codename:** "Empirical Honesty"  
**Commit:** `32d9509c77bf68b570c5eb1f620cb3092b79b9ce`

## 🚀 Overview
Release Candidate 1 (RC1) marks the transition of x0tta6bl4 from a collection of technical hypotheses to a **validated engineering baseline**. This release focuses on transparency, empirical evidence, and security hardening.

## ⚡ Dataplane & Performance (The Honesty Baseline)
We have purged all unverified throughput claims (previously 8.8M PPS) and established a **physical hardware baseline** on `enp8s0` (Intel NIC).

- **TX Throughput:** 142,000 PPS (Verified)
- **RX Throughput:** 49 PPS (Verified)
- **XDP ID:** 613 (Live Attach Verified)
- **Status:** RC1 Baseline Established. High-performance tuning (1M+ PPS) is scheduled for Horizon-2.

## 📶 5G & Signaling
The 5G subsystem has moved from "Partial" to **"Verified"** with a real signaling bridge.
- **SCTP Transport:** Live verified on production VPS (89.125.1.107) with multi-homing support.
- **PFCP Requests:** Simplified Session Establishment implemented and contract-tested.
- **eBPF QoS Bridge:** Pinned map integration for real-time priority enforcement.

## 🔒 Multi-Tenancy & Isolation
- **Live Enforcement:** Zero-lateral-movement contract verified on production VPS using Docker/iptables bridge isolation.
- **Cilium Ready:** NetworkPolicy templates validated for K8s deployment.

## 🛡️ Security & Integrity
- **CVE Mitigation:** 0 HIGH/CRITICAL vulnerabilities in current repo-level dependencies.
- **Provenance:** Keyless Rekor signing is prepared for CI integration.
- **Integrity Note:** Formally documented the purge of hallucinated data in `docs/release/RC1_INTEGRITY_NOTE.md`.

## 📊 Observability
- **Exporter:** eBPF Prometheus Exporter with live/stub modes.
- **Scrape Path:** Prometheus configuration included in `infra/prometheus.yml`.
- **Artifacts:** All benchmark and security scan results are included in `security/sbom/out/` and `ebpf/prod/results/`.

## 🛠 Toolchain Requirements
- **Go:** 1.24+ (Required for eBPF/5G modules)
- **Python:** 3.12+
- **Kernel:** 6.1+ (Recommended for CO-RE eBPF)

## 📦 Reproducibility & Safety
- **Verification Matrix:** `docs/v1.1/VERIFICATION-MATRIX.md`
- **Cleanup:** `scripts/ebpf_cleanup_safe.sh` for safe datapath teardown.
- **SBOM:** Full SPDX and CycloneDX manifests provided.

---
**x0tta6bl4 Swarm Intelligence**  
*Verification Mode: RC1-STABLE*

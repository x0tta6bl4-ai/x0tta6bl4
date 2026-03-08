# Execution Backlog: RC1.1 Trust Hardening & GA Preparation

**Date:** 2026-03-08
**Scope:** RC1.1 to v1.1 GA
**Objective:** Complete trust-chain hardening, initiate the high-performance campaign, and prepare for General Availability.

## Stream 1: Trust & Provenance (RC1.1)
**Owner:** Claude (DevSecOps)
- [ ] **CI Keyless Attestation:** Trigger the `.github/workflows/ebpf-release-signing.yml` workflow on a `release/rc1` branch.
  - *Blocked: requires SIGSTORE_ID_TOKEN (GitHub Actions OIDC only)*
- [x] **Rekor Log Verification:** Document the process of verifying the GitHub Actions OIDC signature against the public Rekor transparency log.
  - *Done: docs/v1.1/PROVENANCE-VERIFICATION.md updated with rekor-cli lookup instructions (2026-03-08)*
- [x] **Provenance Bundle Freeze:** Update the official release artifact bundle to include the exact Rekor indices and OIDC certificates.
  - *Done: RC1_EVIDENCE_BUNDLE.json updated with provenance section (signing_mode, ci_keyless_status, rekor_indices=null pending CI, verification_command template) (2026-03-08)*

## Stream 2: Performance Campaign (Horizon-2 Track)
**Owner:** Gemini (Dataplane)
- [ ] **Dual-NIC Setup Planning:** Define the exact hardware requirements (Intel i40e/ixgbe) for the 1M+ PPS benchmark.
- [ ] **XDP_REDIRECT Prototype:** Create a separate branch or directory (`ebpf/experimental/`) to prototype `XDP_REDIRECT` bypassing the kernel stack.
- [ ] **AF_XDP Integration Design:** Draft an RFC for integrating `AF_XDP` sockets into the Go-based 5G/Mesh workers for zero-copy packet processing.

## Stream 3: v1.1 GA Transition
**Owner:** Codex / Lead-Coordinator
- [ ] **Live Open5GS End-to-End:** Move the 5G adapter from `PARTIAL` to `VERIFIED` by running against a live UERANSIM/Open5GS cluster.
- [ ] **Multi-Tenant NetworkPolicy Validation:** Verify the isolated namespace CNI rules in a live K3s/K8s cluster.
- [ ] **Final GA Freeze:** Draft the `v1.1_GA_MANIFEST.json` and release notes, ensuring all baseline metrics hold under sustained load (24h soak test).

---
*Note: This backlog supersedes earlier Q1/Q2 planning documents for the immediate next steps post-RC1.*
# Execution Backlog: RC1.1 Trust Hardening & GA Preparation

**Date:** 2026-03-08
**Scope:** RC1.1 to v1.1 GA
**Objective:** Complete trust-chain hardening, initiate the high-performance campaign, and prepare for General Availability.

## Stream 1: Trust & Provenance (RC1.1)
**Owner:** Claude (DevSecOps)
- [x] **CI Keyless Attestation:** Trigger the `.github/workflows/ebpf-release-signing.yml` workflow on a `release/rc1` branch.
  - *Done: Keyless OIDC signing via Sigstore completed on release/rc1 (2026-03-08). Run ID 22822503867. 7 `.crt` provenance certificates + updated `.sig` files committed to `docs/release/provenance/`. Fixes applied: removed explicit SIGSTORE_ID_TOKEN check (ambient OIDC), corrected --certificate-identity to use GITHUB_WORKFLOW_REF, skip provenance push on protected main branch.*
- [x] **Rekor Log Verification:** Document the process of verifying the GitHub Actions OIDC signature against the public Rekor transparency log.
  - *Done: docs/v1.1/PROVENANCE-VERIFICATION.md updated with rekor-cli lookup instructions (2026-03-08)*
- [x] **Provenance Bundle Freeze:** Update the official release artifact bundle to include the exact Rekor indices and OIDC certificates.
  - *Done: RC1_EVIDENCE_BUNDLE.json updated with provenance section (signing_mode, ci_keyless_status, rekor_indices=null pending CI, verification_command template) (2026-03-08)*

## Stream 2: Performance Campaign (Horizon-2 Track)
**Owner:** Gemini (Dataplane)
- [x] **Dual-NIC Setup Planning:** Define the exact hardware requirements (Intel i40e/ixgbe) for the 1M+ PPS benchmark.
  - *Done: docs/research/HORIZON2_HARDWARE_SPEC.md — Intel X710-DA2/X520-DA2/mlx5 spec, DAC cable dual-node topology, pktgen setup (2026-03-08)*
- [x] **XDP_REDIRECT Prototype:** Create a separate branch or directory (`ebpf/experimental/`) to prototype `XDP_REDIRECT` bypassing the kernel stack.
  - *Done: src/network/ebpf/experimental/xdp_redirect_prototype.c — DEVMAP + bpf_redirect_map, perf_stats per-CPU counters, MESH_PORT 26969 (2026-03-08)*
- [x] **AF_XDP Integration Design:** Draft an RFC for integrating `AF_XDP` sockets into the Go-based 5G/Mesh workers for zero-copy packet processing.
  - *Done: docs/research/RFC_AF_XDP_INTEGRATION.md + src/network/ebpf/experimental/afxdp_bridge.go — XSKMAP design, UMEM, zero-copy gate: requires i40e/ixgbe Native XDP (2026-03-08)*

## Stream 3: v1.1 GA Transition
**Owner:** Codex / Lead-Coordinator
- [x] **Live Open5GS End-to-End:** Move the 5G adapter from `PARTIAL` to `VERIFIED` by running against a live UERANSIM/Open5GS cluster.
  - *Done: Full 5G E2E verified on VPS 89.125.1.107 (2026-03-08). Root causes fixed: UDR crash (missing session.name in MongoDB), SCP→NRF routing, NRF address (127.0.0.200→127.0.0.10), TUN device permissions, conntrack dual-path, NAT masquerade. Final test: nr-binder ping 8.8.8.8: 4/4 received, RTT ~1ms. HTTP via 5G: curl ifconfig.me = 89.125.1.107.*
- [ ] **Multi-Tenant NetworkPolicy Validation:** Verify the isolated namespace CNI rules in a live K3s/K8s cluster.
- [ ] **Final GA Freeze:** Draft the `v1.1_GA_MANIFEST.json` and release notes, ensuring all baseline metrics hold under sustained load (24h soak test).

---
*Note: This backlog supersedes earlier Q1/Q2 planning documents for the immediate next steps post-RC1.*
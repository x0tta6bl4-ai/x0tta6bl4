# Release Gate — v1.1

Date: 2026-03-06
Decision basis:

- `bash scripts/verify-v1.1.sh --fast`
- `bash ebpf/prod/verify-local.sh --no-status`
- `bash scripts/agents/check_coordination_contract.sh`

---

## Decision

### Go / No-Go

- `NO-GO` for final defensible sign-off
- `GO` for controlled pre-pilot hardening and operator-driven live validation

This repository is already in a real execution/hardening phase, but not yet at
the point where all public-facing claims can be backed by environment-specific
artifacts.

---

## Verified Here

Current fast verification snapshot:

- `VERIFIED HERE: 13`
- `VERIFIED VIA SCRIPT/CI: 1`
- `NOT VERIFIED YET: 14`
- `FAILED: 0`

The strongest currently verified local facts are:

- config/YAML parsing passes
- CO-RE generation path is wired
- kernel and BTF prerequisites are present
- coordination docs are guarded against drift
- SOC2 evidence docs exist and pass sanity checks
- eBPF benchmark harness runs in plan-only mode without making throughput claims
- eBPF dry-run verification path completes locally with explicit fallback behavior

---

## Blockers

These are the blockers preventing final sign-off:

1. Live XDP attach on a real NIC is not yet verified here.
2. PPS benchmark `>= 5M` is not yet measured.
3. Keyless cosign + Rekor path is not yet evidenced.
4. Live Open5GS transport is not yet evidenced.
5. Live SX1303 HAL binding is not yet evidenced.
6. Docker-backed local validation is unavailable in this environment.
7. Local `helm lint` is blocked by a snap-confined Helm binary in this environment.
8. Local source rebuild of `ebpf/prod` is blocked by `go1.22.2` vs module/tool dependency requiring newer Go; container rebuild path exists but was not run here.

---

## Required Evidence Before Sign-Off

### Required for final eBPF datapath claims

- `sudo -E IFACE=<real-nic> ebpf/prod/verify-local.sh --live-attach`
- clean output with no verifier/kernel rejection
- operator-preserved command log

### Required for throughput claims

- `RUN_BENCH=1 sudo -E IFACE=<real-nic> ebpf/prod/benchmark-harness.sh`
- `ebpf/prod/results/benchmark-<timestamp>.json`
- JSON contains `"pass": true`

### Required for supply-chain attestation claims

- CI keyless run for `security/sbom/verify-cosign-rekor.sh --mode ci-keyless --tool-mode native`
- Rekor log entry or equivalent CI evidence

### Required for chart/runtime claims

- containerized chart render through `charts/render-in-docker.sh`
- cluster-level enforcement checks for multi-tenant isolation

### Required for 5G / LoRa / DP claims

- real Open5GS transport evidence
- real SX1303 HAL evidence
- real DP backend evidence

---

## Public Claim Restrictions

Do not publicly state the following as verified facts yet:

- measured PPS throughput
- `98.5% uptime`
- `1.8s MTTR`
- `94%` GNN accuracy as production validation
- Rekor-attested verification
- production-deployed live Open5GS / SX1303 / DP backend

These remain simulated, blocked, or dependent on separate evidence.

---

## Operator Next Steps

Recommended order:

1. `charts/render-in-docker.sh`
2. `ebpf/prod/build-in-docker.sh`
3. `sudo -E IFACE=eth0 ebpf/prod/verify-local.sh --live-attach`
4. `RUN_BENCH=1 sudo -E IFACE=eth0 ebpf/prod/benchmark-harness.sh`
5. `security/sbom/run-local-sbom-check.sh full --tool-mode docker`
6. `security/sbom/verify-cosign-rekor.sh --mode mock --tool-mode docker`
7. CI keyless signing / Rekor path
8. live Open5GS / SX1303 / DP validation

Until those artifacts exist, this branch should be described as:

`evidence-driven hardening branch with verified local preflight paths and pending live validation`

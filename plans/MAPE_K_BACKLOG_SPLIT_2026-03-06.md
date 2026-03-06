# MAPE-K Backlog Split — 2026-03-06

**Owner:** `lead-coordinator`  
**Purpose:** keep the post-freeze queue separated into what can run now and what
must remain live-validation-only.

## Verification-ready

These tasks are runnable now in the current local environment and may improve
local evidence without requiring real hardware or CI identity.

| Task ID | Agent | Next command | Evidence target |
|---|---|---|---|
| `CLAUDE-RDM-001` | `claude` | `bash charts/render-in-docker.sh` | Helm render output |
| `CLAUDE-RDM-002` | `claude` | `bash security/sbom/run-local-sbom-check.sh full --tool-mode docker` | SBOM + CVE gate result |
| `CLAUDE-RDM-003` | `claude` | `bash security/sbom/verify-cosign-rekor.sh --mode mock --tool-mode docker` | Mock signing output |
| `CODEX-RDM-001` | `codex` | `go test ./edge/5g/... -v` | Focused 5G test output |
| `CODEX-RDM-002` | `codex` | `bash scripts/verify-5g-path.sh` | Updated 5G verify path |
| `COORD-RDM-001` | `lead-coordinator` | `bash scripts/agent-coord.sh roadmap_sync lead-coordinator` | Shared roadmap dispatch sync |

## Live-validation-only

These tasks must not be promoted without fresh machine-readable artifacts from a
real NIC, real endpoint, or privileged environment.

| Task ID | Agent | Next command | Required artifact |
|---|---|---|---|
| `GEMINI-RDM-001` | `gemini` | `sudo -E IFACE=enp8s0 ebpf/prod/verify-local.sh --live-attach` | live attach output + kernel/BPF evidence |
| `GEMINI-RDM-002` | `gemini` | `modprobe pktgen && RUN_BENCH=1 sudo -E IFACE=enp8s0 ebpf/prod/benchmark-harness.sh` | `benchmark-<ts>.json` with measured PPS and `pass=true` |

Rules:

- Do not promote any PPS number without a fresh benchmark artifact.
- Do not reuse older bridge-only or hand-crafted JSON as evidence.
- Keep this bucket separate from the local verification baseline.

## Blocked / Horizon-2

These items remain frozen until release-gate blockers are re-evaluated.

| Task ID | Agent | Status | Condition |
|---|---|---|---|
| `COORD-RDM-002` | `lead-coordinator` | `blocked` | Decentralized RAG stays RFC-only until live gaps are re-evaluated |

## Current rule

If a task can run now without hardware-only or CI-only prerequisites, it stays
in `verification-ready`. If it needs a real NIC, root, lab hardware, or OIDC
identity, it belongs in `live-validation-only`.

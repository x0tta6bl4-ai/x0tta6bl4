# Agent Coordination — x0tta6bl4

**READ THIS FIRST** at the start of every agent session.
Update the machine-readable state through the coordination front door before
session end.

Front door: `scripts/agent-coord.sh`
Compatibility state: `.agent-coord/state.json`
Audit log: `.agent-coord/log.jsonl`
Per-agent inboxes: `.agent-coord/inbox/<name>.jsonl`
Authoritative request thread backend: `.git/swarm/coordination_state.json`

`python3 scripts/agents/run_agent_cycle.py` now mirrors cycle START/HB/END into
this same front door through `scripts/agent-coord.sh`.

---

## How to start a session

```bash
# See global state + your inbox
bash scripts/agent-coord.sh session_start <your-name> "short request summary"

# Example for gemini:
bash scripts/agent-coord.sh session_start gemini "live eBPF attach follow-up"
```

## How to end a session

```bash
bash scripts/agent-coord.sh session_end gemini \
  '{"verified_here": 3, "files_changed": ["ebpf/prod/verify-local.sh"], "next_for_claude": "update hardening-status with live attach result"}'

# Send a message to another agent:
bash scripts/agent-coord.sh send gemini claude "handoff" "see request thread for verified/simulated/not-verified status"
```

---

## Current agent ownership (do not touch each other's scope without checking)

| Agent | Primary scope | Current status |
|-------|--------------|----------------|
| **claude** | `scripts/verify-v1.1.sh`, `docs/verification/`, `compliance/soc2/`, `security/sbom/`, `docs/commercial/`, `docs/STATUS.md` | idle — last session 2026-03-06 |
| **gemini** | `ebpf/prod/`, `edge/5g/ebpf/` | awaiting live attach |
| **codex** | `edge/5g/`, `integration/`, `test/` | awaiting Open5GS transport |

---

## Execution contours

Run each session in exactly one contour:

- `verification` = reproducible checks, tests, renders, evidence updates
- `validation` = live-path checks with root, real NICs, hardware, CI identity, or external endpoints

Examples:

```bash
bash scripts/agent-coord.sh session_start claude --mode verification "refresh evidence state"
bash scripts/agent-coord.sh session_start gemini --mode validation "live XDP attach"
bash scripts/agent-coord.sh next_task codex --mode verification
```

If `--mode` is omitted, the front door uses the current agent's `preferred_mode`
from `plans/ROADMAP_AGENT_QUEUE.json`.

For `validation`, `session_start` now runs a lightweight prereq gate derived
from validation tasks in `plans/ROADMAP_AGENT_QUEUE.json`. If prereqs are
missing, the session does not open unless `--allow-blocked` is passed
explicitly for standby/handoff coordination only.

---

## Evidence rules — ALL agents must follow

```
VERIFIED HERE         = ran this command in this environment, got this output
VERIFIED VIA SCRIPT/CI = script exists, reproducible, not run here
SIMULATED             = code runs but with mock/stub backend
NOT VERIFIED YET      = blocked by hardware/credentials/cluster
```

**Never upgrade a status without the artifact to back it up.**

| Claim | Required artifact |
|-------|------------------|
| live XDP attach verified | `dmesg` + output of `verify-local.sh --live-attach` with no BPF errors |
| PPS throughput verified | `ebpf/prod/results/benchmark-<ts>.json` with `"pass": true` and `"measured_pps"` |
| Rekor-attested | Rekor log index from CI job `release:cosign-attest` |
| Open5GS live | HTTP session log from real Open5GS endpoint |
| SX1303 verified | telemetry dump from real SX1303 gateway |

---

## What must NOT be said publicly yet

- Any PPS throughput figure — no benchmark JSON exists yet
- 98.5% uptime / 1.8s MTTR — simulated, not from production traffic
- 94% GNN accuracy as production metric — training-set figure
- "Rekor-attested" / "transparency-log verified" — no CI-keyless run
- "Production-deployed" for any module
- Field-validated 5G or LoRa performance

---

## Nearest unblocked actions (do these in order)

1. **Verification** (any agent): `charts/render-in-docker.sh` — Docker available, runs now
2. **Verification** (any agent): `security/sbom/run-local-sbom-check.sh full --tool-mode docker`
3. **Verification** (any agent): `security/sbom/verify-cosign-rekor.sh --mode mock --tool-mode docker`
4. **Validation** (`gemini`): `sudo -E IFACE=eth0 ebpf/prod/verify-local.sh --live-attach` (needs root + real NIC)
5. **Validation** (`gemini`): `modprobe pktgen && RUN_BENCH=1 sudo -E IFACE=eth0 ebpf/prod/benchmark-harness.sh`
6. **Verification** (`codex`): `go test ./edge/5g/... -v` then implement real Open5GS transport without upgrading live status

Full runbook: `docs/verification/operator-live-validation-checklist.md`

---

## Quick verify (run at any time to see current local evidence state)

```bash
bash scripts/verify-v1.1.sh --fast
# Review the current summary from this environment; do not rely on stale counts.

bash scripts/agent-coord.sh status
# Shows global coordination state + recent log
```

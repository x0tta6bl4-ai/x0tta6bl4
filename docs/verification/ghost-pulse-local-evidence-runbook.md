# x0tta6bl4_pulse Local Evidence Runbook

Status: `LOCAL_EXPERIMENT_ONLY`

This runbook collects local evidence for the experimental `x0tta6bl4_pulse`
transport without upgrading it to a stealth, whitelist, kernel, or production
claim.

## Commands

Collect a bounded local evidence bundle:

```bash
python3 scripts/ops/collect_ghost_pulse_local_evidence.py --packet-count 24 --mode corporate
```

Collect the same bundle with an unshaped UDP negative control:

```bash
python3 scripts/ops/collect_ghost_pulse_local_evidence.py --packet-count 24 --mode corporate --include-baseline
```

Attempt a real loopback packet capture when `tcpdump` permissions are present:

```bash
python3 scripts/ops/collect_ghost_pulse_local_evidence.py --packet-count 24 --mode corporate --include-baseline --capture-pcap
```

Verify the latest bundle:

```bash
python3 scripts/ops/verify_ghost_pulse_local_evidence.py
```

Replay deterministic seed timing plans from the latest local bundle and matrix:

```bash
python3 scripts/ops/verify_ghost_pulse_rng_replay.py
```

Run the local verification suite and write the latest suite report:

```bash
python3 scripts/ops/run_ghost_pulse_verification_suite.py
```

Verify the latest suite report without re-running command gates:

```bash
python3 scripts/ops/verify_ghost_pulse_verification_suite.py
```

This verifier checks suite JSON/Markdown mirror integrity and confirms the
suite Markdown summary renders from the suite JSON.

Verify the full latest artifact chain read-only:

```bash
python3 scripts/ops/verify_ghost_pulse_artifact_chain.py
```

Optional heuristic profile run:

```bash
python3 scripts/ops/collect_ghost_pulse_local_evidence.py --packet-count 12 --mode whitelist
```

## Evidence Produced

- `docs/verification/ghost-pulse-local-evidence-*/evidence.json`
- `docs/verification/ghost-pulse-local-evidence-*/summary.md`
- `docs/verification/ghost-pulse-local-evidence-*/packet-events.jsonl`
- `docs/verification/ghost-pulse-local-evidence-*/packet-events.csv`
- `docs/verification/ghost-pulse-local-evidence-*/baseline-packet-events.jsonl`
  when `--include-baseline` is used
- `docs/verification/ghost-pulse-local-evidence-*/baseline-packet-events.csv`
  when `--include-baseline` is used
- `docs/verification/ghost-pulse-local-evidence-*/loopback-pulse.pcap`
  when `--capture-pcap` succeeds
- `docs/verification/GHOST_PULSE_LOCAL_EVIDENCE_LATEST.json`
- `docs/verification/GHOST_PULSE_LOCAL_EVIDENCE_LATEST.md`
- `docs/verification/GHOST_PULSE_VERIFICATION_SUITE_LATEST.json`
  when the verification suite is run
- `docs/verification/GHOST_PULSE_VERIFICATION_SUITE_LATEST.md`
  when the verification suite is run
- `docs/verification/ghost-pulse-verification-suite-*/suite.json`
  when the verification suite is run
- `docs/verification/ghost-pulse-verification-suite-*/summary.md`
  when the verification suite is run

## Claim Boundary

Passing this runbook means only:

- local loopback send/receive worked;
- sender-side planned delay telemetry was recorded;
- sender-side deterministic timing fields replay from the recorded seed;
- optional local baseline comparison worked when requested;
- Python and shell syntax gates passed;
- static eBPF artifacts are present;
- read-only kernel inspection was captured.
- when the verification suite is run, latest JSON/Markdown artifacts match
  their timestamped bundle files by SHA256.

Passing this runbook does not mean:

- DPI bypass is proven;
- VK/Yandex/Teams whitelist behavior is proven;
- XDP is attached;
- the protocol is suitable for production use.

Even if read-only tools show a BPF map or program, this runbook still does not
promote kernel attach without an operator tying that evidence to the exact
interface and packet run.

## Required Before Stronger Claims

- operator-captured XDP attach proof for the exact interface;
- `bpftool map dump`/counter evidence tied to packet generation;
- packet captures from before and after attach;
- a reproducible lab with controlled baseline traffic and explicit negative
  controls;
- external review of any claim that references third-party service behavior.

# x0tta6bl4_pulse Profile Matrix Runbook

Status: `LOCAL_EXPERIMENT_ONLY`

This runbook repeats local loopback timing experiments for `x0tta6bl4_pulse`
profiles and compares each run with an unshaped UDP negative control.

## Commands

Run the default bounded matrix:

```bash
python3 scripts/ops/run_ghost_pulse_profile_matrix.py
```

Run a slightly larger local matrix:

```bash
python3 scripts/ops/run_ghost_pulse_profile_matrix.py --packet-count 16 --repetitions 3 --modes corporate whitelist
```

Verify the latest matrix:

```bash
python3 scripts/ops/verify_ghost_pulse_profile_matrix.py
```

Replay deterministic seed timing plans recorded in the latest local bundle and
matrix:

```bash
python3 scripts/ops/verify_ghost_pulse_rng_replay.py
```

Run all latest local pulse verification gates and write a suite report:

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

## Evidence Produced

- `docs/verification/ghost-pulse-profile-matrix-*/matrix.json`
- `docs/verification/ghost-pulse-profile-matrix-*/summary.md`
- `docs/verification/ghost-pulse-profile-matrix-*/matrix-runs.jsonl`
- `docs/verification/GHOST_PULSE_PROFILE_MATRIX_LATEST.json`
- `docs/verification/GHOST_PULSE_PROFILE_MATRIX_LATEST.md`
- `docs/verification/GHOST_PULSE_VERIFICATION_SUITE_LATEST.json`
  when the verification suite is run
- `docs/verification/GHOST_PULSE_VERIFICATION_SUITE_LATEST.md`
  when the verification suite is run
- `docs/verification/ghost-pulse-verification-suite-*/suite.json`
  when the verification suite is run
- `docs/verification/ghost-pulse-verification-suite-*/summary.md`
  when the verification suite is run

## Claim Boundary

Passing this matrix means only:

- repeated local pulse timing runs completed;
- sender-side planned delay telemetry was recorded for each pulse run;
- sender-side deterministic timing digests replay from each row seed;
- repeated unshaped UDP negative controls completed;
- aggregate local timing differences were recorded;
- syntax/static-artifact gates passed.
- when the verification suite is run, latest JSON/Markdown artifacts match
  their timestamped bundle files by SHA256.

Passing this matrix does not mean:

- DPI bypass is proven;
- VK/Yandex/Teams whitelist behavior is proven;
- XDP is attached;
- the protocol is suitable for production use.

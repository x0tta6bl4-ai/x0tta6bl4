# Mesh Operator Release Dry-Run Runbook

## Purpose

This runbook defines a repeatable pre-release dry-run for `mesh-operator` with explicit control checkpoints and an audit report.

## Command

```bash
bash scripts/ops/mesh_operator_release_dry_run.sh
```

Optional flags (env):

```bash
FAIL_FAST=0 RUN_KIND_E2E=0 RUN_WEBHOOK_E2E=0 RUN_LIFECYCLE_E2E=0 RUN_CANARY_ROLLBACK_E2E=0 \
  bash scripts/ops/mesh_operator_release_dry_run.sh
```

## Checkpoints

- `CP-01` Toolchain preflight
- `CP-02` Version contract validation
- `CP-03` Mesh operator unit tests
- `CP-04` Fallback image reproducibility
- `CP-05` Helm lint and webhook render
- `CP-06` Git release promotion dry-run
- `CP-07` Kind smoke e2e
- `CP-08` Webhook admission e2e
- `CP-09` Helm lifecycle e2e
- `CP-10` Canary rollout + rollback e2e

## Evidence Artifacts

Script writes artifacts to `docs/release/`:

- `mesh_operator_release_dry_run_<timestamp>.log`
- `mesh_operator_release_dry_run_<timestamp>.json`
- `mesh_operator_release_dry_run_<timestamp>.md`
- `MESH_OPERATOR_RELEASE_DRY_RUN_LATEST.md`

Use these artifacts as release evidence for dry-run checkpoints.

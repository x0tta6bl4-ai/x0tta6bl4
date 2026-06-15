# x0tta6bl4_pulse External Evidence Intake

Timestamp: `2026-06-15T05:50:40.245210+00:00`

Status: `PASS`

Decision: `EXTERNAL_EVIDENCE_INTAKE_ACTION_REQUIRED`

Preflight: `docs/verification/GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST.json`

## Summary

- replacement_required: `dpi_lab, whitelist_lab, security_review, production_readiness`
- ready: `none`
- not_ready: `dpi_lab, whitelist_lab, security_review, production_readiness`
- missing_candidate_paths: `none`
- currently_ready_write_commands: `0`
- post_import_refresh_commands: `9`
- incoming_examples_status: `PASS`
- incoming_examples_count: `7`
- collection_tasks: `4`

## Collection Tasks

- `dpi_lab`: status `CANDIDATE_REJECTED`, candidate `docs/verification/incoming/dpi_lab.json`, blockers `candidate_validation_failed, preflight_failures_present, external_dpi_proxy_validation_failed`, external_dpi_proxy_validation `FAIL/REJECTED`, collector_command_shape `present`
- `whitelist_lab`: status `CANDIDATE_REJECTED`, candidate `docs/verification/incoming/whitelist_lab.json`, blockers `candidate_validation_failed, preflight_failures_present`, external_dpi_proxy_validation `none`, collector_command_shape `none`
- `security_review`: status `CANDIDATE_REJECTED`, candidate `docs/verification/incoming/security_review.json`, blockers `candidate_validation_failed, preflight_failures_present`, external_dpi_proxy_validation `none`, collector_command_shape `none`
- `production_readiness`: status `CANDIDATE_REJECTED`, candidate `docs/verification/incoming/production_readiness.json`, blockers `candidate_validation_failed, preflight_failures_present`, external_dpi_proxy_validation `none`, collector_command_shape `none`

## Operator Command Shapes

Placeholder values in angle brackets must be filled locally by the operator.
Do not paste target URLs, proxy URLs, operator IDs, authorization scope, or policy context into chat.
External DPI runbook: `docs/verification/ghost-pulse-external-dpi-intake-runbook.md`.

### `dpi_lab`

Safe local runner (preferred):

```bash
python3 scripts/ops/run_external_dpi_intake_local.py --json --write-ready
```

Collector command shape:

```bash
python3 scripts/ops/collect_external_dpi_proxy_reachability_evidence.py --output docs/verification/incoming/dpi_lab.json --artifact-dir docs/verification/incoming/artifacts/dpi_lab --allow-external-probes --target-url '<authorized target URL; local input only>' --treatment-proxy '<authorized proxy URL; local input only>' --operator-or-lab-id '<local operator/lab id; hashed before writing>' --authorization-scope-id '<local authorization scope; hashed before writing>' --scope-summary '<bounded authorized scope>' --network-region-bucket '<coarse region>' --network-type '<authorized lab/field network>' --isp-or-lab-profile '<local ISP/lab profile; hashed before writing>' --egress-location-bucket '<coarse egress>' --policy-context '<authorized policy context>' --json
```

Read-only import check:

```bash
python3 scripts/ops/import_ghost_pulse_external_evidence.py --claim dpi_lab --candidate docs/verification/incoming/dpi_lab.json --require-ready --json
```

Write import command, only after readiness is true:

```bash
python3 scripts/ops/import_ghost_pulse_external_evidence.py --claim dpi_lab --candidate docs/verification/incoming/dpi_lab.json --write --json
```

Acceptance commands:

```bash
python3 scripts/ops/verify_ghost_pulse_external_evidence.py --claim dpi_lab --require-pass --json
```

### `whitelist_lab`

Read-only import check:

```bash
python3 scripts/ops/import_ghost_pulse_external_evidence.py --claim whitelist_lab --candidate docs/verification/incoming/whitelist_lab.json --require-ready --json
```

Write import command, only after readiness is true:

```bash
python3 scripts/ops/import_ghost_pulse_external_evidence.py --claim whitelist_lab --candidate docs/verification/incoming/whitelist_lab.json --write --json
```

Acceptance commands:

```bash
python3 scripts/ops/verify_ghost_pulse_external_evidence.py --claim whitelist_lab --require-pass --json
```

### `security_review`

Read-only import check:

```bash
python3 scripts/ops/import_ghost_pulse_external_evidence.py --claim security_review --candidate docs/verification/incoming/security_review.json --require-ready --json
```

Write import command, only after readiness is true:

```bash
python3 scripts/ops/import_ghost_pulse_external_evidence.py --claim security_review --candidate docs/verification/incoming/security_review.json --write --json
```

Acceptance commands:

```bash
python3 scripts/ops/verify_ghost_pulse_external_evidence.py --claim security_review --require-pass --json
```

### `production_readiness`

Read-only import check:

```bash
python3 scripts/ops/import_ghost_pulse_external_evidence.py --claim production_readiness --candidate docs/verification/incoming/production_readiness.json --require-ready --json
```

Write import command, only after readiness is true:

```bash
python3 scripts/ops/import_ghost_pulse_external_evidence.py --claim production_readiness --candidate docs/verification/incoming/production_readiness.json --write --json
```

Acceptance commands:

```bash
python3 scripts/ops/verify_ghost_pulse_external_evidence.py --claim production_readiness --require-pass --json
```

```bash
python3 scripts/ops/verify_ghost_pulse_proof_gate.py --require-all-proven --json
```


## Claim Boundary

- kernel_attach_verified: `False`
- note: `External evidence intake readiness only; this report does not import evidence or promote proof-gate claims.`
- production_ready: `False`
- stealth_verified: `False`
- whitelist_verified: `False`

## Failures

- None

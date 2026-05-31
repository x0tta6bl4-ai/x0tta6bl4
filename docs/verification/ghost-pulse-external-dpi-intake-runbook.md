# Ghost Pulse External DPI Intake Runbook

Status: `AUTHORIZED_EXTERNAL_EVIDENCE_REQUIRED`

This runbook collects the `dpi_lab` replacement candidate for
`x0tta6bl4_pulse`. It is an operator handoff, not evidence by itself.

## Safe Command

Run the local wrapper from the repository root:

```bash
python3 scripts/ops/run_external_dpi_intake_local.py --json --write-ready
```

The wrapper asks for private values interactively. Do not paste target URLs,
proxy endpoints, operator IDs, authorization scope IDs, ISP/lab profiles,
policy context, tokens, subscriber data, or raw captures into chat.

## Required Local Inputs

- authorized target URL
- optional authorized treatment proxy URL
- operator or lab ID
- authorization scope ID
- bounded scope summary
- coarse network region bucket
- authorized lab or field network type
- ISP or lab profile
- coarse egress location bucket
- policy context

The wrapper passes these values to the collector inside the Python process and
redacts matching local input values from its own JSON report.

## Expected Flow

1. Confirm the prompt with `RUN EXTERNAL DPI PROBES`.
2. Enter the private values locally in the terminal.
3. Let the wrapper run the collector, read-only validator, and read-only import
   preflight.
4. If the import preflight reports `READY_TO_IMPORT`, `--write-ready` imports
   the candidate into `docs/verification/GHOST_PULSE_DPI_LAB_LATEST.json`.
5. If the preflight is not ready, the wrapper exits `ACTION_REQUIRED` and does
   not write proof-gate evidence.

## Acceptance Commands

After a successful write, refresh and verify the chain:

```bash
python3 scripts/ops/verify_ghost_pulse_external_evidence.py --claim dpi_lab --require-pass --json
python3 scripts/ops/verify_ghost_pulse_external_evidence_intake.py --write-report --json
python3 scripts/ops/run_ghost_pulse_verification_suite.py
python3 scripts/ops/run_ghost_pulse_proof_gate.py --json
python3 scripts/ops/verify_ghost_pulse_external_evidence_inventory.py --write-report --json
python3 scripts/ops/verify_ghost_pulse_artifact_chain.py --write-report --json
python3 scripts/ops/verify_ghost_pulse_goal_state.py --write-report --json
```

## Claim Boundary

Passing this runbook can only close `dpi_lab` when the validator and import
preflight both report readiness. It does not close:

- `whitelist_lab`
- `production_readiness`
- `current_runtime_attached`
- customer traffic, anonymity, provider health, or payment finality claims

If the wrapper returns `ACTION_REQUIRED`, keep the current fail-closed gap
record. Do not edit `GHOST_PULSE_DPI_LAB_LATEST.json` by hand to make it
`VERIFIED`.

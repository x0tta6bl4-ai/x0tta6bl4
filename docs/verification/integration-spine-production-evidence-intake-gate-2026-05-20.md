# Integration Spine Production Evidence Intake Gate

Generated: `2026-05-20`
Status: `VERIFIED HERE`

## Scope

The production evidence intake gate validates whether operator-supplied production evidence is ready to replace retained component/local-observation raw evidence for the integration spine.

It is read-only. It does not copy files, contact live systems, submit transactions, mutate NL/SPB/runtime state, or mark the integration objective complete.

## Required Evidence Keys

The gate requires ready production candidates for all five integration-spine evidence keys:

- `external_settlement`
- `live_spire_mtls`
- `multi_host_mesh`
- `paid_client_path`
- `safe_rollout_rollback`

## Required Inputs

- `.tmp/validation-shards/integration-spine-evidence-source-candidate-audit-current.json`
- `.tmp/validation-shards/integration-spine-production-evidence-import-current.json`
- `.tmp/validation-shards/production-raw-evidence-readiness-current.json`

## Current Result

Current decision:

- `BLOCKED_OPERATOR_EVIDENCE_REQUIRED`

Current state:

- raw operator bundle syntax ready: `true`
- raw readiness files ready: `63/63`
- required evidence keys ready: `0/5`
- production import ready: `false`
- source candidate gate ready: `false`

Pending evidence keys:

- `external_settlement`
- `live_spire_mtls`
- `multi_host_mesh`
- `paid_client_path`
- `safe_rollout_rollback`

Current generated report:

- `.tmp/validation-shards/integration-spine-production-evidence-intake-current.json`

## Verified Commands

```bash
python3 -m py_compile src/integration/production_evidence_intake.py tests/unit/test_integration_production_evidence_intake.py
pytest tests/unit/test_integration_production_evidence_intake.py tests/unit/test_integration_evidence_readiness.py tests/unit/test_integration_rollout_provenance.py tests/unit/test_integration_external_settlement.py tests/unit/test_integration_completion_audit.py tests/unit/test_integration_spine.py -q --no-cov
python3 -m src.integration.production_evidence_intake --root . --require-ready
```

The `--require-ready` command is expected to return exit code `2` until all five required evidence keys have ready production source candidates and the production import gate accepts them.

# Integration Spine Source-Candidate Audit

Generated: `2026-05-20T22:21:06Z`

Status: `VERIFIED HERE`

## Scope

`src.integration.evidence_source_candidates` rebuilds the source-candidate audit consumed by the production evidence intake gate.

It is read-only. It does not collect live evidence, copy operator bundle files, contact RPC providers or clusters, mutate NL/SPB/runtime state, or mark the integration objective complete.

## Current Decision

`NO_PRODUCTION_SOURCE_CANDIDATES_OPERATOR_REQUIRED`

Current summary:

- `required_inputs_ready`: `0`
- `required_inputs_total`: `10`
- `ready_source_candidates_total`: `0`
- `routes_ready_to_install`: `0`
- `routes_partial_or_blocked`: `10`

## Required Evidence Keys

- `billing-provisioning`
- `ebpf-observability`
- `external_settlement`
- `live_spire_mtls`
- `multi_host_mesh`
- `paid_client_path`
- `safe_rollout_rollback`
- `signed-release-provenance`
- `sla-telemetry`
- `stable-deploy`

## Why Current Files Are Rejected

The current operator bundle files are structurally usable JSON, but they are not production source candidates because they still include one or more of:

- missing `production_ready: true`
- non-empty `production_promotion_blockers`
- local, test, staging, contract-validation, production-like, or component-verification context
- open semantic blockers in `.tmp/validation-shards/integration-spine-semantic-production-blocker-queue-current.json`

Current operator bundle identity is clean:

- `files_clean`: `63`
- `manifest_identity_mismatches_total`: `0`
- `collector_id_mismatches`: `0`
- `raw_id_mismatches`: `0`
- `files_needing_identity_update`: `0`

The external settlement route is also blocked because the retained submitted transaction receipt is missing and live Base RPC verification is not ready.

## Verification

Commands run here:

```bash
python3 -m py_compile src/integration/evidence_source_candidates.py tests/unit/test_integration_evidence_source_candidates.py
pytest tests/unit/test_integration_evidence_source_candidates.py -q --no-cov
python3 -m src.integration.evidence_source_candidates --root . --output-json .tmp/validation-shards/integration-spine-evidence-source-candidate-audit-current.json
python3 -m src.integration.evidence_source_candidates --root . --require-ready
```

Expected current `--require-ready` result: exit code `2`, because no production source candidate is ready yet.

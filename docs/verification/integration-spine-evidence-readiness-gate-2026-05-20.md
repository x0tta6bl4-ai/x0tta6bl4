# Integration Spine Evidence Readiness Gate

Generated: `2026-05-20`
Status: `VERIFIED HERE`

## Scope

The evidence readiness gate validates two production closeout surfaces:

- retained raw evidence inventory
- semantic production blocker queue

It is read-only. It does not create production evidence, mutate runtime state, contact external systems, or mark the integration objective complete.

## Evidence Contract

Required retained inputs:

- `.tmp/validation-shards/integration-spine-raw-evidence-inventory-current.json`
- `.tmp/validation-shards/integration-spine-semantic-production-blocker-queue-current.json`

Raw evidence is ready only when:

- every expected raw file is installed
- every raw file has `VERIFIED HERE` evidence status
- `template_only_files` is `0`
- `fake_or_simulated_files` is `0`
- `usable_for_goal_completion_files` equals `files_total`
- `semantic_blockers_total` is `0`
- every record classification is `PRODUCTION_GRADE`

Semantic blocker queue is ready only when:

- `completion_decision` is `COMPLETE`
- `goal_can_be_marked_complete` is `true`
- `blocking_items_total` is `0`
- `semantic_preflight_errors_total` is `0`
- `collector_groups_blocking` is `0`
- `current_external_settlement_ready` is `true`

## Current Result

Current decision:

- `BLOCKED_ON_PRODUCTION_EVIDENCE`

Current blockers:

- raw files total: `30`
- raw files usable for goal completion: `0`
- raw semantic blockers total: `70`
- semantic blocking items total: `71`
- semantic preflight errors total: `70`
- external settlement ready in semantic queue: `false`

Current generated report:

- `.tmp/validation-shards/integration-spine-evidence-readiness-current.json`

## Verified Commands

```bash
python3 -m py_compile src/integration/evidence_readiness.py tests/unit/test_integration_evidence_readiness.py
pytest tests/unit/test_integration_evidence_readiness.py tests/unit/test_integration_rollout_provenance.py tests/unit/test_integration_external_settlement.py tests/unit/test_integration_completion_audit.py tests/unit/test_integration_spine.py -q --no-cov
python3 -m src.integration.evidence_readiness --root . --require-ready
```

The `--require-ready` command is expected to return exit code `2` until retained raw evidence is production-grade and the semantic blocker queue is empty.

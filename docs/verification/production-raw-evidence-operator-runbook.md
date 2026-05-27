# Production Raw Evidence Operator Runbook

This runbook is not production evidence. It lists the operator inputs required
before the production raw-evidence gates can pass.

## Required Steps

1. Capture production JSON for every file listed in `.tmp/validation-shards/production-raw-evidence-intake-manifest-current.json`.
2. Set `status` and `evidence_status` to `VERIFIED HERE` only for commands actually run in the production environment.
3. Include `collected_at`, `collected_by`, and non-placeholder `source_commands` for every raw file.
4. Set `production_ready=true` and `production_promotion_blockers=[]` only when the file is production-context evidence, not local, staging, dry-run, template, or simulated evidence.
5. Import the bundle with:

```bash
python3 scripts/ops/import_production_raw_evidence_bundle.py \
  --bundle-root .tmp/production-raw-evidence-operator-bundle \
  --require-ready
```

6. Rerun:

```bash
python3 -m src.integration.production_raw_evidence_readiness --root . --require-ready
python3 -m src.integration.production_raw_evidence_semantics --root . --require-ready
python3 -m src.integration.production_raw_evidence_pipeline --root . --require-ready
python3 scripts/ops/audit_production_grade_goal.py --require-complete
python3 -m src.integration.completion_audit --root . --require-complete
```

The expected current state before operator replacement is fail-closed, not
complete.

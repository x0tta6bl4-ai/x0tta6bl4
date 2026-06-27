# Live Rollout Image Digest Provenance Gate

Generated: `2026-05-21T06:49:50Z`
Decision: `CANNOT_CLOSE_WITH_CURRENT_RETAINED_ARTIFACTS`
Operator handoff: `LIVE_ROLLOUT_IMAGE_DIGESTS_BLOCKED_ON_OPERATOR`
Ready for completion rerun: `False`
Goal can be marked complete: `False`

## Summary

- can close image digests blocker: `False`
- raw deploy images digest pinned: `0/7`
- provenance deploy images digest pinned: `0/7`
- runtime image provenance retained here: `False`
- operator actions: `5`
- operator command entrypoints missing: `0`
- operator command surface ready: `True`

## Missing Inputs

- `live_rollout_image_digest_provenance`: `OPERATOR_INPUT_REQUIRED` - runtime/deploy image references must be digest-pinned and backed by retained per-image cosign/SLSA provenance artifacts
  - command: `python3 scripts/ops/scaffold_live_rollout_image_provenance_evidence.py --write-template-files --force`
  - command: `python3 scripts/ops/verify_live_rollout_evidence_gate.py --require-ready`
  - command: `python3 -m src.integration.rollout_provenance --root . --raw-image-digests .tmp/live-rollout-raw-evidence/image-digests.json --provenance-gate .tmp/validation-shards/deploy-image-provenance-gate-current.json --require-ready`
  - command: `python3 -m src.integration.current_evidence_rollup --root . --require-complete`

## Operator Command Checks

- `render_template_pack`: `READY`, entrypoint exists: `True`
- `verify_live_rollout_evidence_gate`: `READY`, entrypoint exists: `True`
- `rerun_rollout_provenance`: `READY`, entrypoint exists: `True`
- `rerun_current_evidence_rollup`: `READY`, entrypoint exists: `True`

## Required Next Evidence

- digest-pinned Helm/ArgoCD/Kustomize deployment refs for every x0tta6bl4 runtime image
- retained per-image cosign/SLSA provenance artifacts for current deployed image digests
- rerun rollout provenance gate after replacing tag-based runtime image refs

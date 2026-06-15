# x0tta6bl4_pulse Goal State

Status: `FAIL`

Decision: `GHOST_PULSE_GOAL_STATE_INVALID`

## Starter Verified Claims
- `packet_capture, baseline_timing_comparison`

## Pending External Evidence
- `dpi_lab` -> `docs/verification/incoming/dpi_lab.json`; proof `INVALID`; errors `14`; current `INCOMPLETE`; blockers `proof_status_not_verified, proof_errors_present, replacement_not_ready, intake_not_ready, current_evidence_not_verified`
- `whitelist_lab` -> `docs/verification/incoming/whitelist_lab.json`; proof `INVALID`; errors `14`; current `INCOMPLETE`; blockers `proof_status_not_verified, proof_errors_present, replacement_not_ready, intake_not_ready, current_evidence_not_verified`
- `security_review` -> `docs/verification/incoming/security_review.json`; proof `INVALID`; errors `13`; current `INCOMPLETE`; blockers `proof_status_not_verified, proof_errors_present, replacement_not_ready, intake_not_ready, current_evidence_not_verified`
- `production_readiness` -> `docs/verification/incoming/production_readiness.json`; proof `INVALID`; errors `16`; current `INCOMPLETE`; blockers `proof_status_not_verified, proof_errors_present, replacement_not_ready, intake_not_ready, current_evidence_not_verified`

## Pending Runtime Claims
- `current_runtime_attached`

## Claim Boundary
- current_runtime_attached: `False`
- kernel_attach_verified: `True`
- production_ready: `False`
- stealth_verified: `False`
- whitelist_verified: `False`

## Source Reports
- artifact_chain: `docs/verification/GHOST_PULSE_ARTIFACT_CHAIN_LATEST.json`; sha256 `e99430906a0f90e90f0beb8cfb901e5421771b4c93a3bb5ea828095949e4258f`; decision `GHOST_PULSE_ARTIFACT_CHAIN_INCOMPLETE`
- external_evidence_intake: `docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INTAKE_LATEST.json`; sha256 `50117cb05189e64e458242ea215b0d1fb7d72ba1878afb378bd44692aaa30122`; decision `EXTERNAL_EVIDENCE_INTAKE_ACTION_REQUIRED`
- external_evidence_inventory: `docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INVENTORY_LATEST.json`; sha256 `4fbaf324e44824f901a2c5959a4c5faa00ff10daaa8418bb5198635ab3c3a726`; decision `EXTERNAL_EVIDENCE_INVENTORY_INCOMPLETE`
- incoming_examples_manifest: `docs/verification/incoming/examples/manifest.json`; sha256 `791beedf73034354b3beccf41a0adb1bf2a17bb2722588c8d46077ab77b1628f`; decision `None`
- proof: `docs/verification/GHOST_PULSE_PROOF_GATE_LATEST.json`; sha256 `8eea87c9783c4abeda4f22b15d7b8c2fe652052f57b76b415f031824d908460c`; decision `GHOST_PULSE_PROOF_INCOMPLETE`
- replacement_candidates: `docs/verification/GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST.json`; sha256 `75e8f5f8b782a7ff0380207b7315510c774bdb055abf99242c6e4de811a53cc6`; decision `REPLACEMENT_CANDIDATES_NOT_READY`

## Failures
- artifact_chain: non-closure claim must not be pending
- proof.not_verified_yet must match pending external/runtime claims
- external_evidence_inventory.status must be PASS
- external_evidence_inventory.failures must be empty
- external_evidence_inventory.inventory_status must be EXTERNAL_EVIDENCE_INVENTORY_COMPLETE_WITH_GAPS
- artifact_chain.decision must be GHOST_PULSE_ARTIFACT_CHAIN_VERIFIED
- artifact_chain.failures must be empty

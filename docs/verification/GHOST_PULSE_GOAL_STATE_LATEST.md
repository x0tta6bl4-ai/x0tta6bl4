# x0tta6bl4_pulse Goal State

Status: `PASS`

Decision: `GHOST_PULSE_GOAL_STATE_GAPS_RECORDED_FAIL_CLOSED`

## Starter Verified Claims
- `packet_capture, baseline_timing_comparison`

## Pending External Evidence
- `dpi_lab` -> `docs/verification/incoming/dpi_lab.json`; proof `INVALID`; errors `14`; current `INCOMPLETE`; blockers `proof_status_not_verified, proof_errors_present, replacement_not_ready, intake_not_ready, current_evidence_not_verified`
- `whitelist_lab` -> `docs/verification/incoming/whitelist_lab.json`; proof `INVALID`; errors `14`; current `INCOMPLETE`; blockers `proof_status_not_verified, proof_errors_present, replacement_not_ready, intake_not_ready, current_evidence_not_verified`
- `security_review` -> `docs/verification/incoming/security_review.json`; proof `INVALID`; errors `13`; current `INCOMPLETE`; blockers `proof_status_not_verified, proof_errors_present, replacement_not_ready, intake_not_ready, current_evidence_not_verified`
- `production_readiness` -> `docs/verification/incoming/production_readiness.json`; proof `INVALID`; errors `16`; current `INCOMPLETE`; blockers `proof_status_not_verified, proof_errors_present, replacement_not_ready, intake_not_ready, current_evidence_not_verified`

## Claim Boundary
- kernel_attach_verified: `True`
- production_ready: `False`
- stealth_verified: `False`
- whitelist_verified: `False`

## Source Reports
- artifact_chain: `docs/verification/GHOST_PULSE_ARTIFACT_CHAIN_LATEST.json`; sha256 `c91b7a15026b700d3c18f08c251ab325602aa085ad6c3906ccad2444a20db5e9`; decision `GHOST_PULSE_ARTIFACT_CHAIN_VERIFIED`
- external_evidence_intake: `docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INTAKE_LATEST.json`; sha256 `4b9bdd7b7ab92d97271b9357e1147b58dbd753b2e3eb7b055e0eb930ff1d3e13`; decision `EXTERNAL_EVIDENCE_INTAKE_ACTION_REQUIRED`
- external_evidence_inventory: `docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INVENTORY_LATEST.json`; sha256 `f4256ee4492c5825d44804aa89413525e6c8e26ca8789799920812ba360d1092`; decision `EXTERNAL_EVIDENCE_INVENTORY_COMPLETE_WITH_GAPS`
- incoming_examples_manifest: `docs/verification/incoming/examples/manifest.json`; sha256 `f3fe1085c595f098473b641b68132dc56a859952e184e68a5d6618c3a7253217`; decision `None`
- proof: `docs/verification/GHOST_PULSE_PROOF_GATE_LATEST.json`; sha256 `6f3689f64f43ed59142182275514f70358cec315d98cbe3ee6c24a4854be3a72`; decision `GHOST_PULSE_PROOF_INCOMPLETE`
- replacement_candidates: `docs/verification/GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST.json`; sha256 `f7cc7ebb57762cae23debf99ff714c7b91e8f2d0827ad24193f74f12ae7bd0bb`; decision `REPLACEMENT_CANDIDATES_NOT_READY`

## Failures
- None

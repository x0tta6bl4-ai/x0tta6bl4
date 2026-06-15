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

## Pending Runtime Claims
- `current_runtime_attached`

## Claim Boundary
- current_runtime_attached: `False`
- kernel_attach_verified: `True`
- production_ready: `False`
- stealth_verified: `False`
- whitelist_verified: `False`

## Source Reports
- artifact_chain: `docs/verification/GHOST_PULSE_ARTIFACT_CHAIN_LATEST.json`; sha256 `035a2ff8cec60879805268fe58b36ffef3bc40f1f98f912c48fcdb97d7375529`; decision `GHOST_PULSE_ARTIFACT_CHAIN_VERIFIED`
- external_evidence_intake: `docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INTAKE_LATEST.json`; sha256 `b7dce847f465d37b8c6b0ca2f4a3d30e80b30c6b540f76e918a6f35c58dad1c8`; decision `EXTERNAL_EVIDENCE_INTAKE_ACTION_REQUIRED`
- external_evidence_inventory: `docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INVENTORY_LATEST.json`; sha256 `364684644a19df5af1097da62e92f4ca8c8ca103ffd927255ddeb4e815c1be90`; decision `EXTERNAL_EVIDENCE_INVENTORY_COMPLETE_WITH_GAPS`
- incoming_examples_manifest: `docs/verification/incoming/examples/manifest.json`; sha256 `791beedf73034354b3beccf41a0adb1bf2a17bb2722588c8d46077ab77b1628f`; decision `None`
- proof: `docs/verification/GHOST_PULSE_PROOF_GATE_LATEST.json`; sha256 `dd4224333a7809a3f836d64b89258b40116528b6cab80d86a3fcaabe999d6a07`; decision `GHOST_PULSE_PROOF_INCOMPLETE`
- replacement_candidates: `docs/verification/GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST.json`; sha256 `510f178d43ee398e4e8a88b55ac02f48371dc1be37cba196db5e41c973ee77d0`; decision `REPLACEMENT_CANDIDATES_NOT_READY`

## Failures
- None

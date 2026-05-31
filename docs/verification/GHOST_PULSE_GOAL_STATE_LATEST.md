# x0tta6bl4_pulse Goal State

Status: `PASS`

Decision: `GHOST_PULSE_GOAL_STATE_GAPS_RECORDED_FAIL_CLOSED`

## Starter Verified Claims
- `packet_capture, baseline_timing_comparison`

## Pending External Evidence
- `dpi_lab` -> `docs/verification/incoming/dpi_lab.json`; proof `INVALID`; errors `14`; current `INCOMPLETE`; blockers `proof_status_not_verified, proof_errors_present, replacement_not_ready, intake_not_ready, current_evidence_not_verified`
- `whitelist_lab` -> `docs/verification/incoming/whitelist_lab.json`; proof `INVALID`; errors `14`; current `INCOMPLETE`; blockers `proof_status_not_verified, proof_errors_present, replacement_not_ready, intake_not_ready, current_evidence_not_verified`
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
- artifact_chain: `docs/verification/GHOST_PULSE_ARTIFACT_CHAIN_LATEST.json`; sha256 `d47abdfb8869bc03d8a59229a16b6f752ea823761be5e9148ca2c28b6aa7d86e`; decision `GHOST_PULSE_ARTIFACT_CHAIN_VERIFIED`
- external_evidence_intake: `docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INTAKE_LATEST.json`; sha256 `cd9def77d50bd853238a727f13f83dbc72b65e3551cb952cfb1cc2ba8311c76e`; decision `EXTERNAL_EVIDENCE_INTAKE_ACTION_REQUIRED`
- external_evidence_inventory: `docs/verification/GHOST_PULSE_EXTERNAL_EVIDENCE_INVENTORY_LATEST.json`; sha256 `96a13d35f53d41b7db84fd89a23474b53ed31e79f174aff3e593ca407cc4a024`; decision `EXTERNAL_EVIDENCE_INVENTORY_COMPLETE_WITH_GAPS`
- incoming_examples_manifest: `docs/verification/incoming/examples/manifest.json`; sha256 `791beedf73034354b3beccf41a0adb1bf2a17bb2722588c8d46077ab77b1628f`; decision `None`
- proof: `docs/verification/GHOST_PULSE_PROOF_GATE_LATEST.json`; sha256 `035e9d9eed970f0e674002ea134d7f4572fa23dcfb2bcd187c6566b2a1f8edd6`; decision `GHOST_PULSE_PROOF_INCOMPLETE`
- replacement_candidates: `docs/verification/GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST.json`; sha256 `5fa35c138ecdb73355c5ff9e47a33bd0e380e90e06c9c90f50cc170263dea3b9`; decision `REPLACEMENT_CANDIDATES_NOT_READY`

## Failures
- None

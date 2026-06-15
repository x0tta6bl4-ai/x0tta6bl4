# x0tta6bl4_pulse Proof Gate

Timestamp: `2026-06-15T05:59:16.174046+00:00`

Decision: `GHOST_PULSE_PROOF_INCOMPLETE`

## Claim Boundary

- current_runtime_attached: `False`
- kernel_attach_verified: `True`
- production_ready: `False`
- stealth_verified: `False`
- whitelist_verified: `False`

## Replacement Candidate Preflight

- report: `docs/verification/GHOST_PULSE_REPLACEMENT_CANDIDATES_LATEST.json`
- sha256: `510f178d43ee398e4e8a88b55ac02f48371dc1be37cba196db5e41c973ee77d0`
- status: `PASS`
- decision: `REPLACEMENT_CANDIDATES_NOT_READY`
- not_ready: `dpi_lab, whitelist_lab, security_review, production_readiness`

## Proof Rows

| Claim | Status | Evidence |
| --- | --- | --- |
| local_timing_replay | `VERIFIED` | `docs/verification/GHOST_PULSE_VERIFICATION_SUITE_LATEST.json` |
| false_claim_hygiene | `VERIFIED` | `docs/verification/GHOST_PULSE_VERIFICATION_SUITE_LATEST.json` |
| artifact_chain | `VERIFIED` | `docs/verification/GHOST_PULSE_VERIFICATION_SUITE_LATEST.json` |
| kernel_attach | `VERIFIED` | `docs/verification/GHOST_PULSE_KERNEL_ATTACH_LATEST.json` |
| packet_capture | `VERIFIED` | `docs/verification/GHOST_PULSE_PACKET_CAPTURE_LATEST.json` |
| baseline_timing_comparison | `VERIFIED` | `docs/verification/GHOST_PULSE_BASELINE_COMPARISON_LATEST.json` |
| dpi_lab | `INVALID` | `docs/verification/GHOST_PULSE_DPI_LAB_LATEST.json` |
| whitelist_lab | `INVALID` | `docs/verification/GHOST_PULSE_WHITELIST_LAB_LATEST.json` |
| security_review | `INVALID` | `docs/verification/GHOST_PULSE_SECURITY_REVIEW_LATEST.json` |
| production_readiness | `INVALID` | `docs/verification/GHOST_PULSE_PRODUCTION_READINESS_LATEST.json` |
| current_runtime_attached | `INVALID` | `READ_ONLY_KERNEL_OBSERVATION:unconfigured` |

## Missing Or Invalid Evidence

- dpi_lab
- whitelist_lab
- security_review
- production_readiness
- current_runtime_attached

## Failures

- dpi_lab: status must be VERIFIED
- dpi_lab: mode must not be EXTERNAL_EVIDENCE_GAP_RECORD
- dpi_lab: missing_inputs must be absent or empty for VERIFIED evidence
- dpi_lab: failures must be absent or empty for VERIFIED evidence
- dpi_lab: claim_boundary.claim_verified must not be false for VERIFIED evidence
- dpi_lab: required artifact role missing: lab_scope
- dpi_lab: required artifact role missing: baseline_result
- dpi_lab: required artifact role missing: pulse_result
- dpi_lab: required artifact role missing: lab_conclusion
- dpi_lab: measurements.authorized_lab must be True
- dpi_lab: measurements.baseline_detected_or_blocked must be True
- dpi_lab: measurements.pulse_result_recorded must be True
- dpi_lab: measurements.dpi_bypass_verified must be True
- dpi_lab: artifact role missing for content check: lab_conclusion
- whitelist_lab: status must be VERIFIED
- whitelist_lab: mode must not be EXTERNAL_EVIDENCE_GAP_RECORD
- whitelist_lab: missing_inputs must be absent or empty for VERIFIED evidence
- whitelist_lab: failures must be absent or empty for VERIFIED evidence
- whitelist_lab: claim_boundary.claim_verified must not be false for VERIFIED evidence
- whitelist_lab: required artifact role missing: provider_or_lab_authorization
- whitelist_lab: required artifact role missing: provider_profile
- whitelist_lab: required artifact role missing: third_party_baseline_capture
- whitelist_lab: required artifact role missing: whitelist_conclusion
- whitelist_lab: measurements.authorized_provider_or_lab must be True
- whitelist_lab: measurements.provider_profile must be nonempty
- whitelist_lab: measurements.third_party_baseline_captured must be True
- whitelist_lab: measurements.whitelist_behavior_verified must be True
- whitelist_lab: artifact role missing for content check: whitelist_conclusion
- security_review: status must be VERIFIED
- security_review: mode must not be EXTERNAL_EVIDENCE_GAP_RECORD
- security_review: missing_inputs must be absent or empty for VERIFIED evidence
- security_review: failures must be absent or empty for VERIFIED evidence
- security_review: claim_boundary.claim_verified must not be false for VERIFIED evidence
- security_review: required artifact role missing: reviewer_identity
- security_review: required artifact role missing: review_scope
- security_review: required artifact role missing: findings_report
- security_review: measurements.reviewer must be nonempty
- security_review: measurements.scope_includes_pulse_transport must be True
- security_review: measurements.open_critical_findings must be 0
- security_review: measurements.open_high_findings must be 0
- security_review: artifact role missing for content check: findings_report
- production_readiness: status must be VERIFIED
- production_readiness: mode must not be EXTERNAL_EVIDENCE_GAP_RECORD
- production_readiness: missing_inputs must be absent or empty for VERIFIED evidence
- production_readiness: failures must be absent or empty for VERIFIED evidence
- production_readiness: claim_boundary.claim_verified must not be false for VERIFIED evidence
- production_readiness: required artifact role missing: operator_approval
- production_readiness: required artifact role missing: rollback_plan
- production_readiness: required artifact role missing: monitoring_plan
- production_readiness: required artifact role missing: prior_claim_references
- production_readiness: measurements.production_ready must be bool_true
- production_readiness: measurements.rollback_plan_verified must be True
- production_readiness: measurements.monitoring_plan_verified must be True
- production_readiness: measurements.operator_approval_recorded must be True
- production_readiness: measurements.all_prior_claims_referenced must be True
- production_readiness: artifact role missing for content check: prior_claim_references
- production_readiness: references must be a non-empty list
- current_runtime_attached: current runtime interface not configured; set GHOST_PULSE_RUNTIME_INTERFACE or pass --runtime-interface

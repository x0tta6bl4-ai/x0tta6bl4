# x0tta6bl4_pulse External Evidence Gap Audit

Timestamp: `2026-06-15T06:45:59.066714+00:00`

Status: `EXTERNAL_EVIDENCE_ACTION_REQUIRED`

## Claim Boundary

- kernel_attach_verified: `False`
- note: `Gap audit only; proof-gate claim boundaries are not upgraded by this report.`
- production_ready: `False`
- stealth_verified: `False`
- whitelist_verified: `False`

## Rows

| Claim | Status | Replacement Required | Evidence |
| --- | --- | --- | --- |
| kernel_attach | `VERIFIED` | `False` | `docs/verification/GHOST_PULSE_KERNEL_ATTACH_LATEST.json` |
| packet_capture | `VERIFIED` | `False` | `docs/verification/GHOST_PULSE_PACKET_CAPTURE_LATEST.json` |
| baseline_timing_comparison | `VERIFIED` | `False` | `docs/verification/GHOST_PULSE_BASELINE_COMPARISON_LATEST.json` |
| dpi_lab | `INVALID` | `True` | `docs/verification/GHOST_PULSE_DPI_LAB_LATEST.json` |
| whitelist_lab | `INVALID` | `True` | `docs/verification/GHOST_PULSE_WHITELIST_LAB_LATEST.json` |
| security_review | `INVALID` | `True` | `docs/verification/GHOST_PULSE_SECURITY_REVIEW_LATEST.json` |
| production_readiness | `INVALID` | `True` | `docs/verification/GHOST_PULSE_PRODUCTION_READINESS_LATEST.json` |

## Next Actions

- dpi_lab: Replace the gap record with an authorized DPI-lab evidence file containing baseline detect-or-block output, pulse output, lab identity, artifact hashes, and a verified conclusion.
- whitelist_lab: Replace the gap record with authorized provider or lab evidence for provider profile, third-party baseline capture, and verified whitelist-behavior result.
- security_review: Replace the gap record with a completed security review covering pulse transport and showing zero open critical and high findings.
- production_readiness: Replace the gap record only after all prior proof rows are referenced by an operator approval record with verified rollback and monitoring plans.

## Blocking Audit

- kernel_attach: `CLEAR`; categories: `none`
- packet_capture: `CLEAR`; categories: `none`
- baseline_timing_comparison: `CLEAR`; categories: `none`
- dpi_lab: `BLOCKED`; categories: `artifact_roles, measurements, missing_inputs, proof_errors, record`
- whitelist_lab: `BLOCKED`; categories: `artifact_roles, measurements, missing_inputs, proof_errors, record`
- security_review: `BLOCKED`; categories: `artifact_roles, measurements, missing_inputs, proof_errors, record`
- production_readiness: `BLOCKED`; categories: `artifact_roles, measurements, missing_inputs, proof_errors, record, references`

## Evidence Records

- kernel_attach: `PASS`; status: `VERIFIED`; mode: `READ_ONLY_KERNEL_OBSERVATION`; missing inputs present: `False`; failures: `none`
- packet_capture: `PASS`; status: `VERIFIED`; mode: `LOCAL_LOOPBACK_INSTRUMENTED_PCAP`; missing inputs present: `False`; failures: `none`
- baseline_timing_comparison: `PASS`; status: `VERIFIED`; mode: `LOCAL_LOOPBACK_BASELINE_VS_PULSE`; missing inputs present: `False`; failures: `none`
- dpi_lab: `FAIL`; status: `INCOMPLETE`; mode: `EXTERNAL_EVIDENCE_GAP_RECORD`; missing inputs present: `True`; failures: `status must be VERIFIED; mode must not be EXTERNAL_EVIDENCE_GAP_RECORD; missing_inputs must be absent or empty; failures must be absent or empty; claim_boundary.claim_verified must not be false`
- whitelist_lab: `FAIL`; status: `INCOMPLETE`; mode: `EXTERNAL_EVIDENCE_GAP_RECORD`; missing inputs present: `True`; failures: `status must be VERIFIED; mode must not be EXTERNAL_EVIDENCE_GAP_RECORD; missing_inputs must be absent or empty; failures must be absent or empty; claim_boundary.claim_verified must not be false`
- security_review: `FAIL`; status: `INCOMPLETE`; mode: `EXTERNAL_EVIDENCE_GAP_RECORD`; missing inputs present: `True`; failures: `status must be VERIFIED; mode must not be EXTERNAL_EVIDENCE_GAP_RECORD; missing_inputs must be absent or empty; failures must be absent or empty; claim_boundary.claim_verified must not be false`
- production_readiness: `FAIL`; status: `INCOMPLETE`; mode: `EXTERNAL_EVIDENCE_GAP_RECORD`; missing inputs present: `True`; failures: `status must be VERIFIED; mode must not be EXTERNAL_EVIDENCE_GAP_RECORD; missing_inputs must be absent or empty; failures must be absent or empty; claim_boundary.claim_verified must not be false`

## Commands

- kernel_attach: `PASS`; missing commands: `none`; failed commands: `none`
- packet_capture: no exact command set required
- baseline_timing_comparison: no exact command set required
- dpi_lab: no exact command set required
- whitelist_lab: no exact command set required
- security_review: no exact command set required
- production_readiness: no exact command set required

## Artifact Files

- kernel_attach: `PASS`; all artifact files match recorded hashes
- packet_capture: `PASS`; all artifact files match recorded hashes
- baseline_timing_comparison: `PASS`; all artifact files match recorded hashes
- dpi_lab: `PASS`; all artifact files match recorded hashes
- whitelist_lab: `PASS`; all artifact files match recorded hashes
- security_review: `PASS`; all artifact files match recorded hashes
- production_readiness: `PASS`; all artifact files match recorded hashes

## Artifact Roles

- kernel_attach: `PASS`; observed roles: `kernel_commands, kernel_measurements, kernel_interface_scan, kernel_candidate_audit, kernel_object_preflight`; missing roles: `none`; duplicate roles: `none`; required roles without path: `none`; reused required paths: `none`; path scope errors: `none`
- packet_capture: `PASS`; observed roles: `sender_pcap, receiver_pcap, sender_events, receiver_events, capture_summary`; missing roles: `none`; duplicate roles: `none`; required roles without path: `none`; reused required paths: `none`; path scope errors: `none`
- baseline_timing_comparison: `PASS`; observed roles: `baseline_events, pulse_events, timing_comparison`; missing roles: `none`; duplicate roles: `none`; required roles without path: `none`; reused required paths: `none`; path scope errors: `none`
- dpi_lab: `FAIL`; observed roles: `evidence_gap_record`; missing roles: `lab_scope, baseline_result, pulse_result, lab_conclusion`; duplicate roles: `none`; required roles without path: `none`; reused required paths: `none`; path scope errors: `none`
- whitelist_lab: `FAIL`; observed roles: `evidence_gap_record`; missing roles: `provider_or_lab_authorization, provider_profile, third_party_baseline_capture, whitelist_conclusion`; duplicate roles: `none`; required roles without path: `none`; reused required paths: `none`; path scope errors: `none`
- security_review: `FAIL`; observed roles: `evidence_gap_record`; missing roles: `reviewer_identity, review_scope, findings_report`; duplicate roles: `none`; required roles without path: `none`; reused required paths: `none`; path scope errors: `none`
- production_readiness: `FAIL`; observed roles: `evidence_gap_record`; missing roles: `operator_approval, rollback_plan, monitoring_plan, prior_claim_references`; duplicate roles: `none`; required roles without path: `none`; reused required paths: `none`; path scope errors: `none`

## Gap Record Roles

- kernel_attach: `NOT_APPLICABLE`; expected gap role: `evidence_gap_record`; observed gap role: `None`; declared proof roles: `kernel_candidate_audit, kernel_commands, kernel_interface_scan, kernel_measurements`; failures: `none`
- packet_capture: `NOT_APPLICABLE`; expected gap role: `evidence_gap_record`; observed gap role: `None`; declared proof roles: `capture_summary, receiver_events, receiver_pcap, sender_events, sender_pcap`; failures: `none`
- baseline_timing_comparison: `NOT_APPLICABLE`; expected gap role: `evidence_gap_record`; observed gap role: `None`; declared proof roles: `baseline_events, pulse_events, timing_comparison`; failures: `none`
- dpi_lab: `PASS`; expected gap role: `evidence_gap_record`; observed gap role: `evidence_gap_record`; declared proof roles: `none`; failures: `none`
- whitelist_lab: `PASS`; expected gap role: `evidence_gap_record`; observed gap role: `evidence_gap_record`; declared proof roles: `none`; failures: `none`
- security_review: `PASS`; expected gap role: `evidence_gap_record`; observed gap role: `evidence_gap_record`; declared proof roles: `none`; failures: `none`
- production_readiness: `PASS`; expected gap role: `evidence_gap_record`; observed gap role: `evidence_gap_record`; declared proof roles: `none`; failures: `none`

## References

- kernel_attach: no prior-claim references required
- packet_capture: no prior-claim references required
- baseline_timing_comparison: no prior-claim references required
- dpi_lab: no prior-claim references required
- whitelist_lab: no prior-claim references required
- security_review: no prior-claim references required
- production_readiness: `FAIL`; missing references: `kernel_attach, packet_capture, baseline_timing_comparison, dpi_lab, whitelist_lab, security_review`; unverified referenced claims: `dpi_lab, whitelist_lab, security_review`

## Replacement Contracts

- kernel_attach: destination `docs/verification/GHOST_PULSE_KERNEL_ATTACH_LATEST.json`; required status `VERIFIED`; acceptance `python3 scripts/ops/verify_ghost_pulse_external_evidence.py --claim kernel_attach --require-pass --json`
- packet_capture: destination `docs/verification/GHOST_PULSE_PACKET_CAPTURE_LATEST.json`; required status `VERIFIED`; acceptance `python3 scripts/ops/verify_ghost_pulse_external_evidence.py --claim packet_capture --require-pass --json`
- baseline_timing_comparison: destination `docs/verification/GHOST_PULSE_BASELINE_COMPARISON_LATEST.json`; required status `VERIFIED`; acceptance `python3 scripts/ops/verify_ghost_pulse_external_evidence.py --claim baseline_timing_comparison --require-pass --json`
- dpi_lab: destination `docs/verification/GHOST_PULSE_DPI_LAB_LATEST.json`; required status `VERIFIED`; acceptance `python3 scripts/ops/verify_ghost_pulse_external_evidence.py --claim dpi_lab --require-pass --json`
- whitelist_lab: destination `docs/verification/GHOST_PULSE_WHITELIST_LAB_LATEST.json`; required status `VERIFIED`; acceptance `python3 scripts/ops/verify_ghost_pulse_external_evidence.py --claim whitelist_lab --require-pass --json`
- security_review: destination `docs/verification/GHOST_PULSE_SECURITY_REVIEW_LATEST.json`; required status `VERIFIED`; acceptance `python3 scripts/ops/verify_ghost_pulse_external_evidence.py --claim security_review --require-pass --json`
- production_readiness: destination `docs/verification/GHOST_PULSE_PRODUCTION_READINESS_LATEST.json`; required status `VERIFIED`; acceptance `python3 scripts/ops/verify_ghost_pulse_external_evidence.py --claim production_readiness --require-pass --json`

## Replacement Passport

- status: `REPLACEMENT_ACTION_REQUIRED`
- dpi_lab: candidate `docs/verification/incoming/dpi_lab.json`; example `docs/verification/incoming/examples/dpi_lab.example.json`; read-only import `python3 scripts/ops/import_ghost_pulse_external_evidence.py --claim dpi_lab --candidate docs/verification/incoming/dpi_lab.json --require-ready --json`; write import `python3 scripts/ops/import_ghost_pulse_external_evidence.py --claim dpi_lab --candidate docs/verification/incoming/dpi_lab.json --write --json`
- whitelist_lab: candidate `docs/verification/incoming/whitelist_lab.json`; example `docs/verification/incoming/examples/whitelist_lab.example.json`; read-only import `python3 scripts/ops/import_ghost_pulse_external_evidence.py --claim whitelist_lab --candidate docs/verification/incoming/whitelist_lab.json --require-ready --json`; write import `python3 scripts/ops/import_ghost_pulse_external_evidence.py --claim whitelist_lab --candidate docs/verification/incoming/whitelist_lab.json --write --json`
- security_review: candidate `docs/verification/incoming/security_review.json`; example `docs/verification/incoming/examples/security_review.example.json`; read-only import `python3 scripts/ops/import_ghost_pulse_external_evidence.py --claim security_review --candidate docs/verification/incoming/security_review.json --require-ready --json`; write import `python3 scripts/ops/import_ghost_pulse_external_evidence.py --claim security_review --candidate docs/verification/incoming/security_review.json --write --json`
- production_readiness: candidate `docs/verification/incoming/production_readiness.json`; example `docs/verification/incoming/examples/production_readiness.example.json`; read-only import `python3 scripts/ops/import_ghost_pulse_external_evidence.py --claim production_readiness --candidate docs/verification/incoming/production_readiness.json --require-ready --json`; write import `python3 scripts/ops/import_ghost_pulse_external_evidence.py --claim production_readiness --candidate docs/verification/incoming/production_readiness.json --write --json`

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

# x0tta6bl4_pulse Incoming External Evidence Examples

Status: `EXAMPLE_ONLY_NOT_EVIDENCE`

These files are examples only. They are not replacement candidates and must not be copied unchanged into the proof gate.

Use the real candidate path from each row, then run the read-only import command before using `--write`.

## Intake Gate

After staging real candidate files, run the intake gate before importing anything.

```bash
python3 scripts/ops/verify_ghost_pulse_external_evidence_intake.py --write-report --json
python3 scripts/ops/verify_ghost_pulse_external_evidence_intake.py --require-all-ready --json
```

Expected current result with only examples present: `EXTERNAL_EVIDENCE_INTAKE_ACTION_REQUIRED`.

After importing real ready candidates, refresh dependent reports in this order:

```bash
python3 scripts/ops/audit_ghost_pulse_external_evidence_gaps.py --json
python3 scripts/ops/verify_ghost_pulse_replacement_candidates.py --write-report --json
python3 scripts/ops/verify_ghost_pulse_external_evidence_intake.py --write-report --json
python3 scripts/ops/run_ghost_pulse_proof_gate.py --json
python3 scripts/ops/verify_ghost_pulse_external_evidence_inventory.py --write-report --json
python3 scripts/ops/run_ghost_pulse_verification_suite.py
python3 scripts/ops/run_ghost_pulse_proof_gate.py --json
python3 scripts/ops/verify_ghost_pulse_artifact_chain.py --write-report --json
python3 scripts/ops/verify_ghost_pulse_goal_state.py --write-report --json
```

## Examples

- kernel_attach: example `docs/verification/incoming/examples/kernel_attach.example.json`, real candidate `docs/verification/incoming/kernel_attach.json`
- packet_capture: example `docs/verification/incoming/examples/packet_capture.example.json`, real candidate `docs/verification/incoming/packet_capture.json`
- baseline_timing_comparison: example `docs/verification/incoming/examples/baseline_timing_comparison.example.json`, real candidate `docs/verification/incoming/baseline_timing_comparison.json`
- dpi_lab: example `docs/verification/incoming/examples/dpi_lab.example.json`, real candidate `docs/verification/incoming/dpi_lab.json`
- whitelist_lab: example `docs/verification/incoming/examples/whitelist_lab.example.json`, real candidate `docs/verification/incoming/whitelist_lab.json`
- security_review: example `docs/verification/incoming/examples/security_review.example.json`, real candidate `docs/verification/incoming/security_review.json`
- production_readiness: example `docs/verification/incoming/examples/production_readiness.example.json`, real candidate `docs/verification/incoming/production_readiness.json`

## Collection Tasks

- kernel_attach: candidate `docs/verification/incoming/kernel_attach.json`, status `WAITING_FOR_REAL_EXTERNAL_EVIDENCE`, artifact roles `kernel_commands, kernel_measurements, kernel_interface_scan, kernel_candidate_audit`
- packet_capture: candidate `docs/verification/incoming/packet_capture.json`, status `WAITING_FOR_REAL_EXTERNAL_EVIDENCE`, artifact roles `sender_pcap, receiver_pcap, sender_events, receiver_events, capture_summary`
- baseline_timing_comparison: candidate `docs/verification/incoming/baseline_timing_comparison.json`, status `WAITING_FOR_REAL_EXTERNAL_EVIDENCE`, artifact roles `baseline_events, pulse_events, timing_comparison`
- dpi_lab: candidate `docs/verification/incoming/dpi_lab.json`, status `WAITING_FOR_REAL_EXTERNAL_EVIDENCE`, artifact roles `lab_scope, baseline_result, pulse_result, lab_conclusion`
- whitelist_lab: candidate `docs/verification/incoming/whitelist_lab.json`, status `WAITING_FOR_REAL_EXTERNAL_EVIDENCE`, artifact roles `provider_or_lab_authorization, provider_profile, third_party_baseline_capture, whitelist_conclusion`
- security_review: candidate `docs/verification/incoming/security_review.json`, status `WAITING_FOR_REAL_EXTERNAL_EVIDENCE`, artifact roles `reviewer_identity, review_scope, findings_report`
- production_readiness: candidate `docs/verification/incoming/production_readiness.json`, status `WAITING_FOR_REAL_EXTERNAL_EVIDENCE`, artifact roles `operator_approval, rollback_plan, monitoring_plan, prior_claim_references`

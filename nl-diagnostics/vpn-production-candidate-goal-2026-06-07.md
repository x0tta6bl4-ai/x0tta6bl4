# VPN Production-Candidate Goal Status

generated_at: `2026-06-07T01:06:41Z`
decision: `VPN_PRODUCTION_CANDIDATE_GOAL_NOT_COMPLETE`
goal_complete: `false`
firstparty_decision: `FIRSTPARTY_VPN_LOCAL_RELEASE_CANDIDATE_READY`
firstparty_build_complete: `true`

## First-Party Objective

firstparty_requirements: `11/11`
legacy_requirements_non_blocking: `true`

### Remaining First-Party Work

- none

## Requirements

| ID | Status | OK | Requirement | Next Step |
|---|---|---|---|---|
| `FIRSTPARTY-CORE-01` | `ready_to_stage` | `true` | New first-party VPN core is present and no-foreign-backend source-audited | collect live first-party canary, TUN dataplane, leak-protection, MTU, and production-readiness evidence |
| `FIRSTPARTY-CANARY-01` | `pass` | `true` | Local first-party VPN canary passes protected DATA, admission, TUN dataplane, MTU, and source audit | collect leak-protection, linux preflight, and production-readiness evidence for a staged first-party deployment |
| `FIRSTPARTY-PROD-READY-01` | `ready_to_stage` | `true` | Local first-party production-readiness bundle passes all staged gates without OS or NL/SPB writes | prepare a guarded staging deploy packet; do not touch NL production until explicit approval and fresh read-only evidence exist |
| `FIRSTPARTY-STAGING-PACKET-01` | `ready_to_stage` | `true` | First-party staging packet has service plans, dry-run config apply, signed client kits, and live readiness | wait for explicit production approval and fresh read-only NL evidence before any real service install |
| `FIRSTPARTY-PRODUCTION-ENDPOINT-01` | `ready_to_stage` | `true` | First-party production endpoint is external, free on NL, and independent of legacy listeners | bind rollout/pre-apply packet to this external endpoint before production apply |
| `FIRSTPARTY-PRODUCTION-APPLY-PACKET-01` | `ready_to_stage` | `true` | First-party production apply packet is external-endpoint-bound, dry-run verified, and approval-blocked | requires explicit APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT plus secure non-repo material handoff before any real NL apply |
| `FIRSTPARTY-SECURE-MATERIAL-HANDOFF-01` | `ready_to_stage` | `true` | First-party private production material is staged outside repo with secret-free evidence | requires explicit APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT before copying the handoff to NL and applying it |
| `FIRSTPARTY-PRODUCTION-AUTHZ-01` | `ready_to_stage` | `true` | First-party production apply materials are bound and still approval-blocked | requires explicit APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT before copying material to NL and running post-apply validation |
| `FIRSTPARTY-ROLLOUT-PACKET-01` | `ready_to_stage` | `true` | First-party production rollout packet is approval-gated, rollback-ready, signed, and legacy-free | wait for explicit production approval and fresh read-only NL evidence before applying the rollout packet |
| `FIRSTPARTY-PREAPPLY-READY-01` | `ready_to_stage` | `true` | First-party production apply is blocked until approval and has mandatory post-apply validation | collect fresh read-only NL host evidence, then require explicit approval before any production apply |
| `FIRSTPARTY-NO-FOREIGN-01` | `pass` | `true` | First-party VPN objective is independent of legacy VLESS/WARP/Happ/Hiddify evidence | keep legacy VLESS/WARP/Happ/Hiddify evidence out of the first-party completion decision |
| `CORE-REALITY-01` | `missing` | `false` | Main NL VLESS/Reality contour remains stable | run restore_nl_vpn_monitor_canary_timer.sh --dry-run/--precheck, then apply only after APPLY_RESTORE_NL_VPN_MONITOR_CANARY_TIMER and collect a fresh snapshot |
| `EVIDENCE-FRESHNESS-01` | `pass` | `true` | Decision and remote request evidence are fresh enough for operator action | continue using current read-only evidence |
| `ANTIBLOCK-CLIENTS-01` | `blocked_external_evidence` | `false` | VLESS Reality profile is confirmed by real clients | collect the privacy-safe remote request-packet reports and record short replies |
| `TELEGRAM-WARP-01` | `ready_to_stage` | `true` | Telegram media has a guarded WARP-route plan | stage only after explicit APPLY_TELEGRAM_MEDIA_WARP_ROUTE approval and a fresh read-only snapshot |
| `NL-GATE-01` | `missing` | `false` | NL actions stay read-only by default and approval-gated | keep NL writes blocked until a separate explicit operator approval phrase exists |
| `CLAIMS-EVIDENCE-01` | `pass` | `true` | Production/customer claims stay evidence-backed and secret-free | publish only the generated evidence summaries, never raw client secrets |

## Evidence

### FIRSTPARTY-CORE-01

- source_root_exists=true
- contract_exists=true
- test_node_exists=true
- unit_test_exists=true
- required_core_files_present=true
- wire_magic_x0vpn001_present=true
- source_audit_passed=true
- source_audit_scanned_files=37
- source_audit_reasons=none
- source_audit_root_hash=174c92b528a696564c12ee65adc4a2bf0ff7ec165ec47c266daaa3626c444709
- source_audit_tree_hash=74ae83244208bd720e3d8dd967b5630a5571aab968a878a919da22d6df31aa26
- source_audit_error=none

### FIRSTPARTY-CANARY-01

- summary_path=/mnt/projects/nl-diagnostics/firstparty-live-canary-20260606T212215Z/summary.json
- canary_ok=true
- transport=tcp
- deployment_epoch=local-firstparty-canary-20260606T212215Z
- host=127.0.0.1
- server_bind_host=127.0.0.1
- local_only=true
- checks_passed=true
- failed_checks=none
- return_codes_ok=true
- dataplane_failed_reasons=none
- tun_dataplane_failed_reasons=none
- mtu_failed_reasons=none
- source_tree_hash=74ae83244208bd720e3d8dd967b5630a5571aab968a878a919da22d6df31aa26
- scanned_files=37

### FIRSTPARTY-PROD-READY-01

- summary_path=/mnt/projects/nl-diagnostics/firstparty-production-readiness-20260606T214343Z/summary.json
- readiness_ok=true
- decision_allowed=true
- decision_reasons=none
- deployment_epoch=local-firstparty-production-readiness-20260606T214343Z
- transport=tcp
- server_bind_host=127.0.0.1
- local_only=true
- checks_passed=true
- failed_checks=none
- collected_passed=true
- missing_collected=none
- return_codes_ok=true
- pqc_runtime_metadata_matches_manifest=true
- pqc_provider_gate_reasons=none
- source_tree_hash=74ae83244208bd720e3d8dd967b5630a5571aab968a878a919da22d6df31aa26
- os_mutation_performed=false
- no_nl_or_spb_writes_performed=true

### FIRSTPARTY-STAGING-PACKET-01

- summary_path=/mnt/projects/nl-diagnostics/firstparty-staging-packet-20260606T215812Z/summary.json
- staging_ok=true
- deployment_epoch=local-firstparty-staging-packet-20260606T215812Z
- transport=tcp
- server_bind_host=127.0.0.1
- local_only=true
- server_service_name=x0tta-firstparty-vpn.service
- client_service_name=x0tta-firstparty-vpn-client.service
- target_paths_ok=true
- client_kit_count=2
- verified_kit_count=2
- kit_counts_ok=true
- readiness_required=true
- archive_checked=true
- signature_required=true
- server_secrets_included=false
- raw_secret_material_stored_in_evidence=false
- kit_material_persisted_in_repo=false
- checks_passed=true
- failed_checks=none
- os_mutation_performed=false
- no_nl_or_spb_writes_performed=true

### FIRSTPARTY-PRODUCTION-ENDPOINT-01

- summary_path=/mnt/projects/nl-diagnostics/firstparty-production-endpoint-20260607T005925Z/summary.json
- endpoint_ok=true
- host=89.125.1.107
- bind_host=0.0.0.0
- port=40467
- transport=tcp
- deployment_epoch=production-firstparty-endpoint-20260607T005916Z
- external_shape_ok=true
- checks_passed=true
- failed_checks=none
- server_service_name=x0tta-firstparty-vpn.service
- client_service_name=x0tta-firstparty-vpn-client.service
- candidate_port_free_on_nl_snapshot=true
- occupied_port_count=45
- legacy_unit_findings=none
- no_mutation=true

### FIRSTPARTY-PRODUCTION-APPLY-PACKET-01

- summary_path=/mnt/projects/nl-diagnostics/firstparty-production-apply-packet-20260607T010129Z/summary.json
- apply_packet_ok=true
- host=89.125.1.107
- bind_host=0.0.0.0
- port=40467
- transport=tcp
- deployment_epoch=production-firstparty-apply-20260607T010042Z
- endpoint_deployment_epoch=production-firstparty-endpoint-20260607T005916Z
- external_shape_ok=true
- approval_guarded=true
- checks_passed=true
- failed_checks=none
- server_apply_dry_run_ok=true
- client_apply_dry_run_ok=true
- post_apply_validation_required=true
- secure_material_handoff_required=true
- server_service_name=x0tta-firstparty-vpn.service
- client_service_name=x0tta-firstparty-vpn-client.service
- client_kit_count=2
- verified_kit_count=2
- kit_counts_ok=true
- legacy_protocol_findings=none
- no_mutation=true

### FIRSTPARTY-SECURE-MATERIAL-HANDOFF-01

- summary_path=/mnt/projects/nl-diagnostics/firstparty-secure-material-handoff-20260607T010254Z/summary.json
- handoff_ok=true
- host=89.125.1.107
- bind_host=0.0.0.0
- port=40467
- transport=tcp
- deployment_epoch=production-firstparty-handoff-20260607T010221Z
- approval_guarded=true
- checks_passed=true
- failed_checks=none
- handoff_dir=/home/x0ttta6bl4/.local/share/x0tta-firstparty-vpn/handoffs/firstparty-production-handoff-20260607T010220Z
- handoff_archive=/home/x0ttta6bl4/.local/share/x0tta-firstparty-vpn/handoffs/firstparty-production-handoff-20260607T010220Z.tar.gz
- handoff_dir_mode=0700
- handoff_archive_mode=0600
- archive_sha256=c10fb4faea166880483dd3be2790d8ea093f26135ee8fcb5ea1d949cba9cdbc7
- manifest_sha256=a02ec8feaf77eeb5b3b6976be9df27f4e6324776137c002f530262fc6c799633
- source_tree_hash=1b44281aff62ba4a0bd763fd98bd704b647d39faeb792f012e2372779d66c1e5
- client_kit_count=2
- verified_kit_count=2
- kit_counts_ok=true
- legacy_protocol_findings=none
- private_handoff_ready=true
- no_mutation=true

### FIRSTPARTY-PRODUCTION-AUTHZ-01

- summary_path=/mnt/projects/nl-diagnostics/firstparty-production-authorization-20260607T010341Z/summary.json
- authorization_ok=true
- host=89.125.1.107
- bind_host=0.0.0.0
- port=40467
- transport=tcp
- approval_guarded=true
- checks_passed=true
- failed_checks=none
- all_evidence_fresh=true
- endpoint_fields_match_apply_and_handoff=true
- handoff_dir=/home/x0ttta6bl4/.local/share/x0tta-firstparty-vpn/handoffs/firstparty-production-handoff-20260607T010220Z
- handoff_archive=/home/x0ttta6bl4/.local/share/x0tta-firstparty-vpn/handoffs/firstparty-production-handoff-20260607T010220Z.tar.gz
- handoff_dir_mode=0700
- handoff_archive_mode=0600
- handoff_manifest_mode=0600
- handoff_archive_hash_matches_summary=true
- handoff_manifest_hash_matches_summary=true
- hashes_present=true
- manual_approval_still_required=true
- production_mutation_allowed=false
- no_mutation=true

### FIRSTPARTY-ROLLOUT-PACKET-01

- summary_path=/mnt/projects/nl-diagnostics/firstparty-rollout-packet-20260606T223505Z/summary.json
- rollout_ok=true
- deployment_epoch=local-firstparty-staging-packet-20260606T215812Z
- approval_phrase_required=APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT
- approval_present=false
- approval_guarded=true
- production_mutation_allowed=false
- os_mutation_performed=false
- no_nl_or_spb_writes_performed=true
- checks_passed=true
- failed_checks=none
- server_service_name=x0tta-firstparty-vpn.service
- client_service_name=x0tta-firstparty-vpn-client.service
- server_config_target=/etc/x0tta-firstparty-vpn-server/server.json
- client_config_target=/etc/x0tta-firstparty-vpn-client/client.json
- client_kit_count=2
- verified_kit_count=2
- kit_counts_ok=true
- legacy_protocol_findings=none

### FIRSTPARTY-PREAPPLY-READY-01

- summary_path=/mnt/projects/nl-diagnostics/firstparty-preapply-readiness-20260606T224533Z/summary.json
- preapply_ok=true
- deployment_epoch=local-firstparty-staging-packet-20260606T215812Z
- approval_phrase_required=APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT
- approval_present=false
- approval_guarded=true
- production_mutation_allowed=false
- os_mutation_performed=false
- no_nl_or_spb_writes_performed=true
- checks_passed=true
- failed_checks=none
- source_checks_passed=true
- failed_source_checks=none
- server_service_name=x0tta-firstparty-vpn.service
- client_service_name=x0tta-firstparty-vpn-client.service
- legacy_service_findings=none

### FIRSTPARTY-NO-FOREIGN-01

- source_audit_passed=true
- source_audit_reasons=none
- source_audit_scanned_files=37
- current_source_tree_hash=74ae83244208bd720e3d8dd967b5630a5571aab968a878a919da22d6df31aa26
- canary_source_tree_hash=74ae83244208bd720e3d8dd967b5630a5571aab968a878a919da22d6df31aa26
- production_readiness_source_tree_hash=74ae83244208bd720e3d8dd967b5630a5571aab968a878a919da22d6df31aa26
- source_tree_hash_consistent=true
- legacy_requirement_ids=ANTIBLOCK-CLIENTS-01, CORE-REALITY-01, TELEGRAM-WARP-01
- legacy_requirements_non_blocking_for_firstparty_goal=true

### CORE-REALITY-01

- decision=restore_transport_canary_monitor
- overall_status=advisory
- transport_status=degraded
- telegram_media_status=healthy
- core_evidence_present=true
- safe_mutation_flags=true

### EVIDENCE-FRESHNESS-01

- max_age_hours=24
- decision_generated_at=2026-06-06T15:33:58.431256+00:00
- decision_age_hours=9.55
- decision_fresh=true
- remote_request_generated_at=2026-06-06T15:47:38Z
- remote_request_age_hours=9.32
- remote_request_fresh=true

### ANTIBLOCK-CLIENTS-01

- matrix_decision=CLIENT_MATRIX_PARTIAL_REAL_DEVICES_REQUIRED
- matrix_complete=false
- missing_requirements=android_happ_or_hiddify, mobile_network, restricted_or_work_wifi
- passing_real_client_checks=2
- production_audit_decision=PRODUCTION_CANDIDATE_GOAL_NOT_MARKED_COMPLETE
- remote_request_decision=REMOTE_CLIENT_EVIDENCE_REQUEST_READY
- remote_request_count=2
- remote_request_ready=true
- remote_request_contract_ready=true
- remote_request_privacy_ok=true
- remote_request_freshness_policy_ok=true
- remote_request_record_commands_use_stdin=true
- remote_request_validate_commands_no_write=true
- remote_request_safe_reply_options_ok=true
- remote_request_hash_binding_policy_ok=true
- remote_request_reply_commands_hash_guard_ok=true
- remote_request_reply_dry_run_uses_packet_hash=true
- remaining_count=6

### TELEGRAM-WARP-01

- plan_decision=TELEGRAM_MEDIA_WARP_ROUTE_READY_TO_STAGE
- telegram_media_status=degraded
- warp_status=healthy
- target_outbound=warp
- safe_rollout_guard=true
- restart_scope=x-ui

### NL-GATE-01

- manifest_status=planning_only
- manifest_nl_write_allowed=false
- readiness_ok=false
- readiness_nl_write_allowed=false
- automatic_failover_allowed=false
- spb_fallback_allowed=false
- preflight_ok=true
- preflight_deploy_status=local_ready_but_deploy_blocked
- preflight_check_count=389

### CLAIMS-EVIDENCE-01

- privacy_findings=0
- not_overclaiming_production_candidate=true
- anti_block_audit_decision=PRODUCTION_CANDIDATE_GOAL_NOT_MARKED_COMPLETE
- client_matrix_complete=false

## Remaining Before Goal Complete

- record Android Happ/Hiddify client evidence after rollout
- record one mobile network evidence case
- record one restricted or work Wi-Fi evidence case
- collect the 2 safe remote request-packet reports: mobile Happ/Hiddify and restricted/work Wi-Fi
- rerun preflight/tests after remaining client matrix evidence is added
- after any new client pass/fail evidence, run refresh_client_evidence_artifacts.py --write before final readiness audit
- run restore_nl_vpn_monitor_canary_timer.sh --dry-run/--precheck, then apply only after APPLY_RESTORE_NL_VPN_MONITOR_CANARY_TIMER and collect a fresh snapshot
- keep NL writes blocked until a separate explicit operator approval phrase exists

## Preflight

```text
ok=true
deploy_status=local_ready_but_deploy_blocked
nl_write_allowed=false
check_count=389
validator_exit_code=0
```

No NL or SPB writes were performed by this goal report.

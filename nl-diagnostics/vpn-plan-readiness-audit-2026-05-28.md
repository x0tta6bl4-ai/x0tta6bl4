# VPN Plan Readiness Audit

generated_at: `2026-05-28T03:26:58.933383+00:00`
overall_status: `ready_local_with_future_blocks`
ok: `true`

## Summary

```text
ready_local=23
blocked_future_approval=4
watch=3
missing=0
decision=observe
operator_status=observe
boot_gap_watch_status=watch
provider_packet_type=provider_watch
provider_packet_stale=False
manual_failover_readiness_status=blocked_no_incident_trigger
manual_failover_switch_allowed=False
secondary_candidate_score_status=missing_candidates
secondary_exit_requirements_status=requirements_ready_no_candidate
secondary_provider_shortlist_status=shortlist_ready_no_endpoint
secondary_provider_shortlist_count=5
secondary_provider_shortlist_endpoint_count=0
secondary_candidate_intake_status=awaiting_public_candidate_metadata
secondary_provisioning_plan_status=provisioning_plan_ready_no_endpoint
secondary_provisioning_external_action_required=True
secondary_provisioning_endpoint_count=0
secondary_exit_flow_status=blocked_missing_candidate
secondary_exit_flow_candidate_configured=False
secondary_exit_flow_manual_switch_allowed=False
secondary_manual_drill_status=drill_plan_ready_blocked_no_endpoint
secondary_manual_drill_test_scope=single_client
secondary_manual_drill_rollback_required=True
secondary_selection_packet_status=selection_packet_ready_no_endpoint
secondary_selection_recommended_label=upcloud-fi-hel
secondary_selection_backup_label=ovhcloud-pl-waw
secondary_selection_option_count=3
secondary_selection_may_create_endpoint_now=False
secondary_public_metadata_template_status=public_metadata_template_ready_no_endpoint
secondary_public_metadata_selected_label=upcloud-fi-hel
secondary_public_metadata_candidate_file_update_allowed=False
local_diagnostic_environment_status=watch_root_full_tmpdir_available
local_root_status=critical_full
local_tmpdir_writable=True
local_root_cleanup_plan_status=manual_cleanup_plan_ready
local_root_cleanup_estimated_reclaim_gib=3.25
local_root_cleanup_execute_allowed=False
local_root_cleanup_approval_packet_status=cleanup_approval_packet_ready
local_root_cleanup_approval_required=True
local_root_cleanup_commands_executed=0
incident_symptom_intake_status=symptom_intake_ready_observe
incident_symptom_required_fields=12
incident_symptom_forbidden_material=12
transport_probe_status=healthy
transport_uptime_status=stable_healthy
nl_write_allowed=false
spb_fallback_allowed=false
automatic_failover_allowed=false
```

## Readiness Matrix

| ID | Status | Area | Next Step |
|---|---|---|---|
| `EVIDENCE-01` | `ready_local` | Latest read-only snapshot is the shared evidence anchor | collect a fresh read-only snapshot during the next visible outage |
| `DECISION-01` | `ready_local` | Current decision blocks mutation and automatic profile changes | keep decision=observe unless a fresh snapshot changes the failure domain |
| `BOOT-01` | `watch` | Boot-gap provider signal is tracked separately from restart decisions | keep provider boot gap on watch while current transport remains healthy/advisory |
| `PROVIDER-01` | `ready_local` | Provider packet is generated from the same read-only snapshot | use the packet for provider questions only when fresh evidence points to provider or host failure |
| `EVIDENCE-02` | `ready_local` | Blocking/app probe history is available as trend evidence | use probes as app/path evidence, not as an x-ui restart trigger |
| `REFRESH-01` | `ready_local` | One refresh command rebuilds the local planning reports | run refresh after every new snapshot before deciding on action |
| `LOCALENV-01` | `watch` | Local diagnostic host has a writable project temp directory | keep using TMPDIR=/mnt/projects/.tmp and clean / only after separate local cleanup approval |
| `LOCALCLEAN-01` | `watch` | Local root cleanup plan is prepared but execution is blocked | review local cleanup candidates and execute cleanup only after separate local approval |
| `LOCALCLEAN-02` | `ready_local` | Local cleanup approval packet is prepared without executing commands | run only prechecks now; execute cleanup previews only after separate local cleanup approval |
| `OPERATOR-01` | `ready_local` | Short incident card exists for the next outage | start incidents from the operator card, then collect fresh evidence |
| `INCIDENT-01` | `ready_local` | Incident symptom intake is safe to use without collecting secrets | use this template for user-visible symptoms and reject any pasted VPN secrets |
| `FAILOVER-03` | `blocked_future_approval` | Manual failover readiness gate blocks unsafe switching | keep manual switch blocked until a fresh incident trigger and healthy non-NL/non-SPB secondary exist |
| `FAILOVER-05` | `ready_local` | Secondary candidate scorer is available before provider choice | score only public metadata for non-NL/non-SPB candidates before generating a probe config |
| `FAILOVER-04` | `ready_local` | Secondary exit requirements are documented without secrets | choose a real non-NL/non-SPB provider/region and fill only public endpoint metadata |
| `FAILOVER-08` | `ready_local` | Secondary provider shortlist exists without endpoint secrets | provision one shortlisted non-NL/non-SPB option, then add only public host/IP metadata |
| `FAILOVER-07` | `ready_local` | Secondary candidate intake checklist exists without secrets | fill only public metadata in the local candidate file, then rerun scorer and refresh |
| `FAILOVER-09` | `ready_local` | Secondary provisioning plan blocks secrets and automation | perform the provider-console provisioning step externally, then store only public endpoint metadata |
| `FAILOVER-06` | `blocked_future_approval` | Secondary exit operating flow blocks unsafe activation | fill public metadata for a non-NL/non-SPB candidate, then generate and run the safe probe config |
| `FAILOVER-10` | `ready_local` | Secondary manual drill is test-only and rollback-gated | after a secondary endpoint exists, run the drill on one test client and roll back to NL |
| `FAILOVER-11` | `ready_local` | Secondary provider selection packet gives a safe decision order | pick the primary label externally, then store only public endpoint metadata after provisioning |
| `FAILOVER-12` | `ready_local` | Secondary public metadata template is ready without secrets | after external provisioning, replace only host with public IP/DNS and rerun scorer |
| `TRANSPORT-01` | `ready_local` | Outside-in NL TCP port probe is available | if any public NL port fails, collect a fresh read-only snapshot and compare listeners |
| `UPTIME-01` | `ready_local` | Outside-in NL TCP uptime history is recorded locally | if uptime history becomes watch, collect a fresh read-only snapshot and provider packet |
| `SCHEDULER-01` | `ready_local` | Local uptime systemd timer templates are prepared but not installed | install/enable the local timer only after separate local host approval |
| `SOURCE-01` | `ready_local` | NL source reconciliation is locally closed and deploy-blocked | keep services/nl-server as reviewed local source until a separate NL write approval exists |
| `PREFLIGHT-01` | `ready_local` | Preflight validator passes while deploy remains blocked | run preflight again before any maintenance window |
| `GATE-01` | `blocked_future_approval` | Future NL write is blocked until the exact approval phrase | do not stage files to NL before the exact approval phrase is given |
| `SPB-01` | `ready_local` | SPB remains excluded from recovery | keep SPB disabled until it has its own explicit reactivation plan |
| `FAILOVER-01` | `ready_local` | Manual failover is documented but inactive | keep failover manual-only and require fresh evidence before any client switch |
| `FAILOVER-02` | `blocked_future_approval` | Secondary exit probe is only a safe template until a new node exists | choose a new non-NL/non-SPB provider/region before any emergency profile test |

## Evidence

### EVIDENCE-01

- decision_snapshot=/mnt/projects/nl-diagnostics/snapshots/20260528T032605Z
- refresh_snapshot=/mnt/projects/nl-diagnostics/snapshots/20260528T032605Z
- latest_snapshot=20260528T032605Z
- snapshot_exists=true
- snapshot_age_seconds=53
- fresh=true

### DECISION-01

- decision=observe
- transport_status=advisory
- failure_domain=external_network
- safe_flags=true

### BOOT-01

- boot_gap_watch_status=watch
- boot_gap_seconds=21907
- provider_status=recent_boot_gap
- transport_status=advisory
- safe_flags=true

### PROVIDER-01

- provider_packet_type=provider_watch
- snapshot_stale=false
- packet_snapshot=/mnt/projects/nl-diagnostics/snapshots/20260528T032605Z
- decision_snapshot=/mnt/projects/nl-diagnostics/snapshots/20260528T032605Z
- same_snapshot=true
- safe_flags=true

### EVIDENCE-02

- snapshot_count=10
- trend=stable_no_probe_evidence
- latest_probe_snapshot=20260528T032605Z
- latest_targets_ok=8/8

### REFRESH-01

- refresh_ok=true
- operator_status=observe
- manual_failover_status=planning_not_active
- safe_flags=true

### LOCALENV-01

- local_environment_status=watch_root_full_tmpdir_available
- root_status=critical_full
- root_used_percent=94.9
- root_free_gib=0.0
- tmp_status=critical_full
- diagnostic_tmpdir=/mnt/projects/.tmp
- diagnostic_tmpdir_writable=true
- recommended_tmpdir_prefix=TMPDIR=/mnt/projects/.tmp
- cleanup_required=true
- safe_flags=true

### LOCALCLEAN-01

- cleanup_plan_status=manual_cleanup_plan_ready
- root_status=critical_full
- root_free_gib=0.0
- existing_candidate_count=5
- estimated_reclaim_gib=3.25
- top_candidate_id=APT-CACHE-01
- cleanup_execute_allowed=false
- safe_flags=true

### LOCALCLEAN-02

- cleanup_approval_packet_status=cleanup_approval_packet_ready
- first_review_id=APT-CACHE-01
- command_preview_count=5
- approval_required=true
- commands_executed=0
- cleanup_execute_allowed=false
- safe_flags=true

### OPERATOR-01

- operator_status=observe
- plain_action=VPN core is healthy. Do not restart NL; collect fresh evidence during the next visible outage.
- blocking_history_trend=stable_no_probe_evidence
- safe_flags=true

### INCIDENT-01

- incident_symptom_intake_status=symptom_intake_ready_observe
- decision=observe
- operator_status=observe
- failure_domain=external_network
- transport_status=advisory
- required_field_count=12
- forbidden_material_count=12
- safe_flags=true

### FAILOVER-03

- manual_failover_readiness_status=blocked_no_incident_trigger
- manual_probe_allowed=false
- manual_switch_allowed=false
- secondary_probe_status=planning_template
- candidate_configured=false
- spb_excluded=true
- safe_flags=true

### FAILOVER-05

- secondary_candidate_score_status=missing_candidates
- candidate_count=0
- viable_count=0
- rejected_count=0
- top_candidate_label=none
- safe_flags=true

### FAILOVER-04

- secondary_exit_requirements_status=requirements_ready_no_candidate
- candidate_configured=false
- missing_items=NET-01
- blocked_items=none
- manual_switch_allowed=false
- safe_flags=true

### FAILOVER-08

- secondary_provider_shortlist_status=shortlist_ready_no_endpoint
- shortlist_count=5
- source_count=9
- endpoint_count=0
- candidate_configured=false
- invalid_source_refs=none
- safe_flags=true

### FAILOVER-07

- secondary_candidate_intake_status=awaiting_public_candidate_metadata
- candidate_file=/mnt/projects/nl-diagnostics/secondary-exit-candidates.example.json
- candidate_count=0
- viable_count=0
- allowed_field_count=7
- forbidden_material_count=7
- safe_flags=true

### FAILOVER-09

- secondary_provisioning_plan_status=provisioning_plan_ready_no_endpoint
- preferred_labels=upcloud-fi-hel,ovhcloud-pl-waw,hetzner-de-or-fi
- endpoint_count=0
- external_action_required=true
- candidate_file=/mnt/projects/nl-diagnostics/secondary-exit-candidates.example.json
- safe_sources=true
- safe_flags=true

### FAILOVER-06

- secondary_exit_flow_status=blocked_missing_candidate
- candidate_viable_count=0
- candidate_configured=false
- secondary_probe_status=planning_template
- manual_probe_allowed=false
- manual_switch_allowed=false
- safe_flags=true

### FAILOVER-10

- secondary_manual_drill_status=drill_plan_ready_blocked_no_endpoint
- manual_probe_allowed=false
- manual_switch_allowed=false
- test_scope=single_client
- bulk_user_switch_allowed=false
- rollback_required=true
- safe_flags=true

### FAILOVER-11

- secondary_selection_packet_status=selection_packet_ready_no_endpoint
- recommended_label=upcloud-fi-hel
- backup_label=ovhcloud-pl-waw
- decision_option_count=3
- endpoint_count=0
- may_create_endpoint_now=false
- safe_flags=true

### FAILOVER-12

- secondary_public_metadata_template_status=public_metadata_template_ready_no_endpoint
- selected_label=upcloud-fi-hel
- selected_provider=UpCloud
- candidate_file=/mnt/projects/nl-diagnostics/secondary-exit-candidates.example.json
- template_candidate_count=1
- candidate_file_update_allowed=false
- forbidden_material_count=11
- safe_flags=true

### TRANSPORT-01

- transport_probe_status=healthy
- transport_probe_ok_count=3/3
- failure_domain_hint=none
- safe_flags=true

### UPTIME-01

- uptime_status=stable_healthy
- sample_count=23
- latest_status=healthy
- consecutive_non_healthy=0
- safe_flags=true

### SCHEDULER-01

- service_exists=true
- timer_exists=true
- expected_commands=true
- tmpdir_environment=Environment=TMPDIR=/mnt/projects/.tmp
- forbidden_word=none

### SOURCE-01

- nl_write_allowed=false
- deployable_to_nl=false
- missing_local_source=0
- local_name_drift=0
- accepted_local_delta=5

### PREFLIGHT-01

- preflight_ok=true
- deploy_status=local_ready_but_deploy_blocked
- nl_write_allowed=false
- check_count=70

### GATE-01

- approval_phrase_present=true
- required_phrase=approve NL write for health shell split only
- nl_write_allowed=false
- deploy_status=local_ready_but_deploy_blocked

### SPB-01

- decision_spb_fallback_allowed=false
- refresh_spb_fallback_allowed=false
- manual_failover_spb_fallback_allowed=false
- secondary_spb_fallback_allowed=false
- manifest_spb_enabled=false
- plain_true_marker_absent=true

### FAILOVER-01

- manual_failover_status=planning_not_active
- spb_fallback_allowed=false
- automatic_failover_allowed=false
- safe_flags=true

### FAILOVER-02

- secondary_probe_status=planning_template
- candidate_configured=false
- spb_fallback_allowed=false
- automatic_failover_allowed=false

No NL or SPB writes were performed by this readiness audit.

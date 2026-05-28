# VPN Planning Refresh

generated_at: `2026-05-28T03:15:13.682618+00:00`
snapshot: `/mnt/projects/nl-diagnostics/snapshots/20260528T031418Z`
ok: `true`

## Summary

```text
decision=observe
decision_confidence=high
operator_status=observe
boot_gap_watch_status=watch
boot_gap_seconds=21907
provider_packet_type=provider_watch
provider_packet_stale=False
provider_packet_snapshot_age_seconds=39
blocking_history_trend=stable_no_probe_evidence
blocking_history_snapshot_count=9
manual_failover_status=planning_not_active
manual_failover_readiness_status=blocked_no_incident_trigger
manual_failover_probe_allowed=False
manual_failover_switch_allowed=False
secondary_candidate_score_status=missing_candidates
secondary_candidate_viable_count=0
secondary_exit_requirements_status=requirements_ready_no_candidate
secondary_exit_requirements_missing=NET-01
secondary_provider_shortlist_status=shortlist_ready_no_endpoint
secondary_provider_shortlist_count=5
secondary_provider_shortlist_endpoint_count=0
secondary_candidate_intake_status=awaiting_public_candidate_metadata
secondary_candidate_intake_allowed_fields=7
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
local_diagnostic_environment_status=watch_root_full_tmpdir_available
local_root_status=critical_full
local_tmpdir_writable=True
local_recommended_tmpdir_prefix=TMPDIR=/mnt/projects/.tmp
local_root_cleanup_plan_status=manual_cleanup_plan_ready
local_root_cleanup_estimated_reclaim_gib=3.23
local_root_cleanup_execute_allowed=False
local_root_cleanup_approval_packet_status=cleanup_approval_packet_ready
local_root_cleanup_approval_required=True
local_root_cleanup_commands_executed=0
incident_symptom_intake_status=symptom_intake_ready_observe
incident_symptom_required_fields=12
incident_symptom_forbidden_material=12
nl_transport_probe_status=healthy
nl_transport_probe_ok_count=3/3
nl_transport_uptime_status=stable_healthy
nl_transport_uptime_samples=22
nl_transport_uptime_bad_streak=0
secondary_probe_template_status=planning_template
readiness_audit_status=ready_local_with_future_blocks
readiness_missing=0
incident_timeline_event_count=20
incident_timeline_latest_type=provider_watch
incident_timeline_latest_snapshot=20260528T031418Z
nl_mutation_allowed=false
spb_fallback_allowed=false
automatic_failover_allowed=false
```

## Steps

### blocking_history

```text
ok=true
exit_code=0
```

### decision_report

```text
ok=true
exit_code=0
```

### boot_gap_watch

```text
ok=true
exit_code=0
```

### provider_packet

```text
ok=true
exit_code=0
```

### improvement_backlog

```text
ok=true
exit_code=0
```

### manual_failover_plan

```text
ok=true
exit_code=0
```

### nl_transport_probe

```text
ok=true
exit_code=0
```

### nl_transport_uptime

```text
ok=true
exit_code=0
```

### secondary_probe_template_check

```text
ok=true
exit_code=0
```

### manual_failover_readiness

```text
ok=true
exit_code=0
```

### secondary_candidate_score

```text
ok=true
exit_code=0
```

### secondary_exit_requirements

```text
ok=true
exit_code=0
```

### secondary_provider_shortlist

```text
ok=true
exit_code=0
```

### secondary_candidate_intake

```text
ok=true
exit_code=0
```

### secondary_provisioning_plan

```text
ok=true
exit_code=0
```

### secondary_exit_flow

```text
ok=true
exit_code=0
```

### secondary_manual_drill

```text
ok=true
exit_code=0
```

### secondary_selection_packet

```text
ok=true
exit_code=0
```

### local_diagnostic_environment

```text
ok=true
exit_code=0
```

### local_root_cleanup_plan

```text
ok=true
exit_code=0
```

### local_root_cleanup_approval_packet

```text
ok=true
exit_code=0
```

### operator_card

```text
ok=true
exit_code=0
```

### incident_symptom_intake

```text
ok=true
exit_code=0
```

### readiness_audit

```text
ok=true
exit_code=0
```

### incident_timeline

```text
ok=true
exit_code=0
```

No NL or SPB writes were performed by this refresh.

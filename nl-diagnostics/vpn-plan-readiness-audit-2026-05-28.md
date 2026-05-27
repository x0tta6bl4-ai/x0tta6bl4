# VPN Plan Readiness Audit

generated_at: `2026-05-27T23:53:10.506939+00:00`
overall_status: `ready_local_with_future_blocks`
ok: `true`

## Summary

```text
ready_local=12
blocked_future_approval=2
watch=1
missing=0
decision=observe
operator_status=observe
boot_gap_watch_status=watch
provider_packet_type=provider_watch
provider_packet_stale=False
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
| `OPERATOR-01` | `ready_local` | Short incident card exists for the next outage | start incidents from the operator card, then collect fresh evidence |
| `TRANSPORT-01` | `ready_local` | Outside-in NL TCP port probe is available | if any public NL port fails, collect a fresh read-only snapshot and compare listeners |
| `UPTIME-01` | `ready_local` | Outside-in NL TCP uptime history is recorded locally | if uptime history becomes watch, collect a fresh read-only snapshot and provider packet |
| `SOURCE-01` | `ready_local` | NL source reconciliation is locally closed and deploy-blocked | keep services/nl-server as reviewed local source until a separate NL write approval exists |
| `PREFLIGHT-01` | `ready_local` | Preflight validator passes while deploy remains blocked | run preflight again before any maintenance window |
| `GATE-01` | `blocked_future_approval` | Future NL write is blocked until the exact approval phrase | do not stage files to NL before the exact approval phrase is given |
| `SPB-01` | `ready_local` | SPB remains excluded from recovery | keep SPB disabled until it has its own explicit reactivation plan |
| `FAILOVER-01` | `ready_local` | Manual failover is documented but inactive | keep failover manual-only and require fresh evidence before any client switch |
| `FAILOVER-02` | `blocked_future_approval` | Secondary exit probe is only a safe template until a new node exists | choose a new non-SPB provider/region before any emergency profile test |

## Evidence

### EVIDENCE-01

- decision_snapshot=nl-diagnostics/snapshots/20260527T230246Z
- refresh_snapshot=nl-diagnostics/snapshots/20260527T230246Z
- latest_snapshot=20260527T230246Z
- snapshot_exists=true
- snapshot_age_seconds=3024
- fresh=true

### DECISION-01

- decision=observe
- transport_status=healthy
- failure_domain=external_network
- safe_flags=true

### BOOT-01

- boot_gap_watch_status=watch
- boot_gap_seconds=21907
- provider_status=recent_boot_gap
- transport_status=healthy
- safe_flags=true

### PROVIDER-01

- provider_packet_type=provider_watch
- snapshot_stale=false
- packet_snapshot=/mnt/projects/nl-diagnostics/snapshots/20260527T230246Z
- decision_snapshot=nl-diagnostics/snapshots/20260527T230246Z
- same_snapshot=true
- safe_flags=true

### EVIDENCE-02

- snapshot_count=4
- trend=stable_no_probe_evidence
- latest_probe_snapshot=20260527T230246Z
- latest_targets_ok=8/8

### REFRESH-01

- refresh_ok=true
- operator_status=observe
- manual_failover_status=planning_not_active
- safe_flags=true

### OPERATOR-01

- operator_status=observe
- plain_action=VPN core is healthy. Do not restart NL; collect fresh evidence during the next visible outage.
- blocking_history_trend=stable_no_probe_evidence
- safe_flags=true

### TRANSPORT-01

- transport_probe_status=healthy
- transport_probe_ok_count=3/3
- failure_domain_hint=none
- safe_flags=true

### UPTIME-01

- uptime_status=stable_healthy
- sample_count=1
- latest_status=healthy
- consecutive_non_healthy=0
- safe_flags=true

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

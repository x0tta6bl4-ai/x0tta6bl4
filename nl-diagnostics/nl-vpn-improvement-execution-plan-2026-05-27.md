# NL VPN Improvement Execution Plan, 2026-05-27

## Status

This is a local execution plan. NL remains read-only.

Current authoritative evidence:

```text
incident entrypoint: nl-diagnostics/run_vpn_incident_readonly_refresh.sh
vpn snapshot: nl-diagnostics/snapshots/20260527T230246Z
server profile: nl-diagnostics/nl-server-profile/20260527T173222Z
gap analysis: nl-diagnostics/nl-profile-gap-analysis-20260527T173222Z.md
decision report: nl-diagnostics/current-vpn-decision-2026-05-28.md
blocking probe history: nl-diagnostics/blocking-probe-history-2026-05-28.md
boot-gap watch: nl-diagnostics/boot-gap-watch-2026-05-28.md
provider packet: nl-diagnostics/provider-incident-packets/provider-incident-packet-20260527T230246Z.md
improvement backlog: nl-diagnostics/vpn-improvement-backlog-2026-05-28.md
manual failover plan: nl-diagnostics/manual-failover-plan-2026-05-28.md
planning refresh report: nl-diagnostics/vpn-planning-refresh-2026-05-28.md
operator card: nl-diagnostics/vpn-operator-card-2026-05-28.md
NL transport probe: nl-diagnostics/nl-transport-probe-2026-05-28.md
NL transport uptime: nl-diagnostics/nl-transport-uptime-summary-2026-05-28.md
local uptime timer templates: infra/systemd/x0tta-vpn-nl-transport-uptime.service, infra/systemd/x0tta-vpn-nl-transport-uptime.timer
readiness audit: nl-diagnostics/vpn-plan-readiness-audit-2026-05-28.md
boot gap report: nl-diagnostics/boot-gap-2026-05-27-report.md
P1 source promotion update: nl-diagnostics/nl-p1-source-promotion-update-2026-05-27.md
```

Current state:

```text
local VPN: ok
exit IP: 89.125.1.107
packet loss: 0
NL x-ui: active
NL listeners: 443, 2083, 39829 present
NL runtime: degraded because Telegram media edges are slow
NL transport: healthy
NL provider_status: recent_boot_gap
current decision: observe, high confidence
operator status: observe
blocking probe history: stable_no_probe_evidence across 4 snapshots
boot-gap watch: watch, boot_gap_seconds=21907
provider packet: provider_watch, snapshot_stale=false
freshness gate: snapshot_age_seconds=2519, max=3600
planning refresh: ok=true
outside-in NL transport probe: healthy, 3/3 ports ok
outside-in NL transport uptime: stable_healthy, samples=2, bad_streak=0
local uptime scheduler templates: prepared only, not installed
readiness audit: ready_local_with_future_blocks, ready_local=13, watch=1, missing=0
blocked future items: GATE-01 future NL write approval, FAILOVER-02 real secondary exit node
NL writes: 0
```

## Diagnosis

The latest user-visible failure is best explained by a NL server availability
gap, not by x-ui config corruption or a local route loop:

```text
previous boot last entry: 2026-05-27 08:53:30 UTC
current boot first entry: 2026-05-27 14:58:37 UTC
gap: 21907 seconds
current boot journal: previous journal corrupted or uncleanly shut down
```

There is no current explicit `hypervisor initiated shutdown` line for this new
gap, so the correct action is provider watch / provider question, not service
restart on NL.

## Improvement Tracks

### P0. Keep mutation blocked while diagnosis is uncertain

Done locally:

```text
scripts/vpn_provider_guard.py blocks local healing on provider outage/stale evidence
scripts/vpn_heal.sh calls provider guard before local mutation
vpn_watchdog hard heal requires explicit env flag and fresh provider guard
collectors use read-only SSH commands and local output only
incident entrypoint runs collector + refresh as one local command
```

Remaining:

```text
keep NL write permission false until a maintenance command is explicit
keep provider_watch separate from provider_outage
refresh snapshot before every manual action
```

### P1. Make status semantics boring and testable

Done locally:

```text
Telegram-only degradation -> advisory/observe when transport is healthy/advisory
boot gap + current healthy transport -> warning, not outage
ifup@eth0.service -> non-critical warning when core VPN is healthy
profile switch -> manual review only, no automatic switch
```

Remaining:

```text
port these semantics into NL runtime code only after explicit write approval
add an on-NL read-only health endpoint that exposes state-contract fields
```

### P2. Reconcile server source before deploy

Current source reconciliation status:

```text
report: nl-diagnostics/nl-source-reconciliation-status-2026-05-27.md
status: locally closed for latest read-only profile
missing_local_source: 0
local_name_drift: 0
```

Current gap summary:

```json
{
  "accepted_local_delta": 5,
  "redacted_review_only": 2,
  "redacted_template_only": 1,
  "same_hash_elsewhere": 18,
  "server_backup_only": 4,
  "server_runtime_artifact": 4
}
```

Promoted locally in this phase:

```text
mesh/listener_loss_signal.py
mesh/publish_client_profile_hint.py
mesh/auto_monitor.py
mesh/apply_config_auto.py
mesh/full_stealth_config.py
mesh/rotation_timer.sh
ghost-access/sync_xray_device_activity.py
ghost-vpn/ghost_tcp_bridge.py
ghost-vpn/ghost_vpn_server.py
ghost-vpn/ghost_vpn_client.py
```

They match the current NL hashes and are covered by local tests, but remain
local source candidates only. They are not deployed while NL is read-only.

Do not deploy now:

```text
vps_build_runtime_state.py local semantics differ intentionally
ghost_vpn_protocol.py local import fallback differs intentionally
redacted Ghost Access files are not deployable
x-ui db/config/binaries are runtime artifacts, not repo source
```

### P3. Prepare provider resilience

Needed:

```text
external uptime probe for 89.125.1.107:443/2083/39829
provider evidence packet generated automatically from fresh snapshots
boot-gap watch generated automatically from fresh snapshots
freshness gate marks old snapshots as watch after 3600 seconds
manual failover requirements are documented for a new secondary node, not SPB
local-only secondary health probe template: nl-diagnostics/probe_secondary_exit.py
local-only outside-in NL transport probe: nl-diagnostics/probe_nl_transport_ports.py
local-only transport uptime history: nl-diagnostics/record_nl_transport_uptime.py
local-only uptime systemd templates: infra/systemd/x0tta-vpn-nl-transport-uptime.service, infra/systemd/x0tta-vpn-nl-transport-uptime.timer
safe secondary config generator: nl-diagnostics/create_secondary_exit_config.py
example secondary probe config: nl-diagnostics/manual-failover-secondary.example.json
alert when boot gap appears after an unclean shutdown
```

Acceptance:

```text
provider incident can be opened with exact boot window and current service state
local healing does not hide provider/host incidents
manual profile switch never happens from stale evidence
SPB remains excluded from fallback while disabled
secondary probe blocks raw VPN URI/private key/token config
```

### P4. First future write, if approved

The safest first NL write is not a service replacement. It is adding dry-run
health wrappers:

```text
/opt/x0tta6bl4-mesh/scripts/health_check_readonly.sh
/opt/x0tta6bl4-mesh/scripts/health_action_policy.py
/opt/x0tta6bl4-mesh/scripts/health_heal_xui.sh
```

Gate:

```text
operator says: approve NL write for health shell split only
fresh read-only snapshot and profile pass
backup/rollback commands prepared
files staged first
no systemd reload
no service restart
old health_check.sh unchanged
post-write read-only verification passes
```

## Current Decision

```text
recommended_action: observe
decision_report: nl-diagnostics/current-vpn-decision-2026-05-28.md
improvement_backlog: nl-diagnostics/vpn-improvement-backlog-2026-05-28.md
manual_failover_plan: nl-diagnostics/manual-failover-plan-2026-05-28.md
do_not_restart_nl: true
do_not_deploy_to_nl: true
next_best_work: keep local evidence/backlog current; prepare failover requirements without using SPB
refresh_command: python3 nl-diagnostics/refresh_vpn_planning_reports.py --snapshot nl-diagnostics/snapshots/<timestamp>
incident_entrypoint: VPN_ENABLE_BLOCKING_PROBES=1 nl-diagnostics/run_vpn_incident_readonly_refresh.sh
operator_card: nl-diagnostics/vpn-operator-card-2026-05-28.md
boot_gap_watch: nl-diagnostics/boot-gap-watch-2026-05-28.md
provider_packet: nl-diagnostics/provider-incident-packets/provider-incident-packet-20260527T230246Z.md
freshness_rule: collect a fresh read-only snapshot if snapshot_age_seconds > 3600
nl_transport_probe: nl-diagnostics/nl-transport-probe-2026-05-28.md
nl_transport_uptime: nl-diagnostics/nl-transport-uptime-summary-2026-05-28.md
local_uptime_scheduler_templates: prepared only, not installed
readiness_audit: nl-diagnostics/vpn-plan-readiness-audit-2026-05-28.md
```

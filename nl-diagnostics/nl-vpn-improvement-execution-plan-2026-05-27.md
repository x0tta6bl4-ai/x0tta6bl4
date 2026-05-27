# NL VPN Improvement Execution Plan, 2026-05-27

## Status

This is a local execution plan. NL remains read-only.

Current authoritative evidence:

```text
vpn snapshot: nl-diagnostics/snapshots/20260527T154832Z
server profile: nl-diagnostics/nl-server-profile/20260527T173222Z
gap analysis: nl-diagnostics/nl-profile-gap-analysis-20260527T173222Z.md
provider packet: nl-diagnostics/provider-incident-packets/provider-incident-packet-20260527T154832Z.md
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
NL transport: advisory, main/443 and secondary/2083 healthy
NL provider_status: recent_boot_gap
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

Fresh gap summary:

```json
{
  "local_name_drift": 7,
  "missing_local_source": 2,
  "redacted_review_only": 2,
  "same_hash_elsewhere": 15,
  "server_backup_only": 4,
  "server_runtime_artifact": 4
}
```

First promote/reconstruct candidates:

```text
ghost-access/run_vpn_service_access_agent.py
ghost-access/run_vpn_delivery_canary.py
ghost-access/xray_runtime_user_manager.py
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
manual failover profile doc for nl-beta / reserve path
alert when boot gap appears after an unclean shutdown
```

Acceptance:

```text
provider incident can be opened with exact boot window and current service state
local healing does not hide provider/host incidents
manual profile switch never happens from stale evidence
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
recommended_action: continue local reconciliation and provider evidence tracking
do_not_restart_nl: true
do_not_deploy_to_nl: true
next_best_work: reconstruct/read-only review missing P1 source, then add tests
```

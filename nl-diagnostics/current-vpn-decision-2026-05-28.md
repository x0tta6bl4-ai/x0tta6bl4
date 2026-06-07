# Current VPN Decision

generated_at: `2026-06-06T15:33:58.431256+00:00`
snapshot: `/mnt/projects/nl-diagnostics/snapshots/20260606T125103Z`

## Status

decision: `restore_transport_canary_monitor`
confidence: `high`
reason: core VPN has live TCP/x-ui evidence, but transport canary evidence is not configured

## Current State

```text
overall_status=advisory
transport_status=degraded
telegram_media_status=healthy
provider_status=historical_incident
failure_domain=monitoring
recommended_action=restore_transport_canary_monitor
blocking_category=monitoring_gap
blocking_history_trend=has_degradation
blocking_history_snapshots=15
nl_mutation_allowed=false
auto_profile_switch_allowed=false
spb_fallback_allowed=false
```

## Next Actions

- run the local dry-run/precheck for restoring ghost-access-vpn-monitor.timer
- apply the monitor restore only after explicit approval
- collect a fresh read-only snapshot after the monitor evidence is refreshed

## Blocked Actions

- do not restart x-ui from app/blocking evidence alone
- do not change NL without explicit write approval
- do not auto-switch VPN profile
- do not use SPB as fallback while SPB is disabled

## Warnings

- NL Reality transport canary monitor is not configured

## Problems

- NL transport_status=degraded

## Evidence

- local vpn_status_json overall=advisory
- route to VPN server bypasses singbox_tun
- external exit IP is VPN server
- watchdog proxy healthy
- packet_loss_percent=0
- NL systemctl --failed empty
- NL key services active
- NL core listeners 443/2083/39829 present
- historical provider shutdown signal present

## Blocking Probe History

```text
snapshot_count=15
trend=has_degradation
latest_snapshot=20260606T125103Z
latest_targets_ok=0/8
latest_degraded_targets=8
```

No NL or SPB writes were performed by this report.

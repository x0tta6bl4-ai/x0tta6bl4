# Current VPN Decision

generated_at: `2026-07-02T13:55:13.838707+00:00`
snapshot: `/mnt/projects/nl-diagnostics/snapshots/20260702T135431Z`

## Status

decision: `provider_ticket`
confidence: `high`
reason: classification points to provider or host failure

## Current State

```text
overall_status=provider_outage
transport_status=healthy
telegram_media_status=healthy
provider_status=suspect_active
failure_domain=provider_host
recommended_action=provider_ticket
blocking_category=provider_or_host_issue
blocking_history_trend=has_degradation
blocking_history_snapshots=22
nl_mutation_allowed=false
auto_profile_switch_allowed=false
spb_fallback_allowed=false
```

## Next Actions

- build or refresh provider incident packet
- keep NL mutation blocked until provider symptoms are understood

## Blocked Actions

- do not restart x-ui from app/blocking evidence alone
- do not change NL without explicit write approval
- do not auto-switch VPN profile
- do not use SPB as fallback while SPB is disabled

## Warnings

- NL non-critical failed units: ifup@eth0.service

## Problems

- none

## Evidence

- local vpn_status_json overall=advisory
- route to VPN server bypasses singbox_tun
- generic traffic routes through singbox_tun
- external exit IP is VPN server
- packet_loss_percent=0
- NL failed units are known non-critical: ifup@eth0.service
- NL key services active
- NL core listeners 443/2083/39829 present
- NL transport_status=healthy

## Blocking Probe History

```text
snapshot_count=22
trend=has_degradation
latest_snapshot=20260702T135431Z
latest_targets_ok=8/8
latest_degraded_targets=0
```

No NL or SPB writes were performed by this report.

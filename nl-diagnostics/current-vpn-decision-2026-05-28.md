# Current VPN Decision

generated_at: `2026-07-17T18:26:19.620475+00:00`
snapshot: `/mnt/projects/nl-diagnostics/snapshots/20260717T182536Z`

## Status

decision: `local_fix`
confidence: `high`
reason: local client path is critical

## Current State

```text
overall_status=critical
transport_status=unknown
telegram_media_status=unknown
provider_status=normal
failure_domain=local_client
recommended_action=local_soft_heal
blocking_category=local_client_issue
blocking_history_trend=has_degradation
blocking_history_snapshots=23
nl_mutation_allowed=false
auto_profile_switch_allowed=false
spb_fallback_allowed=false
```

## Next Actions

- fix local route/SOCKS/client state first
- collect a new read-only snapshot after the local fix

## Blocked Actions

- do not restart x-ui from app/blocking evidence alone
- do not change NL without explicit write approval
- do not auto-switch VPN profile
- do not use SPB as fallback while SPB is disabled

## Warnings

- none

## Problems

- local vpn_status is not PASS
- route to VPN server may loop through tunnel
- NL critical failed units: ghost-access-live-subscription-payload-check.service
- NL transport_status=unknown

## Evidence

- generic traffic routes through singbox_tun
- external exit IP is VPN server
- packet_loss_percent=0
- NL key services active
- NL core listeners 443/2083/39829 present

## Blocking Probe History

```text
snapshot_count=23
trend=has_degradation
latest_snapshot=20260717T182536Z
latest_targets_ok=0/8
latest_degraded_targets=8
```

No NL or SPB writes were performed by this report.

# Current VPN Decision

generated_at: `2026-05-28T03:26:45.222779+00:00`
snapshot: `/mnt/projects/nl-diagnostics/snapshots/20260528T032605Z`

## Status

decision: `observe`
confidence: `high`
reason: core VPN is healthy/advisory and blocking probes show no direct-vs-SOCKS failure

## Current State

```text
overall_status=advisory
transport_status=advisory
telegram_media_status=degraded
provider_status=recent_boot_gap
failure_domain=external_network
recommended_action=observe
blocking_category=app_specific_degradation
blocking_history_trend=stable_no_probe_evidence
blocking_history_snapshots=10
nl_mutation_allowed=false
auto_profile_switch_allowed=false
spb_fallback_allowed=false
```

## Next Actions

- keep observing current VPN path
- when a user-visible outage happens, collect a fresh read-only snapshot with blocking probes
- test Telegram/media separately from core VPN transport
- keep provider boot gap on watch; build provider packet if transport degrades

## Blocked Actions

- do not restart x-ui from app/blocking evidence alone
- do not change NL without explicit write approval
- do not auto-switch VPN profile
- do not use SPB as fallback while SPB is disabled

## Warnings

- NL non-critical failed units: ifup@eth0.service
- NL boot gap seconds=21907
- NL previous boot ended uncleanly

## Problems

- none

## Evidence

- local vpn_status_json overall=ok
- route to VPN server bypasses singbox_tun
- generic traffic routes through singbox_tun
- external exit IP is VPN server
- watchdog proxy healthy
- packet_loss_percent=0
- NL failed units are known non-critical: ifup@eth0.service
- NL key services active
- NL core listeners 443/2083/39829 present
- NL transport_status=advisory
- NL current boot reports previous journal uncleanly shut down

## Blocking Probe History

```text
snapshot_count=10
trend=stable_no_probe_evidence
latest_snapshot=20260528T032605Z
latest_targets_ok=8/8
latest_degraded_targets=0
```

No NL or SPB writes were performed by this report.

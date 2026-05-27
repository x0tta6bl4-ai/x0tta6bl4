# NL Current State Refresh, 2026-05-27T06:48:44Z

## Status

Fresh read-only evidence was collected.

```text
NL writes: 0
snapshot: nl-diagnostics/snapshots/20260527T064844Z
profile: nl-diagnostics/nl-server-profile/20260527T064844Z
gap report: nl-diagnostics/nl-profile-gap-analysis-20260527T064844Z.md
```

## Snapshot Classification

```json
{
  "overall_status": "advisory",
  "transport_status": "healthy",
  "telegram_media_status": "degraded",
  "provider_status": "historical_incident",
  "runtime_mode": "degraded",
  "failure_domain": "external_network",
  "recommended_action": "observe",
  "mutation_allowed": false,
  "nl_mutation_allowed": false
}
```

Important evidence:

```text
local vpn_status PASS
route to VPN server bypasses singbox_tun
generic traffic routes through singbox_tun
external exit IP is VPN server
watchdog proxy healthy
packet_loss_percent=0
NL systemctl --failed empty
NL key services active
NL core listeners 443/2083/39829 present
NL transport_status=healthy
historical provider shutdown signal present
```

Interpretation:

```text
This is not a current x-ui outage.
VPN transport is healthy at the time of this read-only snapshot.
The current advisory state is driven by Telegram media/external network behavior.
The old NL runtime mode still says degraded because NL has not received the local semantic fix.
```

## Runtime-State Evidence

Current NL runtime summary:

```text
mode=degraded
reason=telegram media edges are slow from the current egress path
recommended_action=observe
best_path=main
best_path_port=443
primary_path_port=443
primary_path_latency_s=0.049001
secondary_path_port=2083
secondary_path_latency_s=0.057947
transport_health_status=healthy
telegram_media_status=degraded
subscription_health_status=healthy
warp_status=healthy
ghost_ready=true
```

Current x-ui shape:

```text
api: 127.0.0.1:62789
public Reality listeners: 39829, 443, 2083
outbounds: direct, warp, blocked
stats enabled: true
```

Local fix already prepared:

```text
transport healthy/advisory + telegram_media degraded -> advisory/observe
```

This fix is local only and has not been deployed to NL.

## Fresh Gap Summary

```json
{
  "local_name_drift": 7,
  "missing_local_source": 12,
  "redacted_review_only": 2,
  "same_hash_elsewhere": 5,
  "server_backup_only": 4,
  "server_runtime_artifact": 4
}
```

Compared with the earlier gap report, the two sensitive Ghost Access files are
now classified separately:

```text
redacted_review_only: 2
raw source saved locally: false
redacted files deployable: false
```

Intentional local drift remains:

```text
services/nl-server/mesh-runtime/vps_build_runtime_state.py differs from NL by design
services/nl-server/ghost-vpn/ghost_vpn_protocol.py differs from NL by local import-compat fallback
```

## Deploy Posture

Current deploy posture:

```text
local_ready_but_deploy_blocked
```

Reason:

```text
NL is still read-only by instruction.
Future deploy requires explicit approval, fresh snapshot/profile, backup commands,
rollback commands, and staged validation.
```

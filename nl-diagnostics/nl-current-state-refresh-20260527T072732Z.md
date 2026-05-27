# NL Current State Refresh, 2026-05-27T07:27:32Z

## Status

Fresh read-only evidence was collected.

```text
NL writes: 0
snapshot: nl-diagnostics/snapshots/20260527T072732Z
profile: nl-diagnostics/nl-server-profile/20260527T072838Z
gap report: nl-diagnostics/nl-profile-gap-analysis-20260527T072838Z.md
```

## Snapshot Classification

```json
{
  "overall_status": "advisory",
  "transport_status": "advisory",
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
local vpn_status_json overall=ok
route to VPN server bypasses singbox_tun
generic traffic routes through singbox_tun
external exit IP is VPN server
watchdog proxy healthy
packet_loss_percent=0
NL systemctl --failed empty
NL key services active
NL core listeners 443/2083/39829 present
NL transport_status=advisory
historical provider shutdown signal present
```

Interpretation:

```text
This is not a current x-ui outage.
The local client status is ok by vpn_status.json.
The combined advisory state is still driven by NL runtime Telegram media/external network behavior.
No mutation was performed on NL.
```

## Local JSON Status

New snapshot evidence:

```text
local/vpn_status.json
```

Current values:

```json
{
  "overall_status": "ok",
  "transport_status": "healthy",
  "failure_domain": "none",
  "recommended_action": "observe",
  "mutation_allowed": false,
  "nl_mutation_allowed": false,
  "vpn_server": "89.125.1.107",
  "vpn_port": 39829,
  "socks_port": 10918,
  "packet_loss_percent": 0
}
```

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

This is unchanged from the prior fresh profile, which means the new local JSON
diagnostic work did not change the NL source reconciliation surface.

## Deploy Posture

```text
local_ready_but_deploy_blocked
NL write permission: false
recommended action: continue local reconciliation and planning
```

# VPN Operator Card

generated_at: `2026-05-28T01:11:40.320530+00:00`
snapshot: `/mnt/projects/nl-diagnostics/snapshots/20260528T000600Z`

## Status

```text
operator_status=observe
plain_action=VPN core is healthy. Do not restart NL; collect fresh evidence during the next visible outage.
decision=observe
confidence=high
overall_status=advisory
transport_status=healthy
telegram_media_status=degraded
provider_status=recent_boot_gap
failure_domain=external_network
blocking_history_trend=stable_no_probe_evidence
blocking_history_snapshot_count=5
manual_failover_status=planning_not_active
nl_mutation_allowed=false
spb_fallback_allowed=false
automatic_failover_allowed=false
```

## First Commands

### incident_readonly_refresh

```bash
VPN_ENABLE_BLOCKING_PROBES=1 /mnt/projects/nl-diagnostics/run_vpn_incident_readonly_refresh.sh
```

Expected: prints snapshot path and refresh report path; vpn-planning-refresh ok=true

Writes: local snapshot and local reports only; NL read-only commands only

### read_decision

```bash
sed -n '1,120p' /mnt/projects/nl-diagnostics/vpn-planning-refresh-2026-05-28.md
```

Expected: decision, confidence, blocking trend, failover status

Writes: none

## Decision Table

| When | Do | Do Not |
|---|---|---|
| `decision=observe` | observe; test affected app/media path separately | restart x-ui, change NL, auto-switch profile, use SPB |
| `decision=local_fix` | fix local route/SOCKS/client first | touch NL before local client is healthy |
| `decision=provider_ticket` | build provider packet from fresh snapshot | restart services to mask provider or host symptoms |
| `decision=manual_profile_review` | manual profile review only after fresh evidence and explicit approval | automatic profile switch |
| `decision=nl_readonly_review` | inspect NL services/listeners read-only and prepare backup/rollback | write to NL without separate approval |

## Blocked Actions

- do not restart x-ui from app/blocking evidence alone
- do not change NL without explicit write approval
- do not auto-switch VPN profile
- do not use SPB as fallback while SPB is disabled
- do not store raw VPN URIs, UUIDs, private keys, or bot tokens in reports

No NL or SPB writes were performed by this card builder.

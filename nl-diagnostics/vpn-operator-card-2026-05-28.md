# VPN Operator Card

generated_at: `2026-07-02T13:55:15.874611+00:00`
snapshot: `/mnt/projects/nl-diagnostics/snapshots/20260702T135431Z`

## Status

```text
operator_status=provider_ticket
plain_action=Build a provider packet; do not hide provider symptoms with restarts.
decision=provider_ticket
confidence=high
overall_status=provider_outage
transport_status=healthy
telegram_media_status=healthy
provider_status=suspect_active
failure_domain=provider_host
blocking_history_trend=has_degradation
blocking_history_snapshot_count=22
manual_failover_status=manual_failover_candidate
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

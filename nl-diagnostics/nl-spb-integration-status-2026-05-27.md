# NL SPB Integration Status

Status: SPB standalone Xray is disabled and not used in the current VPN path.

## What This Means

- Do not use SPB sync as a recovery action for NL VPN incidents.
- Keep `services/nl-server/ghost-access/sync_spb_standalone_clients.py` as local
  reconciliation evidence only.
- Treat the script as class C review-only source because it can write remote SPB
  Xray config and restart remote `xray`.
- Future SPB reactivation requires explicit approval, a fresh SPB profile,
  config backup command, rollback command, and a dry-run gate.

No NL or SPB writes were performed.

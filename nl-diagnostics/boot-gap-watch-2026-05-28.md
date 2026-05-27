# Boot Gap Watch

generated_at: `2026-05-27T23:40:36.626368+00:00`
snapshot: `nl-diagnostics/snapshots/20260527T230246Z`

## Summary

```text
status=watch
boot_gap_seconds=21907
overall_status=advisory
transport_status=healthy
provider_status=recent_boot_gap
failure_domain=external_network
recommended_action=observe provider signal; do not restart NL while transport is healthy/advisory
nl_mutation_allowed=false
spb_fallback_allowed=false
automatic_failover_allowed=false
```

## Boot Window

```text
previous_boot_first_entry=Wed 2026-05-27 02:50:41 UTC
previous_boot_last_entry=Wed 2026-05-27 08:53:30 UTC
current_boot_first_entry=Wed 2026-05-27 14:58:37 UTC
```

## Unclean Boot Lines

- May 27 14:58:38 01164.com systemd-journald[302]: File /var/log/journal/e4584c4328b15cd591d7d5c553802e8a/system.journal corrupted or uncleanly shut down, renaming and replacing.

## Provider Signal Lines

- none

No NL or SPB writes were performed by this boot-gap watch report.

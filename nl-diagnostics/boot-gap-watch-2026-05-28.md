# Boot Gap Watch

generated_at: `2026-06-06T12:58:06.166716+00:00`
snapshot: `/mnt/projects/nl-diagnostics/snapshots/20260606T125103Z`

## Summary

```text
status=provider_ticket
boot_gap_seconds=9
overall_status=provider_outage
transport_status=degraded
provider_status=suspect_active
failure_domain=provider_host
recommended_action=build provider incident packet from the same fresh snapshot
nl_mutation_allowed=false
spb_fallback_allowed=false
automatic_failover_allowed=false
```

## Boot Window

```text
previous_boot_first_entry=Sat 2026-06-06 01:40:12 UTC
previous_boot_last_entry=Sat 2026-06-06 08:34:22 UTC
current_boot_first_entry=Sat 2026-06-06 08:34:31 UTC
```

## Unclean Boot Lines

- none

## Provider Signal Lines

- Jun 06 08:34:07 01164.com qemu-ga[961]: info: guest-shutdown called, mode: powerdown
- Jun 06 08:34:07 01164.com systemd-logind[656]: System is powering down (hypervisor initiated shutdown).

No NL or SPB writes were performed by this boot-gap watch report.

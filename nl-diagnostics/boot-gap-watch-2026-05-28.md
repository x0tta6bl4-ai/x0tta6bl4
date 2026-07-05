# Boot Gap Watch

generated_at: `2026-07-02T13:55:13.939921+00:00`
snapshot: `/mnt/projects/nl-diagnostics/snapshots/20260702T135431Z`

## Summary

```text
status=provider_ticket
boot_gap_seconds=15
overall_status=provider_outage
transport_status=healthy
provider_status=suspect_active
failure_domain=provider_host
recommended_action=build provider incident packet from the same fresh snapshot
nl_mutation_allowed=false
spb_fallback_allowed=false
automatic_failover_allowed=false
```

## Boot Window

```text
previous_boot_first_entry=Thu 2026-07-02 06:50:26 UTC
previous_boot_last_entry=Thu 2026-07-02 09:48:58 UTC
current_boot_first_entry=Thu 2026-07-02 09:49:13 UTC
```

## Unclean Boot Lines

- none

## Provider Signal Lines

- Jul 02 09:48:53 01164.com qemu-ga[858]: info: guest-shutdown called, mode: powerdown
- Jul 02 09:48:53 01164.com systemd-logind[662]: System is powering down (hypervisor initiated shutdown).

No NL or SPB writes were performed by this boot-gap watch report.

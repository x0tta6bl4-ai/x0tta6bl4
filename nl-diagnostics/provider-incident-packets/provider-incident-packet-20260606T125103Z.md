# Provider Incident Packet, 2026-06-06T12:58:07.065841+00:00

## Status

```text
packet_type: provider_ticket
decision_reason: current evidence points to provider or host failure
snapshot: /mnt/projects/nl-diagnostics/snapshots/20260606T125103Z
snapshot_age_seconds: 424
snapshot_stale: False
NL writes: 0
```

## Current VPN Classification

```text
overall_status: provider_outage
failure_domain: provider_host
recommended_action: provider_ticket
transport_status: degraded
telegram_media_status: healthy
provider_status: suspect_active
runtime_recommended_action: observe
warnings: []
```

Profile switch policy:

```json
{
  "automatic_allowed": false,
  "decision": "observe",
  "manual_allowed": false,
  "manual_review_required": false,
  "nl_mutation_allowed": false,
  "reason": "runtime_recommended_action=observe",
  "requires_fresh_snapshot": false
}
```

## Local Client Evidence

```text
local_overall_status: advisory
local_failure_domain: none
exit_ip: 89.125.1.107
packet_loss_percent: 0
tcp_connections: {'close_wait': 0, 'established': 1, 'fin_wait_2': 0}
```

## NL Runtime Evidence

```text
mode: primary
reason: primary and secondary public ingress paths healthy
recommended_action: observe
transport_health_status: degraded
telegram_media_status: healthy
best_path_port: 443
```

## Provider Evidence

Current snapshot shutdown lines:

```text
Jun 06 08:34:07 01164.com qemu-ga[961]: info: guest-shutdown called, mode: powerdown
Jun 06 08:34:07 01164.com systemd-logind[656]: System is powering down (hypervisor initiated shutdown).
```

Current boot unclean-shutdown lines:

```text
none
```

Historical shutdown lines:

```text
May 26 10:18:29 01164.com qemu-ga[785]: info: guest-shutdown called, mode: powerdown
May 26 10:19:14 01164.com systemd-logind[641]: System is powering down (hypervisor initiated shutdown).
```

Boot window:

```text
previous_boot_first_entry: Sat 2026-06-06 01:40:12 UTC
previous_boot_last_entry: Sat 2026-06-06 08:34:22 UTC
current_boot_first_entry: Sat 2026-06-06 08:34:31 UTC
```

Host metrics:

```text
historical_max_cpu_steal: 43.78%
historical_max_load_average: 31.09
historical_max_disk_await: 187 ms
current_cpu_steal_percent: 0.0
```

## Provider Ticket Text

```text
Hello. Please check the host node for VPS 01164.com / IP 89.125.1.107.

The selected guest snapshot shows evidence of a hypervisor-initiated shutdown:
- Jun 06 08:34:07 01164.com qemu-ga[961]: info: guest-shutdown called, mode: powerdown
- Jun 06 08:34:07 01164.com systemd-logind[656]: System is powering down (hypervisor initiated shutdown).

Boot window from guest journal:
- previous boot last entry: Sat 2026-06-06 08:34:22 UTC
- current boot first entry: Sat 2026-06-06 08:34:31 UTC

Host-side degradation observed before shutdown:
- CPU steal reached: 43.78%
- load average reached: 31.09
- vda disk await reached: 187 ms

Please confirm whether there was host maintenance, node overload, storage degradation, or an automated power action.
```

## Local Rule

This packet is local evidence only. It does not permit NL mutation, service restart, x-ui DB edit, or deploy.

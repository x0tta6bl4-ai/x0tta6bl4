# Provider Incident Packet, 2026-06-01T19:17:25.795786+00:00

## Status

```text
packet_type: historical_provider_incident
decision_reason: historical hypervisor shutdown evidence is present; current VPN is not in provider outage
snapshot: /mnt/projects/nl-diagnostics/snapshots/20260601T191625Z
snapshot_age_seconds: 60
snapshot_stale: False
NL writes: 0
```

## Current VPN Classification

```text
overall_status: advisory
failure_domain: external_network
recommended_action: observe
transport_status: advisory
telegram_media_status: degraded
provider_status: historical_incident
runtime_recommended_action: observe
warnings: ['NL non-critical failed units: ifup@eth0.service']
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
local_overall_status: ok
local_failure_domain: none
exit_ip: 89.125.1.107
packet_loss_percent: 0
tcp_connections: {'close_wait': 0, 'established': 7, 'fin_wait_2': 0}
```

## NL Runtime Evidence

```text
mode: degraded
reason: telegram media edges are slow from the current egress path
recommended_action: observe
transport_health_status: advisory
telegram_media_status: degraded
best_path_port: 2083
```

## Provider Evidence

Current snapshot shutdown lines:

```text
Jun 01 07:50:48 01164.com qemu-ga[949]: info: guest-shutdown called, mode: powerdown
Jun 01 07:50:48 01164.com systemd-logind[656]: System is powering down (hypervisor initiated shutdown).
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
previous_boot_first_entry: Sun 2026-05-31 17:22:36 UTC
previous_boot_last_entry: Mon 2026-06-01 07:50:59 UTC
current_boot_first_entry: Mon 2026-06-01 07:51:07 UTC
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
- Jun 01 07:50:48 01164.com qemu-ga[949]: info: guest-shutdown called, mode: powerdown
- Jun 01 07:50:48 01164.com systemd-logind[656]: System is powering down (hypervisor initiated shutdown).

Boot window from guest journal:
- previous boot last entry: Mon 2026-06-01 07:50:59 UTC
- current boot first entry: Mon 2026-06-01 07:51:07 UTC

Host-side degradation observed before shutdown:
- CPU steal reached: 43.78%
- load average reached: 31.09
- vda disk await reached: 187 ms

Please confirm whether there was host maintenance, node overload, storage degradation, or an automated power action.
```

## Local Rule

This packet is local evidence only. It does not permit NL mutation, service restart, x-ui DB edit, or deploy.

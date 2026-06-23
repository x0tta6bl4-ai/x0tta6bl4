# Provider Incident Packet, 2026-06-06T06:20:21.422175+00:00

## Status

```text
packet_type: historical_provider_incident
decision_reason: historical provider shutdown evidence is present; current VPN is not in provider outage
snapshot: /mnt/projects/nl-diagnostics/snapshots/20260606T061939Z
snapshot_age_seconds: 42
snapshot_stale: False
NL writes: 0
```

## Current VPN Classification

```text
overall_status: critical
failure_domain: local_client
recommended_action: local_soft_heal
transport_status: advisory
telegram_media_status: degraded
provider_status: normal
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
local_overall_status: critical
local_failure_domain: local_client
exit_ip: 104.167.199.71
packet_loss_percent: 0
tcp_connections: {'close_wait': 0, 'established': 1, 'fin_wait_2': 0}
```

## NL Runtime Evidence

```text
mode: advisory
reason: telegram media edges are slow, but VPN transport is usable
recommended_action: observe
transport_health_status: advisory
telegram_media_status: degraded
best_path_port: 2083
```

## Provider Evidence

Current snapshot shutdown lines:

```text
none
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
previous_boot_first_entry: None
previous_boot_last_entry: None
current_boot_first_entry: Fri 2026-06-05 17:55:19 UTC
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

The selected guest snapshot shows a boot gap, but no explicit hypervisor-initiated shutdown line was found in the available journal.

Historical related shutdown evidence from a previous incident:
- May 26 10:18:29 01164.com qemu-ga[785]: info: guest-shutdown called, mode: powerdown
- May 26 10:19:14 01164.com systemd-logind[641]: System is powering down (hypervisor initiated shutdown).

Boot window from guest journal:
- previous boot last entry: unknown
- current boot first entry: Fri 2026-06-05 17:55:19 UTC

Host-side degradation observed before shutdown:
- CPU steal reached: 43.78%
- load average reached: 31.09
- vda disk await reached: 187 ms

Please confirm whether there was host maintenance, node overload, storage degradation, or an automated power action.
```

## Local Rule

This packet is local evidence only. It does not permit NL mutation, service restart, x-ui DB edit, or deploy.

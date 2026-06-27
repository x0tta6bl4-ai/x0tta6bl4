# Provider Incident Packet, 2026-05-27T08:31:17.256781+00:00

## Status

```text
packet_type: historical_provider_incident
decision_reason: historical hypervisor shutdown evidence is present; current VPN is not in provider outage
snapshot: /mnt/projects/nl-diagnostics/snapshots/20260527T072732Z
snapshot_age_seconds: 3825
snapshot_stale: True
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
```

## Local Client Evidence

```text
local_overall_status: ok
local_failure_domain: none
exit_ip: 89.125.1.107
packet_loss_percent: 0
tcp_connections: {'close_wait': 0, 'established': 12, 'fin_wait_2': 0}
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

Shutdown lines:

```text
May 26 10:18:29 01164.com qemu-ga[785]: info: guest-shutdown called, mode: powerdown
May 26 10:19:14 01164.com systemd-logind[641]: System is powering down (hypervisor initiated shutdown).
May 26 10:18:29 01164.com qemu-ga[785]: info: guest-shutdown called, mode: powerdown
May 26 10:19:14 01164.com systemd-logind[641]: System is powering down (hypervisor initiated shutdown).
`hypervisor initiated shutdown` означает, что выключение пришло с хост-машины провайдера, а не изнутри VPS.
May 26 10:18:29 01164.com qemu-ga[785]: info: guest-shutdown called, mode: powerdown
May 26 10:19:14 01164.com systemd-logind[641]: System is powering down (hypervisor initiated shutdown).
```

Boot window:

```text
previous_boot_first_entry: Mon 2026-05-25 18:43:23 UTC
previous_boot_last_entry: Tue 2026-05-26 10:21:04 UTC
current_boot_first_entry: Wed 2026-05-27 02:50:41 UTC
```

Host metrics:

```text
historical_max_cpu_steal: 43.78%
historical_max_load_average: 31.09
historical_max_disk_await: 187 ms
current_cpu_steal_percent: 0.18
```

## Provider Ticket Text

```text
Hello. Please check the host node for VPS 01164.com / IP 89.125.1.107.

The guest shows evidence of a hypervisor-initiated shutdown:
- May 26 10:18:29 01164.com qemu-ga[785]: info: guest-shutdown called, mode: powerdown
- May 26 10:19:14 01164.com systemd-logind[641]: System is powering down (hypervisor initiated shutdown).
- May 26 10:18:29 01164.com qemu-ga[785]: info: guest-shutdown called, mode: powerdown
- May 26 10:19:14 01164.com systemd-logind[641]: System is powering down (hypervisor initiated shutdown).

Boot window from guest journal:
- previous boot last entry: Tue 2026-05-26 10:21:04 UTC
- current boot first entry: Wed 2026-05-27 02:50:41 UTC

Host-side degradation observed before shutdown:
- CPU steal reached: 43.78%
- load average reached: 31.09
- vda disk await reached: 187 ms

Please confirm whether there was host maintenance, node overload, storage degradation, or an automated power action.
```

## Local Rule

This packet is local evidence only. It does not permit NL mutation, service restart, x-ui DB edit, or deploy.

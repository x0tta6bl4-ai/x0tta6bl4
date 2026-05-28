# Provider Incident Packet, 2026-05-28T03:14:57.726907+00:00

## Status

```text
packet_type: provider_watch
decision_reason: recent NL boot gap is present; current VPN transport is healthy
snapshot: /mnt/projects/nl-diagnostics/snapshots/20260528T031418Z
snapshot_age_seconds: 39
snapshot_stale: False
NL writes: 0
```

## Current VPN Classification

```text
overall_status: advisory
failure_domain: external_network
recommended_action: observe
transport_status: healthy
telegram_media_status: degraded
provider_status: recent_boot_gap
runtime_recommended_action: observe
warnings: ['NL non-critical failed units: ifup@eth0.service', 'NL boot gap seconds=21907', 'NL previous boot ended uncleanly']
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
tcp_connections: {'close_wait': 0, 'established': 10, 'fin_wait_2': 0}
```

## NL Runtime Evidence

```text
mode: degraded
reason: telegram media edges are slow from the current egress path
recommended_action: observe
transport_health_status: healthy
telegram_media_status: degraded
best_path_port: 443
```

## Provider Evidence

Current snapshot shutdown lines:

```text
none
```

Current boot unclean-shutdown lines:

```text
May 27 14:58:38 01164.com systemd-journald[302]: File /var/log/journal/e4584c4328b15cd591d7d5c553802e8a/system.journal corrupted or uncleanly shut down, renaming and replacing.
```

Historical shutdown lines:

```text
May 26 10:18:29 01164.com qemu-ga[785]: info: guest-shutdown called, mode: powerdown
May 26 10:19:14 01164.com systemd-logind[641]: System is powering down (hypervisor initiated shutdown).
```

Boot window:

```text
previous_boot_first_entry: Wed 2026-05-27 02:50:41 UTC
previous_boot_last_entry: Wed 2026-05-27 08:53:30 UTC
current_boot_first_entry: Wed 2026-05-27 14:58:37 UTC
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

The current boot journal also reports an unclean previous shutdown:
- May 27 14:58:38 01164.com systemd-journald[302]: File /var/log/journal/e4584c4328b15cd591d7d5c553802e8a/system.journal corrupted or uncleanly shut down, renaming and replacing.

Boot window from guest journal:
- previous boot last entry: Wed 2026-05-27 08:53:30 UTC
- current boot first entry: Wed 2026-05-27 14:58:37 UTC

Host-side degradation observed before shutdown:
- CPU steal reached: 43.78%
- load average reached: 31.09
- vda disk await reached: 187 ms

Please confirm whether there was host maintenance, node overload, storage degradation, or an automated power action.
```

## Local Rule

This packet is local evidence only. It does not permit NL mutation, service restart, x-ui DB edit, or deploy.

# NL Transport Probe

generated_at: `2026-07-20T16:56:53.444101+00:00`
host: `89.125.1.107`

## Summary

```text
status=degraded
ok_count=1/3
failure_domain_hint=nl_or_provider_or_path
recommended_action=collect fresh read-only snapshot and compare NL listeners
nl_mutation_allowed=false
spb_fallback_allowed=false
automatic_failover_allowed=false
```

## Ports

| Port | OK | Latency ms | Error |
|---|---|---:|---|
| `443` | `true` | `72.801` |  |
| `2083` | `false` | `None` | [Errno 111] Connection refused |
| `39829` | `false` | `None` | [Errno 111] Connection refused |

No NL or SPB writes were performed by this transport probe.

# x0tta6bl4 On-Call Runbooks

Runbooks for common production incidents. Each runbook includes:
triage steps, root cause paths, mitigations, and escalation paths.

**MTTR target**: < 30 min for all P1 incidents.

---

## Index

| Runbook | Alert(s) | Severity |
|---------|----------|----------|
| [REDIS_FAILURE.md](REDIS_FAILURE.md) | `RedisUnavailable`, `RedisHighMemoryUsage` | Critical |
| [CIRCUIT_BREAKER_OPEN.md](CIRCUIT_BREAKER_OPEN.md) | `CircuitBreakerOpen`, `MaaSBillingFailure` | Warning/Critical |
| [HIGH_LATENCY.md](HIGH_LATENCY.md) | `MaaSHighLatencyP95`, `DatabaseQuerySlowP99` | Warning/Critical |
| [HIGH_ERROR_RATE.md](HIGH_ERROR_RATE.md) | `MaaSHighErrorRate`, `MaaSCriticalErrorRate` | Warning/Critical |
| [MAAS_ESCROW_FAILURE.md](MAAS_ESCROW_FAILURE.md) | `MaaSEscrowFailureSpike`, `MaaSNodeHeartbeatMissing` | Warning |
| [../operations/INCIDENT_RESPONSE_PLAN.md](../operations/INCIDENT_RESPONSE_PLAN.md) | — | P0 Escalation |
| [../operations/DISASTER_RECOVERY_PLAN.md](../operations/DISASTER_RECOVERY_PLAN.md) | — | DR |
| [../operations/db-migration-rollback-runbook.md](../operations/db-migration-rollback-runbook.md) | — | DB migration |

---

## Alert → Runbook mapping

Alert names correspond to rules in [`docs/monitoring/prometheus_alerts.yaml`](../monitoring/prometheus_alerts.yaml).

```
RedisUnavailable              → REDIS_FAILURE.md
RedisHighMemoryUsage          → REDIS_FAILURE.md
RedisConnectionPoolExhausted  → REDIS_FAILURE.md
CircuitBreakerOpen            → CIRCUIT_BREAKER_OPEN.md
CircuitBreakerFlapping        → CIRCUIT_BREAKER_OPEN.md
MaaSHighLatencyP95            → HIGH_LATENCY.md
MaaSCriticalLatencyP99        → HIGH_LATENCY.md
DatabaseQuerySlowP99          → HIGH_LATENCY.md
DatabaseConnectionPoolExhausted → HIGH_LATENCY.md
MaaSHighErrorRate             → HIGH_ERROR_RATE.md
MaaSCriticalErrorRate         → HIGH_ERROR_RATE.md
MaaSEscrowFailureSpike        → MAAS_ESCROW_FAILURE.md
MaaSNodeHeartbeatMissing      → MAAS_ESCROW_FAILURE.md
MaaSBillingFailure            → CIRCUIT_BREAKER_OPEN.md
```

---

## Escalation chain

1. **On-call engineer** — primary responder, follows runbook
2. **Platform lead** — escalation at T+15 min if no resolution
3. **Engineering director** — escalation at T+30 min if SLA breach
4. **VP Engineering** — customer-facing impact > 30 min

---

## Adding a new runbook

1. Copy the template structure (symptoms / triage / root causes / mitigation / verify / post-incident / escalation)
2. Add the alert → runbook mapping to this README
3. Reference the runbook `url` field in `prometheus_alerts.yaml`

# Manual Failover Readiness

generated_at: `2026-06-06T12:58:09.994813+00:00`

## Status

```text
status=blocked_missing_secondary
manual_probe_allowed=false
manual_switch_allowed=false
decision=provider_ticket
transport_status=degraded
failure_domain=provider_host
provider_status=suspect_active
manual_failover_status=manual_failover_candidate
secondary_probe_status=planning_template
candidate_configured=false
spb_excluded=true
nl_write_allowed=false
automatic_failover_allowed=false
```

## Gates

| ID | Status | Gate | Next Step |
|---|---|---|---|
| `TRIGGER-01` | `pass` | Incident evidence justifies considering failover | stay on observe while NL transport is healthy and no incident trigger exists |
| `LOCAL-01` | `pass` | Local client is not the failure domain | fix local route/SOCKS/client before any failover work |
| `SECONDARY-01` | `blocked` | Secondary exit candidate is configured | choose a new non-SPB provider/region and generate a safe public probe config |
| `SECONDARY-02` | `blocked` | Secondary exit health is verified enough for the requested action | run probe_secondary_exit.py against the secondary public endpoint before any profile test |
| `SPB-01` | `pass` | SPB is excluded from failover | do not use SPB or SPB sync scripts as emergency recovery |
| `MANUAL-01` | `pass` | Failover remains manual and NL read-only | keep switching manual-only and keep NL unchanged during failover diagnosis |

## Evidence

### TRIGGER-01

- decision=provider_ticket
- failure_domain=provider_host
- transport_status=degraded
- provider_status=suspect_active

### LOCAL-01

- decision=provider_ticket
- failure_domain=provider_host

### SECONDARY-01

- secondary_status=planning_template
- candidate_configured=false
- candidate_label=secondary-placeholder
- candidate_provider=TBD-new-provider-not-NL-not-SPB
- candidate_region=TBD-new-region

### SECONDARY-02

- secondary_status=planning_template

### SPB-01

- failover_spb_fallback_allowed=false
- secondary_spb_fallback_allowed=false
- candidate_configured=false
- candidate_has_spb_marker=false

### MANUAL-01

- automatic_failover_allowed=false
- nl_mutation_allowed=false
- secondary_automatic_failover_allowed=false
- secondary_nl_mutation_allowed=false

No NL or SPB writes were performed by this failover readiness gate.

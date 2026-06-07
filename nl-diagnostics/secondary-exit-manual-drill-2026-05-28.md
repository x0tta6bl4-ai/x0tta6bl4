# Secondary Exit Manual Drill

generated_at: `2026-06-06T12:58:13.267770+00:00`
status: `drill_plan_ready_blocked_no_endpoint`
ok: `true`

## Summary

```text
manual_probe_allowed=false
manual_switch_allowed=false
candidate_configured=false
endpoint_count=0
secondary_flow_status=blocked_missing_candidate
secondary_probe_status=planning_template
provisioning_plan_status=provisioning_plan_ready_no_endpoint
test_scope=single_client
bulk_user_switch_allowed=false
rollback_required=true
safe_flags=true
nl_write_allowed=false
spb_fallback_allowed=false
automatic_failover_allowed=false
```

## Gates

| ID | Status | Gate | Next Step |
|---|---|---|---|
| `DRILL-01` | `blocked` | Use one manually controlled test client only | keep drill blocked until failover readiness permits a test-client profile check |
| `DRILL-02` | `blocked` | Public secondary endpoint exists before profile testing | provision the secondary endpoint and add only public metadata before testing |
| `DRILL-03` | `blocked` | Probe endpoint before touching any client profile | run the public TCP probe after a candidate endpoint exists |
| `DRILL-04` | `blocked` | Manual switch remains test-only and reversible | activate only the test client, then immediately verify rollback to NL daily profile |
| `DRILL-05` | `pass` | Return-to-NL rollback is mandatory | after the drill, switch the test client back to NL and record the result |

## Evidence

### DRILL-01

- manual_probe_allowed=false
- test_scope=single_client
- bulk_user_switch_allowed=false

### DRILL-02

- candidate_configured=false
- endpoint_count=0
- secondary_flow_status=blocked_missing_candidate

### DRILL-03

- secondary_probe_status=planning_template
- probe_config_path=/mnt/projects/.tmp/secondary-exit-probe.json

### DRILL-04

- manual_switch_allowed=false
- automatic_failover_allowed=false
- rollback_required=true

### DRILL-05

- rollback_target=NL daily profile
- secondary_profile_final_state=inactive
- nl_write_allowed=false

## Test Client Steps

- Collect a fresh read-only incident snapshot first.
- Run the secondary public endpoint probe from local diagnostics.
- Activate the emergency secondary profile on exactly one test client only.
- Verify basic connectivity and expected exit behavior on that test client.
- Switch the test client back to the NL daily profile.
- Record pass/fail evidence in the local incident timeline.

## Rollback Checks

- test client uses NL daily profile again
- secondary profile is inactive
- no bulk user profile change was made
- NL was not changed
- SPB was not used

## Forbidden Material

- raw VPN URI
- UUID
- private key
- bot token
- subscription link
- provider API token
- SSH private key
- NL endpoint
- SPB endpoint

No NL or SPB writes were performed by this manual drill plan.

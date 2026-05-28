# Secondary Exit Flow

generated_at: `2026-05-28T03:42:22.116800+00:00`
status: `blocked_missing_candidate`
ok: `true`

## Summary

```text
candidate_score_status=missing_candidates
candidate_viable_count=0
top_candidate_label=none
secondary_probe_status=planning_template
candidate_configured=false
manual_probe_allowed=false
manual_switch_allowed=false
requirements_status=requirements_ready_no_candidate
missing_requirements=NET-01
nl_write_allowed=false
spb_fallback_allowed=false
automatic_failover_allowed=false
```

## Phases

| ID | Status | Phase | Next Step |
|---|---|---|---|
| `CANDIDATE-01` | `blocked` | Score non-NL/non-SPB public candidate metadata | fill public metadata for at least one independent non-NL/non-SPB provider candidate |
| `CONFIG-01` | `blocked` | Generate safe public probe config without profile secrets | generate /mnt/projects/.tmp/secondary-exit-probe.json from the top viable candidate |
| `PROBE-01` | `blocked` | Verify public TCP endpoint reachability | run probe_secondary_exit.py against the generated public probe config |
| `CLIENT-01` | `blocked` | Manual test-client profile activation is gated | activate a test client profile only during a real incident and only after endpoint probe passes |
| `SWITCH-01` | `blocked` | Manual switch remains blocked until healthy secondary and incident trigger | do not switch users until manual_switch_allowed=true in failover readiness |

## Safe Commands

```bash
python3 nl-diagnostics/create_secondary_exit_config.py --label <label> --provider <provider> --region <region> --host <public-host-or-ip> --tcp-port 443 --out /mnt/projects/.tmp/secondary-exit-probe.json
python3 nl-diagnostics/probe_secondary_exit.py --config /mnt/projects/.tmp/secondary-exit-probe.json --json-out /mnt/projects/.tmp/secondary-exit-probe-result.json
```

## Execution Rules

- Do not store raw VPN URIs, UUIDs, private keys, bot tokens, or subscription links.
- Do not use NL or SPB as the secondary exit.
- Do not run client exit verification until a test client profile is manually activated.
- Do not switch users until failover readiness sets manual_switch_allowed=true.

No NL or SPB writes were performed by this secondary exit flow report.

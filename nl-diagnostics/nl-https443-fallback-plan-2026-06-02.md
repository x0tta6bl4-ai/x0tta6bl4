# NL HTTPS 443 Fallback Plan

generated_at: `2026-06-02T19:14:27.837042+00:00`
decision: `HTTPS443_FALLBACK_REQUIRED`
status: `ready_to_prepare_secondary_https443_endpoint`
ok: `true`

## Summary

```text
profile_dir=/mnt/projects/nl-diagnostics/nl-server-profile/20260602T181820Z
server_state_verified=true
current_gap_verified=true
user_report_all_config_ports_failed=true
work_network_cause_verified=false
verified_gap=no XHTTP/WS fallback on public standard HTTPS 443
public_443_owner=xray
public_443_protocol=VLESS Reality TCP
fallback_transport=xhttp
fallback_public_port=8443
local_transport_probe_status=healthy
recommended_primary_path=new_or_independent_https443_endpoint
in_place_nl_443_change_allowed_now=false
nl_write_allowed=false
spb_fallback_allowed=false
automatic_failover_allowed=false
```

## Gates

| ID | Status | Gate | Next Step |
|---|---|---|---|
| `STATE-01` | `pass` | Current NL 443 owner is known | refresh the read-only NL profile before any future staging |
| `FALLBACK-01` | `pass` | Existing fallback is on 8443, not standard 443 | stop treating additional port tries as the main fix |
| `USER-01` | `pass` | User reports every configured port failed | treat the work-network cause as unverified but stop relying on current ports |
| `BLAST-01` | `blocked` | In-place 443 move would affect existing Reality users | do not move public 443 from Reality to nginx until a tested replacement path exists |
| `SECONDARY-01` | `ready` | Independent HTTPS 443 endpoint is the low-blast-radius path | provision and validate a non-NL/non-SPB endpoint with public HTTPS 443 before user migration |

## Recommended Path

- `PREP-01` Keep current NL Reality 443 alive during preparation
- `EDGE-01` Prepare an independent public HTTPS 443 fallback endpoint
- `CANARY-01` Canary with one admin client before subscription promotion
- `SUBSCRIPTION-01` Promote HTTPS 443 fallback first only after canary passes

## Rejected Shortcuts

- try more current ports
- move NL public 443 from Reality to nginx without tested replacement
- enable automatic failover
- use SPB fallback
- store raw VPN URIs or UUIDs in local reports

## Approval Gate

required_for_any_nl_write=true
confirm_token=`APPLY_HTTPS443_FALLBACK_PLAN`

Forbidden before confirm:
- restart x-ui
- reload nginx
- edit x-ui database
- edit /usr/local/x-ui/bin/config.json
- change systemd units on NL
- change bot subscription delivery on NL

## Acceptance Criteria

- public HTTPS 443 fallback endpoint exists and is not the current raw Reality listener
- XHTTP and WebSocket dataplane tests pass through public 443
- subscription output contains xhttp:443 before legacy Reality entries
- at least one work/restricted Wi-Fi client passes
- at least one mobile network client passes
- rollback keeps the old NL Reality 443 profile available

## Evidence

### STATE-01

- profile_dir=/mnt/projects/nl-diagnostics/nl-server-profile/20260602T181820Z
- public_443_owner=xray
- reality_443=true
- nginx_8443_owner=nginx

### FALLBACK-01

- audit_required_transport=xhttp
- audit_required_port=8443
- rollout_has_xhttp_8443=true
- rollout_has_ws_8443=true

### USER-01

- user_report_all_config_ports_failed=true
- local_transport_probe_status=healthy
- local_transport_probe_ports=443,2083,39829

### BLAST-01

- public_443_owner=xray
- reality_443=true
- safe_in_place_move=false

### SECONDARY-01

- secondary_provisioning_status=provisioning_plan_ready_no_endpoint
- secondary_endpoint_count=0
- required_public_port=443

No NL or SPB writes were performed by this plan.

# First-Party VPN Production Completion Audit

generated_at: `2026-06-07T02:45:29Z`
ok: `false`
completion_decision: `FIRSTPARTY_VPN_PRODUCTION_NOT_PROVEN`
goal_completion_claim_allowed: `false`

## Checks

| Check | Passed |
|---|---|
| `audit_does_not_execute_commands` | `true` |
| `client_doctor_evidence_present` | `false` |
| `client_doctor_ok` | `false` |
| `client_doctor_requires_installed_health` | `false` |
| `client_health_evidence_present` | `false` |
| `client_health_ok` | `false` |
| `completion_evidence_present` | `false` |
| `endpoint_matches_runbook` | `false` |
| `no_nl_or_spb_writes_performed` | `true` |
| `post_apply_evidence_no_os_mutation` | `true` |
| `runbook_approval_guarded` | `true` |
| `runbook_no_legacy_commands` | `true` |
| `runbook_required_checks_ok` | `true` |
| `runbook_required_commands_present` | `true` |
| `runbook_summary_ok` | `true` |
| `server_health_evidence_present` | `false` |
| `server_health_ok` | `false` |
| `service_names_match` | `false` |

## Failed Checks

- client_doctor_evidence_present
- client_doctor_ok
- client_doctor_requires_installed_health
- client_health_evidence_present
- client_health_ok
- completion_evidence_present
- endpoint_matches_runbook
- server_health_evidence_present
- server_health_ok
- service_names_match

## Required Evidence Commands

```bash
sudo python3 /root/x0tta-firstparty-vpn/production-firstparty-handoff-20260607T010221Z/x0vpn_node.py client-doctor --config /etc/x0tta-firstparty-vpn-client/client.json --service-name x0tta-firstparty-vpn-client.service --require-installed-health
```

```bash
sudo python3 /root/x0tta-firstparty-vpn/production-firstparty-handoff-20260607T010221Z/x0vpn_node.py client-health --config /etc/x0tta-firstparty-vpn-client/client.json --service-name x0tta-firstparty-vpn-client.service
```

```bash
sudo python3 /root/x0tta-firstparty-vpn/production-firstparty-handoff-20260607T010221Z/x0vpn_node.py server-health --config /etc/x0tta-firstparty-vpn-server/server.json --service-name x0tta-firstparty-vpn.service --uplink-interface eth0
```

This audit did not execute any command and did not write to NL/SPB.

# Secondary Exit Post-Provision Validation

generated_at: `2026-05-28T03:39:35.711604+00:00`
status: `post_provision_validation_ready_waiting_endpoint`
ok: `true`

## Summary

```text
selected_label=upcloud-fi-hel
candidate_file=/mnt/projects/nl-diagnostics/secondary-exit-candidates.example.json
endpoint_count=0
candidate_score_status=missing_candidates
candidate_count=0
viable_count=0
top_candidate_label=none
secondary_probe_status=planning_template
candidate_configured=false
manual_probe_allowed=false
manual_switch_allowed=false
can_generate_probe_config=false
can_run_public_probe=false
test_client_allowed=false
probe_config_path=/mnt/projects/.tmp/secondary-exit-probe.json
nl_write_allowed=false
spb_fallback_allowed=false
automatic_failover_allowed=false
```

## Phases

| ID | Status | Phase | Next Step |
|---|---|---|---|
| `ENDPOINT-01` | `external_required` | Provision one selected server outside the repository | create the selected VPS externally and keep provider credentials out of repo |
| `METADATA-01` | `blocked` | Add only public endpoint metadata to candidate file | replace only host with public IPv4/DNS after the endpoint exists |
| `SCORE-01` | `blocked` | Score candidate metadata before generating probe config | run score_secondary_exit_candidates.py after public metadata is saved |
| `CONFIG-01` | `blocked` | Generate safe public probe config in project tmpdir | generate the probe config only from a viable public candidate |
| `PROBE-01` | `blocked` | Run public TCP endpoint probe | run probe_secondary_exit.py against the generated config |
| `TESTCLIENT-01` | `blocked` | Test-client profile remains gated | activate a test-client profile only during a real incident after endpoint probe passes |
| `SWITCH-01` | `blocked` | User switch remains manual and blocked | do not switch users until readiness explicitly allows manual switch |

## Safe Commands

```bash
python3 -m json.tool /mnt/projects/nl-diagnostics/secondary-exit-candidates.example.json >/dev/null
TMPDIR=/mnt/projects/.tmp python3 nl-diagnostics/score_secondary_exit_candidates.py --candidates /mnt/projects/nl-diagnostics/secondary-exit-candidates.example.json
TMPDIR=/mnt/projects/.tmp python3 nl-diagnostics/create_secondary_exit_config.py --label upcloud-fi-hel --provider UpCloud --region Helsinki --host <public-host-or-ip> --tcp-port 443 --out /mnt/projects/.tmp/secondary-exit-probe.json
TMPDIR=/mnt/projects/.tmp python3 nl-diagnostics/probe_secondary_exit.py --config /mnt/projects/.tmp/secondary-exit-probe.json --json-out /mnt/projects/.tmp/secondary-exit-probe-result.json
TMPDIR=/mnt/projects/.tmp python3 nl-diagnostics/refresh_vpn_planning_reports.py
TMPDIR=/mnt/projects/.tmp python3 nl-diagnostics/audit_vpn_plan_readiness.py
```

## Blocked Actions

- Do not store VPN profile URI, UUID, private key, bot token, subscription link, or provider credentials.
- Do not enable client probe until one test client is manually configured during a real incident.
- Do not switch users while manual_switch_allowed=false.
- Do not use SPB while SPB is disabled.
- Do not write to NL from this workflow.

No NL or SPB writes were performed by this post-provision validation report.

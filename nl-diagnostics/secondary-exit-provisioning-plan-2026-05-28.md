# Secondary Exit Provisioning Plan

generated_at: `2026-07-02T13:55:14.923102+00:00`
status: `provisioning_plan_ready_no_endpoint`
ok: `true`

## Summary

```text
shortlist_status=shortlist_ready_no_endpoint
shortlist_count=5
preferred_labels=upcloud-fi-hel,ovhcloud-pl-waw,hetzner-de-or-fi
endpoint_count=0
external_action_required=true
candidate_file=/mnt/projects/nl-diagnostics/secondary-exit-candidates.example.json
candidate_intake_status=awaiting_public_candidate_metadata
requirements_status=requirements_ready_no_candidate
safe_sources=true
nl_write_allowed=false
spb_fallback_allowed=false
automatic_failover_allowed=false
```

## Public Metadata

- label
- provider
- country
- region
- public host/IP
- public TCP ports
- non-secret notes

## Forbidden Material

- provider API token
- billing data
- SSH private key
- root password
- raw VPN URI
- UUID
- private key
- bot token
- subscription link
- NL endpoint
- SPB endpoint

## Steps

| ID | Status | Step | Next Step |
|---|---|---|---|
| `SELECT-01` | `ready` | Choose one non-NL/non-SPB shortlist option | choose one of the first three labels unless provider independence check fails |
| `ACCOUNT-01` | `external_required` | Use a separate provider project/account where practical | create or select the provider project in the provider console, not in repo |
| `SERVER-01` | `external_required` | Provision the smallest suitable server in the selected region | create the server manually, then keep only its public host/IP for local planning |
| `NETWORK-01` | `external_required` | Expose only a public TCP health target first | confirm public TCP 443 is reachable before any client profile test |
| `CANDIDATE-01` | `blocked` | Add public endpoint metadata to the local candidate file | after provisioning, fill only label/provider/region/country/host/tcp_ports/notes |
| `VALIDATE-01` | `blocked` | Run scorer and refresh before generating a probe config | run candidate scorer, then refresh local reports from the latest snapshot |

## Evidence

### SELECT-01

- shortlist_status=shortlist_ready_no_endpoint
- shortlist_count=5
- preferred_labels=upcloud-fi-hel,ovhcloud-pl-waw,hetzner-de-or-fi

### ACCOUNT-01

- no provider API token is needed in this repository
- billing data must stay outside this repository

### SERVER-01

- endpoint_count=0
- server provisioning is intentionally outside local automation

### NETWORK-01

- default_health_port=443
- profile secret generation remains outside repo

### CANDIDATE-01

- candidate_file=/mnt/projects/nl-diagnostics/secondary-exit-candidates.example.json
- candidate_intake_status=awaiting_public_candidate_metadata
- allowed_field_count=7

### VALIDATE-01

- requirements_status=requirements_ready_no_candidate
- missing_requirements=NET-01

## Local Validation Commands

```bash
TMPDIR=/mnt/projects/.tmp python3 nl-diagnostics/score_secondary_exit_candidates.py --candidates /mnt/projects/nl-diagnostics/secondary-exit-candidates.example.json
TMPDIR=/mnt/projects/.tmp python3 nl-diagnostics/refresh_vpn_planning_reports.py --snapshot /mnt/projects/nl-diagnostics/snapshots/20260528T011622Z
```

No NL or SPB writes were performed by this provisioning plan.

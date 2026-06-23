# Secondary Exit Public Metadata Template

generated_at: `2026-05-28T03:42:22.666240+00:00`
status: `public_metadata_template_ready_no_endpoint`
ok: `true`

## Summary

```text
selected_label=upcloud-fi-hel
selected_provider=UpCloud
selected_country=Finland
selected_region=Helsinki
endpoint_count=0
candidate_file=/mnt/projects/nl-diagnostics/secondary-exit-candidates.example.json
candidate_intake_status=awaiting_public_candidate_metadata
candidate_score_status=missing_candidates
template_candidate_count=1
forbidden_material_count=11
candidate_file_update_allowed=false
external_action_required=true
nl_write_allowed=false
spb_fallback_allowed=false
automatic_failover_allowed=false
```

## Candidate File Template

```json
{
  "schema_version": 1,
  "purpose": "Public metadata only for future secondary exit scoring. No secrets.",
  "candidates": [
    {
      "label": "upcloud-fi-hel",
      "provider": "UpCloud",
      "country": "Finland",
      "region": "Helsinki",
      "host": "FILL_PUBLIC_IPV4_OR_HOST_AFTER_PROVISIONING",
      "tcp_ports": [
        443
      ],
      "notes": "public metadata only; no VPN URI, UUID, private key, token, password, or subscription link"
    }
  ]
}
```

## Forbidden Material

- raw VPN URI
- UUID
- private key
- provider API token
- bot token
- subscription link
- SSH private key
- root password
- billing data
- NL endpoint
- SPB endpoint

## Safe Local Steps

- Provision the selected server externally first; do not store provider credentials in repo.
- Replace only host with the public IPv4 or DNS name after provisioning.
- Save public metadata locally in /mnt/projects/nl-diagnostics/secondary-exit-candidates.example.json only after the endpoint exists.
- Run the candidate scorer, refresh, and readiness audit before any probe config or client test.
- Keep VPN profile secrets outside repository and outside diagnostic reports.

## Validation Commands

```bash
TMPDIR=/mnt/projects/.tmp python3 nl-diagnostics/score_secondary_exit_candidates.py --candidates /mnt/projects/nl-diagnostics/secondary-exit-candidates.example.json
TMPDIR=/mnt/projects/.tmp python3 nl-diagnostics/refresh_vpn_planning_reports.py
TMPDIR=/mnt/projects/.tmp python3 nl-diagnostics/audit_vpn_plan_readiness.py
```

No candidate file update, NL write, or SPB fallback was performed by this template.

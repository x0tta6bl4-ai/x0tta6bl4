# Secondary Exit Candidate Intake

generated_at: `2026-05-31T13:45:55.580419+00:00`
status: `awaiting_public_candidate_metadata`
ok: `true`

## Summary

```text
candidate_file=/mnt/projects/nl-diagnostics/secondary-exit-candidates.example.json
candidate_score_status=missing_candidates
candidate_count=0
viable_count=0
top_candidate_label=none
requirements_status=requirements_ready_no_candidate
missing_requirements=NET-01
nl_write_allowed=false
spb_fallback_allowed=false
automatic_failover_allowed=false
```

## Allowed Fields

- `label`
- `provider`
- `region`
- `country`
- `host`
- `tcp_ports`
- `notes`

## Forbidden Material

- raw VPN URI
- UUID
- private key
- bot token
- subscription link
- NL endpoint
- SPB endpoint

## Candidate Template

```json
{
  "label": "secondary-1",
  "provider": "FILL_PUBLIC_PROVIDER_NAME",
  "region": "FILL_PUBLIC_REGION",
  "country": "FILL_PUBLIC_COUNTRY",
  "host": "FILL_PUBLIC_HOST_OR_IP",
  "tcp_ports": [
    443
  ],
  "notes": "public metadata only; no VPN URI, UUID, private key, token, or subscription link"
}
```

## Safe Local Steps

- Edit /mnt/projects/nl-diagnostics/secondary-exit-candidates.example.json locally with public metadata only.
- Run the candidate scorer before generating any probe config.
- Generate a probe config only after candidate_score_status=candidate_pool_ready.
- Keep profile secrets outside repo and outside reports.

## Validation Commands

```bash
TMPDIR=/mnt/projects/.tmp python3 nl-diagnostics/score_secondary_exit_candidates.py --candidates /mnt/projects/nl-diagnostics/secondary-exit-candidates.example.json
TMPDIR=/mnt/projects/.tmp python3 nl-diagnostics/refresh_vpn_planning_reports.py --snapshot /mnt/projects/nl-diagnostics/snapshots/20260528T011622Z
```

No NL or SPB writes were performed by this candidate intake report.

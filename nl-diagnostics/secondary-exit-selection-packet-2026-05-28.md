# Secondary Exit Selection Packet

generated_at: `2026-05-28T03:42:22.489207+00:00`
status: `selection_packet_ready_no_endpoint`
ok: `true`

## Summary

```text
recommended_label=upcloud-fi-hel
backup_label=ovhcloud-pl-waw
decision_option_count=3
endpoint_count=0
shortlist_status=shortlist_ready_no_endpoint
provisioning_plan_status=provisioning_plan_ready_no_endpoint
candidate_intake_status=awaiting_public_candidate_metadata
requirements_status=requirements_ready_no_candidate
secondary_flow_status=blocked_missing_candidate
manual_drill_status=drill_plan_ready_blocked_no_endpoint
manual_switch_allowed=false
bulk_user_switch_allowed=false
rollback_required=true
candidate_file=/mnt/projects/nl-diagnostics/secondary-exit-candidates.example.json
missing_requirements=NET-01
external_action_required=true
may_create_endpoint_now=false
nl_write_allowed=false
spb_fallback_allowed=false
automatic_failover_allowed=false
```

## Decision Order

| Rank | Role | Label | Provider | Country | Region | Ports | Source |
|---:|---|---|---|---|---|---|---|
| 1 | `primary_pick` | `upcloud-fi-hel` | UpCloud | Finland | Helsinki | `443` | https://upcloud.com/docs/getting-started/locations/ |
| 2 | `backup_pick` | `ovhcloud-pl-waw` | OVHcloud | Poland | Warsaw | `443` | https://www.ovhcloud.com/en/public-cloud/regions-availability/ |
| 3 | `fallback_review` | `hetzner-de-or-fi` | Hetzner | Germany or Finland | Nuremberg/Falkenstein/Helsinki | `443` | https://docs.hetzner.com/cloud/general/locations/ |

## Operator Checks

- verify provider and account are independent from NL
- verify exact region stock in the provider console
- verify public IPv4 and inbound TCP 443 before any profile work
- record only public metadata in secondary-exit-candidates.example.json
- run scorer, refresh, and readiness audit before creating any client test profile

## Stop Conditions

- selected region is NL, Amsterdam, SPB, or Russia
- selected provider/account is the current NL provider/account
- public IPv4 or public TCP 443 cannot be confirmed
- provider console requires storing API tokens, billing data, SSH private keys, or root passwords in repo
- candidate metadata contains raw VPN URI, UUID, private key, bot token, subscription link, NL endpoint, or SPB endpoint
- readiness audit does not remain ready_local_with_future_blocks after metadata is added

## Evidence By Option

### upcloud-fi-hel

Why:
- not NL and not SPB/Russia
- separate provider/account can be used
- near enough to European users for emergency fallback

Risk notes:
- verify current stock in provider console before provisioning
- do not choose UpCloud Amsterdam for this fallback
- do not store profile URI, UUID, private key, token, or subscription link in repo

### ovhcloud-pl-waw

Why:
- not NL and not SPB/Russia
- large European provider with a Poland Public Cloud region
- good candidate for provider and country diversity

Risk notes:
- verify instance flavor availability at order time
- keep the future endpoint public metadata only until probe config generation
- do not reuse the NL account or any existing VPN secret material

### hetzner-de-or-fi

Why:
- not NL and not SPB/Russia
- simple VPS footprint in Germany/Finland
- useful as a low-cost emergency profile if provider independence is confirmed

Risk notes:
- verify this is not the current NL provider before choosing it
- verify current stock in provider console before provisioning
- prefer a fresh project/account and avoid reusing NL automation credentials

## Next Local Commands After Public Metadata

```bash
TMPDIR=/mnt/projects/.tmp python3 nl-diagnostics/score_secondary_exit_candidates.py --candidates /mnt/projects/nl-diagnostics/secondary-exit-candidates.example.json
TMPDIR=/mnt/projects/.tmp python3 nl-diagnostics/refresh_vpn_planning_reports.py
TMPDIR=/mnt/projects/.tmp python3 nl-diagnostics/audit_vpn_plan_readiness.py
```

No NL or SPB writes were performed by this selection packet.

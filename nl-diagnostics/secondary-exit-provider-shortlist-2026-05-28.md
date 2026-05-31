# Secondary Exit Provider Shortlist

generated_at: `2026-05-31T13:45:54.844465+00:00`
source_check_date: `2026-05-28`
status: `shortlist_ready_no_endpoint`
ok: `true`

## Summary

```text
shortlist_count=5
source_count=9
endpoint_count=0
candidate_configured=false
candidate_file_action=after provisioning one shortlisted server, put only public host/IP metadata in nl-diagnostics/secondary-exit-candidates.example.json
invalid_source_refs=none
nl_write_allowed=false
spb_fallback_allowed=false
automatic_failover_allowed=false
```

## Selection Rules

- Do not use NL, Amsterdam, SPB, Russia, or the current NL provider/account as the secondary exit.
- Use a fresh provider project/account when practical.
- Expose only a public TCP health target, normally TCP 443, before any client profile test.
- Do not store raw VPN URI, UUID, private key, bot token, subscription link, or NL/SPB endpoint in repo.
- Keep failover manual; this shortlist does not permit a switch.

## Blocking Context

| Source | Planning Signal | URL |
|---|---|---|
| `cloudflare-russia-throttling-2025` | App/CDN failures can look like VPN failures even when the VPN server is healthy. | https://blog.cloudflare.com/russian-internet-users-are-unable-to-access-the-open-internet/ |
| `cloudflare-q1-2026-disruptions` | Government-directed shutdowns and non-server outages remain active operational risks. | https://blog.cloudflare.com/q1-2026-internet-disruption-summary/ |
| `access-now-keepiton-2025` | The global pattern favors multi-path diagnostics rather than one-server assumptions. | https://www.accessnow.org/tag/keepiton/ |
| `freedom-house-tunnel-vision-2025` | VPN and circumvention tools are blocked in multiple countries, so provider diversity matters. | https://freedomhouse.org/report/special-report/2025/tunnel-vision-anti-censorship-tools-end-end-encryption-and-fight-free |

## Provider Options

| Priority | Label | Provider | Country | Region | Slugs | Ports | Status |
|---:|---|---|---|---|---|---|---|
| 1 | `upcloud-fi-hel` | UpCloud | Finland | Helsinki | `fi-hel1,fi-hel2` | `443` | `shortlist_ready_no_endpoint` |

Source: https://upcloud.com/docs/getting-started/locations/

Why:
- not NL and not SPB/Russia
- separate provider/account can be used
- near enough to European users for emergency fallback

Risk notes:
- verify current stock in provider console before provisioning
- do not choose UpCloud Amsterdam for this fallback
- do not store profile URI, UUID, private key, token, or subscription link in repo

| 2 | `ovhcloud-pl-waw` | OVHcloud | Poland | Warsaw | `WAW` | `443` | `shortlist_ready_no_endpoint` |

Source: https://www.ovhcloud.com/en/public-cloud/regions-availability/

Why:
- not NL and not SPB/Russia
- large European provider with a Poland Public Cloud region
- good candidate for provider and country diversity

Risk notes:
- verify instance flavor availability at order time
- keep the future endpoint public metadata only until probe config generation
- do not reuse the NL account or any existing VPN secret material

| 3 | `hetzner-de-or-fi` | Hetzner | Germany or Finland | Nuremberg/Falkenstein/Helsinki | `nbg1,fsn1,hel1` | `443` | `shortlist_ready_no_endpoint` |

Source: https://docs.hetzner.com/cloud/general/locations/

Why:
- not NL and not SPB/Russia
- simple VPS footprint in Germany/Finland
- useful as a low-cost emergency profile if provider independence is confirmed

Risk notes:
- verify this is not the current NL provider before choosing it
- verify current stock in provider console before provisioning
- prefer a fresh project/account and avoid reusing NL automation credentials

| 4 | `digitalocean-de-fra-or-uk-lon` | DigitalOcean | Germany or United Kingdom | Frankfurt or London | `fra1,lon1` | `443` | `shortlist_ready_no_endpoint` |

Source: https://docs.digitalocean.com/platform/regional-availability/

Why:
- not NL and not SPB/Russia
- mainstream cloud with documented non-NL European regions
- useful if we want a provider very different from small EU VPS hosts

Risk notes:
- avoid Amsterdam even though it is available
- larger cloud IP ranges may have stronger VPN/proxy reputation signals
- verify outbound policy and public IPv4 availability before provisioning

| 5 | `scaleway-pl-waw-or-fr-par` | Scaleway | Poland or France | Warsaw or Paris | `WAW,PAR` | `443` | `shortlist_ready_no_endpoint` |

Source: https://www.scaleway.com/en/docs/account/reference-content/products-availability/

Why:
- not NL and not SPB/Russia
- European provider with Warsaw and Paris regions
- useful as a second EU-sovereign option after OVHcloud/UpCloud

Risk notes:
- avoid Amsterdam for this fallback
- check exact instance product availability in the chosen zone
- keep all VPN secrets outside repository and reports

## Next Steps

- Pick one option from priority 1-3 unless provider independence check fails.
- Provision the smallest suitable server with public TCP 443 reachability.
- Add only public metadata to secondary-exit-candidates.example.json.
- Run the scorer and refresh; do not generate profile secrets in the repository.

No NL or SPB writes were performed by this provider shortlist.

# First-Party VPN Rollout Packet

generated_at: `2026-06-06T22:35:05Z`
ok: `true`
deployment_epoch: `local-firstparty-staging-packet-20260606T215812Z`
approval_phrase_required: `APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT`
production_mutation_allowed: `false`

## Checks

| Check | Passed |
|---|---|
| `approval_required` | `true` |
| `canary_ok` | `true` |
| `client_apply_dry_run_ok` | `true` |
| `client_config_hash_matches_staging` | `true` |
| `client_kits_exported_without_server_secrets` | `true` |
| `client_kits_verified` | `true` |
| `client_service_plan_ok` | `true` |
| `client_unit_has_rollback_exec_stop` | `true` |
| `client_unit_starts_firstparty_client_tun` | `true` |
| `kit_material_not_persisted_in_repo` | `true` |
| `legacy_protocol_markers_absent` | `true` |
| `no_nl_or_spb_writes_performed` | `true` |
| `no_raw_secret_material_in_evidence` | `true` |
| `os_mutation_not_performed` | `true` |
| `production_mutation_blocked` | `true` |
| `production_readiness_ok` | `true` |
| `server_apply_dry_run_ok` | `true` |
| `server_config_hash_matches_staging` | `true` |
| `server_service_plan_ok` | `true` |
| `server_unit_starts_firstparty_server_tun` | `true` |
| `staging_ok` | `true` |

## Failed Checks

- none

## Evidence

- staging_summary_path: `/mnt/projects/nl-diagnostics/firstparty-staging-packet-20260606T215812Z/summary.json`
- production_readiness_summary_path: `/mnt/projects/nl-diagnostics/firstparty-production-readiness-20260606T214343Z/summary.json`
- canary_summary_path: `/mnt/projects/nl-diagnostics/firstparty-live-canary-20260606T212215Z/summary.json`
- server_service_name: `x0tta-firstparty-vpn.service`
- client_service_name: `x0tta-firstparty-vpn-client.service`
- client_kit_count: `2`
- verified_kit_count: `2`
- legacy_protocol_findings: `none`

No NL or SPB writes were performed by this rollout packet.

# First-Party VPN Pre-Apply Readiness

generated_at: `2026-06-06T22:45:33Z`
ok: `true`
deployment_epoch: `local-firstparty-staging-packet-20260606T215812Z`
approval_phrase_required: `APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT`
production_mutation_allowed: `false`

## Checks

| Check | Passed |
|---|---|
| `approval_not_present` | `true` |
| `approval_phrase_expected` | `true` |
| `firstparty_config_targets_scoped` | `true` |
| `firstparty_server_client_targets_distinct` | `true` |
| `firstparty_service_names_scoped` | `true` |
| `firstparty_service_names_unique` | `true` |
| `firstparty_unit_paths_scoped` | `true` |
| `legacy_service_markers_absent` | `true` |
| `manifest_nl_write_allowed_false` | `true` |
| `manifest_not_deployable_to_nl` | `true` |
| `no_nl_or_spb_writes_performed` | `true` |
| `os_mutation_not_performed` | `true` |
| `preapply_packet_does_not_authorize_mutation` | `true` |
| `rollout_packet_mutation_blocked` | `true` |
| `rollout_packet_no_nl_spb_writes` | `true` |
| `rollout_packet_ok` | `true` |
| `source_post_apply_validation_ready` | `true` |

## Failed Checks

- none

## Post-Apply Validation Source

- applied_state_checks_tun_routes_dns_nat: `true`
- build_linux_post_apply_validator: `true`
- collect_linux_applied_state_snapshot: `true`
- evaluate_linux_applied_state: `true`
- executor_requires_post_apply_validation: `true`

## Evidence

- rollout_summary_path: `/mnt/projects/nl-diagnostics/firstparty-rollout-packet-20260606T223505Z/summary.json`
- manifest_path: `/mnt/projects/services/nl-server/manifest.json`
- server_service_name: `x0tta-firstparty-vpn.service`
- client_service_name: `x0tta-firstparty-vpn-client.service`
- legacy_service_findings: `none`

No NL or SPB writes were performed by this pre-apply readiness packet.

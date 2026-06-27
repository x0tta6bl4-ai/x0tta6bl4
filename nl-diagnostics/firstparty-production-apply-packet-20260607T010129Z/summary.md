# First-Party VPN Production Apply Packet

generated_at: `2026-06-07T01:00:41Z`
ok: `true`
endpoint: `tcp://89.125.1.107:40467`
approval_phrase_required: `APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT`
production_mutation_allowed: `false`
secure_material_handoff_required: `true`

## Checks

| Check | Passed |
|---|---|
| `approval_not_present` | `true` |
| `approval_required` | `true` |
| `client_apply_dry_run_ok` | `true` |
| `client_apply_hash_matches_generated` | `true` |
| `client_kits_exported` | `true` |
| `client_kits_signed` | `true` |
| `client_kits_verified` | `true` |
| `client_kits_without_server_secrets` | `true` |
| `client_service_plan_ok` | `true` |
| `client_unit_has_rollback_exec_stop` | `true` |
| `client_unit_starts_firstparty_client_tun` | `true` |
| `endpoint_bind_not_loopback` | `true` |
| `endpoint_host_public` | `true` |
| `endpoint_no_mutation` | `true` |
| `endpoint_port_free_on_nl_snapshot` | `true` |
| `endpoint_summary_ok` | `true` |
| `generate_ok` | `true` |
| `generated_client_host_matches_endpoint` | `true` |
| `generated_port_matches_endpoint` | `true` |
| `generated_server_bind_matches_endpoint` | `true` |
| `generated_transport_matches_endpoint` | `true` |
| `kit_material_not_persisted_in_repo` | `true` |
| `no_nl_or_spb_writes_performed` | `true` |
| `os_mutation_not_performed` | `true` |
| `post_apply_validation_required` | `true` |
| `production_mutation_blocked` | `true` |
| `raw_secret_material_not_stored_in_evidence` | `true` |
| `secure_material_handoff_required` | `true` |
| `server_apply_dry_run_ok` | `true` |
| `server_apply_hash_matches_generated` | `true` |
| `server_service_plan_ok` | `true` |
| `server_unit_starts_firstparty_server_tun` | `true` |
| `service_units_firstparty_only` | `true` |
| `temp_config_dir_removed` | `true` |

## Failed Checks

- none

## Evidence

- endpoint_summary_path: `nl-diagnostics/firstparty-production-endpoint-20260607T005925Z/summary.json`
- endpoint_summary_sha256: `da8e588e114abbf7a5b09ccd10f7b4bb312c6cd2c9b099a9c2bed4d62079bfdc`
- server_service_name: `x0tta-firstparty-vpn.service`
- client_service_name: `x0tta-firstparty-vpn-client.service`
- server_config_target: `/etc/x0tta-firstparty-vpn-server/server.json`
- client_config_target: `/etc/x0tta-firstparty-vpn-client/client.json`
- client_kit_count: `2`
- verified_kit_count: `2`
- legacy_protocol_findings: `none`

No NL or SPB writes were performed by this production apply packet.
Raw config and client kit material were generated only in a temporary directory and removed before evidence write.

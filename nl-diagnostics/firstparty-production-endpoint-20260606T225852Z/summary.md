# First-Party VPN Production Endpoint

generated_at: `2026-06-06T22:58:46Z`
ok: `true`
endpoint: `tcp://89.125.1.107:40467`
bind_host: `0.0.0.0`

## Checks

| Check | Passed |
|---|---|
| `candidate_port_free_on_nl_snapshot` | `true` |
| `candidate_port_in_range` | `true` |
| `candidate_port_not_legacy_known` | `true` |
| `client_service_plan_ok` | `true` |
| `endpoint_host_public` | `true` |
| `generate_ok` | `true` |
| `generated_client_host_matches` | `true` |
| `generated_port_matches` | `true` |
| `generated_server_bind_matches` | `true` |
| `generated_transport_matches` | `true` |
| `no_nl_or_spb_writes_performed` | `true` |
| `os_mutation_not_performed` | `true` |
| `raw_secret_material_not_stored_in_evidence` | `true` |
| `server_bind_not_loopback` | `true` |
| `server_service_plan_ok` | `true` |
| `service_units_firstparty_only` | `true` |
| `temp_config_dir_removed` | `true` |

## Failed Checks

- none

## Evidence

- server_service_name: `x0tta-firstparty-vpn.service`
- client_service_name: `x0tta-firstparty-vpn-client.service`
- occupied_port_count: `42`
- legacy_unit_findings: `none`
- listeners_sha256: `59c2ac09cd56196fafb8c5a236324f55529433a9cd681bc6788cf228b07f008a`

No NL or SPB writes were performed by this endpoint packet.

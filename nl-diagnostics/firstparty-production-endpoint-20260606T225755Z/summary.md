# First-Party VPN Production Endpoint

generated_at: `2026-06-06T22:57:46Z`
ok: `false`
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
| `os_mutation_performed` | `false` |
| `raw_secret_material_stored_in_evidence` | `false` |
| `server_bind_not_loopback` | `true` |
| `server_service_plan_ok` | `true` |
| `service_units_firstparty_only` | `true` |
| `temp_config_dir_removed` | `true` |

## Failed Checks

- os_mutation_performed
- raw_secret_material_stored_in_evidence

## Evidence

- server_service_name: `x0tta-firstparty-vpn.service`
- client_service_name: `x0tta-firstparty-vpn-client.service`
- occupied_port_count: `44`
- legacy_unit_findings: `none`
- listeners_sha256: `380904f5bd73048853dcc16f7186c704e040e6b8dca29e4bfa90157ea1dfac96`

No NL or SPB writes were performed by this endpoint packet.

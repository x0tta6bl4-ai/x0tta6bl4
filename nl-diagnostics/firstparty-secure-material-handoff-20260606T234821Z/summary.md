# First-Party VPN Secure Material Handoff

generated_at: `2026-06-06T23:47:45Z`
ok: `false`
endpoint: `tcp://89.125.1.107:40467`
handoff_dir: `/home/x0ttta6bl4/.local/share/x0tta-firstparty-vpn/handoffs/firstparty-production-handoff-20260606T234745Z`
handoff_archive: `/home/x0ttta6bl4/.local/share/x0tta-firstparty-vpn/handoffs/firstparty-production-handoff-20260606T234745Z.tar.gz`
production_mutation_allowed: `false`

## Checks

| Check | Passed |
|---|---|
| `apply_packet_approval_blocked` | `true` |
| `apply_packet_external_endpoint` | `true` |
| `apply_packet_ok` | `true` |
| `apply_packet_requires_secure_handoff` | `true` |
| `client_apply_dry_run_ok` | `true` |
| `client_candidate_hash_matches_apply_packet` | `false` |
| `client_kits_exported` | `true` |
| `client_kits_signed` | `true` |
| `client_kits_verified` | `true` |
| `client_kits_without_server_secrets` | `true` |
| `client_service_plan_ok` | `true` |
| `generate_ok` | `true` |
| `handoff_archive_outside_repo` | `true` |
| `handoff_archive_private` | `true` |
| `handoff_dir_outside_repo` | `true` |
| `handoff_dir_private` | `true` |
| `legacy_protocol_markers_absent` | `true` |
| `manifest_secret_free` | `true` |
| `no_nl_or_spb_writes_performed` | `true` |
| `os_mutation_not_performed` | `true` |
| `private_files_mode_ok` | `true` |
| `raw_secret_material_not_stored_in_evidence` | `true` |
| `repo_material_not_persisted` | `true` |
| `server_apply_dry_run_ok` | `true` |
| `server_candidate_hash_matches_apply_packet` | `false` |
| `server_service_plan_ok` | `true` |
| `source_tree_hash_matches_current` | `false` |
| `source_tree_included` | `true` |

## Failed Checks

- client_candidate_hash_matches_apply_packet
- server_candidate_hash_matches_apply_packet
- source_tree_hash_matches_current

## Evidence

- apply_packet_summary_path: `/mnt/projects/nl-diagnostics/firstparty-production-apply-packet-20260606T233341Z/summary.json`
- archive_sha256: `6bcfe7abf71604be71b0fd8d6bbece9f3175cea11306f155e9099fabaf44d3ee`
- manifest_sha256: `fb4ea81899770017530fdc125bbfff6b52fc90cbd5798f054536d2e6d9cac517`
- handoff_dir_mode: `0700`
- handoff_archive_mode: `0600`
- handoff_file_count: `149`
- source_tree_hash: `1b44281aff62ba4a0bd763fd98bd704b647d39faeb792f012e2372779d66c1e5`
- client_kit_count: `2`
- verified_kit_count: `2`
- legacy_protocol_findings: `none`

No NL or SPB writes were performed by this handoff builder.
Private configs and client kits are outside the git workspace; diagnostics contain only hashes and metadata.

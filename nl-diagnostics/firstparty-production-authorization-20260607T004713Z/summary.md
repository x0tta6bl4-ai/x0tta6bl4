# First-Party VPN Production Authorization

generated_at: `2026-06-07T00:47:13Z`
ok: `true`
endpoint: `tcp://89.125.1.107:40467`
approval_phrase_required: `APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT`
production_mutation_allowed: `false`

## Checks

| Check | Passed |
|---|---|
| `all_evidence_fresh` | `true` |
| `apply_packet_ok` | `true` |
| `approval_blocked_apply_packet` | `true` |
| `approval_blocked_handoff` | `true` |
| `approval_blocked_preapply` | `true` |
| `approval_blocked_rollout` | `true` |
| `endpoint_fields_match_apply_and_handoff` | `true` |
| `endpoint_summary_ok` | `true` |
| `handoff_archive_exists` | `true` |
| `handoff_archive_hash_matches_summary` | `true` |
| `handoff_archive_outside_repo` | `true` |
| `handoff_archive_private` | `true` |
| `handoff_dir_exists` | `true` |
| `handoff_dir_outside_repo` | `true` |
| `handoff_dir_private` | `true` |
| `handoff_manifest_exists` | `true` |
| `handoff_manifest_hash_matches_summary` | `true` |
| `handoff_manifest_outside_repo` | `true` |
| `handoff_manifest_private` | `true` |
| `handoff_summary_secret_free` | `true` |
| `manual_approval_still_required` | `true` |
| `mutation_blocked_all_packets` | `true` |
| `no_nl_or_spb_writes_performed` | `true` |
| `os_mutation_not_performed` | `true` |
| `post_apply_validation_required` | `true` |
| `preapply_readiness_ok` | `true` |
| `rollout_packet_ok` | `true` |
| `secure_handoff_ok` | `true` |
| `secure_material_handoff_required` | `true` |

## Failed Checks

- none

## Evidence

- apply_packet_summary_path: `/mnt/projects/nl-diagnostics/firstparty-production-apply-packet-20260606T233341Z/summary.json`
- endpoint_summary_path: `/mnt/projects/nl-diagnostics/firstparty-production-endpoint-20260606T225852Z/summary.json`
- handoff_archive: `/home/x0ttta6bl4/.local/share/x0tta-firstparty-vpn/handoffs/firstparty-production-handoff-20260607T002710Z.tar.gz`
- handoff_dir: `/home/x0ttta6bl4/.local/share/x0tta-firstparty-vpn/handoffs/firstparty-production-handoff-20260607T002710Z`
- handoff_manifest: `/home/x0ttta6bl4/.local/share/x0tta-firstparty-vpn/handoffs/firstparty-production-handoff-20260607T002710Z/MANIFEST.secret-free.json`
- handoff_summary_path: `/mnt/projects/nl-diagnostics/firstparty-secure-material-handoff-20260607T002810Z/summary.json`
- preapply_summary_path: `/mnt/projects/nl-diagnostics/firstparty-preapply-readiness-20260606T224533Z/summary.json`
- rollout_summary_path: `/mnt/projects/nl-diagnostics/firstparty-rollout-packet-20260606T223505Z/summary.json`

This packet is read-only and does not authorize copying or applying the handoff.
A real production apply still requires the explicit approval phrase and post-apply validation.

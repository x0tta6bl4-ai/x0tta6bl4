# First-Party VPN Production Operator Scripts

generated_at: `2026-06-07T04:29:06Z`
ok: `true`
approval_phrase_required: `APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT`
runbook_summary_sha256: `ab47f541ddfbaa0b094057dc3736be2e42e591a9be337f1e52f4bb7a6245bf4a`

## Scripts

- apply: `/mnt/projects/nl-diagnostics/firstparty-production-operator-script-20260607T042907Z/apply-firstparty-production.sh`
- rollback: `/mnt/projects/nl-diagnostics/firstparty-production-operator-script-20260607T042907Z/rollback-firstparty-production.sh`

## Checks

| Check | Passed |
|---|---|
| `apply_script_excludes_rollback` | `true` |
| `apply_script_syntax_ok` | `true` |
| `commands_syntax_ok` | `true` |
| `mutating_commands_guarded` | `true` |
| `no_legacy_commands` | `true` |
| `no_nl_or_spb_writes_performed` | `true` |
| `operator_builder_does_not_execute_commands` | `true` |
| `required_apply_commands_present` | `true` |
| `required_rollback_commands_present` | `true` |
| `rollback_script_contains_only_rollback` | `true` |
| `rollback_script_syntax_ok` | `true` |
| `runbook_approval_guarded` | `true` |
| `runbook_hash_present` | `true` |
| `runbook_no_mutation` | `true` |
| `runbook_summary_ok` | `true` |
| `script_file_hashes_match_preview` | `true` |
| `script_files_written_executable_not_group_world_writable` | `true` |
| `scripts_default_dry_run` | `true` |
| `scripts_hash_bound_to_runbook` | `true` |
| `scripts_log_self_hash_meta` | `true` |
| `scripts_require_approval_to_execute` | `true` |

## Failed Checks

- none

The generated scripts default to dry-run. They require EXECUTE=1, DRY_RUN=0, and the explicit approval phrase before any command is executed.
This builder did not execute any command and did not write to NL/SPB.

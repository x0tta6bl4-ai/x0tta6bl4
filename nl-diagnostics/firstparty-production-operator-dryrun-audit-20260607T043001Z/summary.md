# First-Party VPN Production Operator Dry-Run Audit

generated_at: `2026-06-07T04:30:01Z`
ok: `true`
approval_phrase_required: `APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT`

## Checks

| Check | Passed |
|---|---|
| `apply_dryrun_exit_zero` | `true` |
| `apply_transcript_complete` | `true` |
| `apply_transcript_excludes_rollback` | `true` |
| `apply_transcript_meta_approval_not_ok` | `true` |
| `apply_transcript_meta_dry_run_enabled` | `true` |
| `apply_transcript_meta_execute_disabled` | `true` |
| `apply_transcript_meta_present` | `true` |
| `apply_transcript_meta_role_apply` | `true` |
| `apply_transcript_meta_runbook_hash_matches` | `true` |
| `apply_transcript_meta_script_hash_matches` | `true` |
| `audit_only_runs_dryrun_scripts` | `true` |
| `dryrun_env_safe` | `true` |
| `dryrun_transcripts_have_no_finish_events` | `true` |
| `guard_blocks_execute_without_dryrun_pair` | `true` |
| `guard_blocks_wrong_approval` | `true` |
| `guard_checks_do_not_start_steps` | `true` |
| `no_legacy_command_findings` | `true` |
| `no_nl_or_spb_writes_performed` | `true` |
| `operator_summary_approval_guarded` | `true` |
| `operator_summary_no_mutation` | `true` |
| `operator_summary_ok` | `true` |
| `os_mutation_not_performed` | `true` |
| `rollback_dryrun_exit_zero` | `true` |
| `rollback_transcript_complete` | `true` |
| `rollback_transcript_contains_only_rollback` | `true` |
| `rollback_transcript_meta_approval_not_ok` | `true` |
| `rollback_transcript_meta_dry_run_enabled` | `true` |
| `rollback_transcript_meta_execute_disabled` | `true` |
| `rollback_transcript_meta_present` | `true` |
| `rollback_transcript_meta_role_rollback` | `true` |
| `rollback_transcript_meta_runbook_hash_matches` | `true` |
| `rollback_transcript_meta_script_hash_matches` | `true` |
| `script_hashes_match_summary` | `true` |
| `script_paths_present` | `true` |
| `scripts_syntax_ok` | `true` |

## Failed Checks

- none

## Transcripts

- apply: `/mnt/projects/nl-diagnostics/firstparty-production-operator-dryrun-audit-20260607T043001Z/apply-dryrun.jsonl`
- guard_requires_approval: `/mnt/projects/nl-diagnostics/firstparty-production-operator-dryrun-audit-20260607T043001Z/guard-requires-approval.jsonl`
- guard_requires_pair: `/mnt/projects/nl-diagnostics/firstparty-production-operator-dryrun-audit-20260607T043001Z/guard-requires-execute-and-dryrun.jsonl`
- rollback: `/mnt/projects/nl-diagnostics/firstparty-production-operator-dryrun-audit-20260607T043001Z/rollback-dryrun.jsonl`

This audit ran generated scripts only in dry-run or pre-step guard-failure mode.
No nested production command was executed and no NL/SPB write was performed.

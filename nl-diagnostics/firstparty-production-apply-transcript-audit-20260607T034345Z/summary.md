# First-Party VPN Production Apply Transcript Audit

generated_at: `2026-06-07T03:43:45Z`
ok: `false`
apply_execution_proven: `false`
approval_phrase_required: `APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT`

## Checks

| Check | Passed |
|---|---|
| `apply_script_hash_matches_summary` | `true` |
| `apply_script_path_present` | `true` |
| `apply_script_syntax_ok` | `true` |
| `apply_transcript_all_expected_finishes_rc0` | `false` |
| `apply_transcript_all_expected_starts_present` | `false` |
| `apply_transcript_excludes_rollback_steps` | `true` |
| `apply_transcript_has_only_expected_apply_steps` | `true` |
| `apply_transcript_no_dry_run_events` | `true` |
| `apply_transcript_no_failed_finishes` | `true` |
| `apply_transcript_nonempty` | `false` |
| `apply_transcript_present` | `false` |
| `audit_does_not_execute_commands` | `true` |
| `no_nl_or_spb_writes_performed` | `true` |
| `operator_summary_approval_guarded` | `true` |
| `operator_summary_no_mutation` | `true` |
| `operator_summary_ok` | `true` |
| `os_mutation_not_performed_by_audit` | `true` |
| `rollback_script_hash_matches_summary` | `true` |
| `rollback_script_path_present` | `true` |
| `rollback_script_syntax_ok` | `true` |

## Failed Checks

- apply_transcript_all_expected_finishes_rc0
- apply_transcript_all_expected_starts_present
- apply_transcript_nonempty
- apply_transcript_present

apply_transcript: `missing`

This audit did not execute the apply script and did not write to NL/SPB.

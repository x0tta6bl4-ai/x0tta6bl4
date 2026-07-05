# Local Root Cleanup Plan

generated_at: `2026-07-02T13:55:15.762023+00:00`
status: `no_cleanup_needed`
ok: `true`

## Summary

```text
root_status=ok
root_free_gib=10.39
existing_candidate_count=3
estimated_reclaim_gib=1.46
top_candidate_id=JOURNAL-01
top_candidate_size_gib=1.12
cleanup_execute_allowed=false
nl_write_allowed=false
spb_fallback_allowed=false
automatic_failover_allowed=false
```

## Review Order

- `JOURNAL-01`
- `APT-CACHE-01`
- `VARTMP-01`

## Candidates

| ID | Exists | Size GiB | Risk | Action | Command Preview |
|---|---:|---:|---|---|---|
| `TMP-ANTIGRAVITY-01` | false | 0.0 | `medium_manual_review` | `manual_review_before_delete` | `sudo rm -rf /tmp/antigravity_restore` |
| `TMP-ANTIGRAVITY-02` | false | 0.0 | `medium_manual_review` | `manual_review_before_delete` | `sudo rm -rf /tmp/antigravity_restore_correct` |
| `APT-CACHE-01` | true | 0.29 | `low_standard_cache` | `command_requires_approval` | `sudo apt-get clean` |
| `JOURNAL-01` | true | 1.12 | `medium_keep_recent_logs` | `command_requires_approval` | `sudo journalctl --vacuum-size=500M` |
| `VARTMP-01` | true | 0.05 | `high_manual_review` | `manual_review_before_delete` | `sudo find /var/tmp -mindepth 1 -maxdepth 1 -mtime +7 -print` |

## Execution Rules

- This report does not delete files.
- Run command previews only after separate local cleanup approval.
- Review /tmp/antigravity_restore* contents before any rm -rf command.
- Keep using TMPDIR=/mnt/projects/.tmp until root has free space again.

No cleanup, NL writes, or SPB fallback were performed by this plan.

# Local Root Cleanup Plan

generated_at: `2026-05-28T03:26:54.079762+00:00`
status: `manual_cleanup_plan_ready`
ok: `true`

## Summary

```text
root_status=critical_full
root_free_gib=0.0
existing_candidate_count=5
estimated_reclaim_gib=3.25
top_candidate_id=APT-CACHE-01
top_candidate_size_gib=0.85
cleanup_execute_allowed=false
nl_write_allowed=false
spb_fallback_allowed=false
automatic_failover_allowed=false
```

## Review Order

- `APT-CACHE-01`
- `JOURNAL-01`
- `TMP-ANTIGRAVITY-01`
- `TMP-ANTIGRAVITY-02`
- `VARTMP-01`

## Candidates

| ID | Exists | Size GiB | Risk | Action | Command Preview |
|---|---:|---:|---|---|---|
| `TMP-ANTIGRAVITY-01` | true | 0.67 | `medium_manual_review` | `manual_review_before_delete` | `sudo rm -rf /tmp/antigravity_restore` |
| `TMP-ANTIGRAVITY-02` | true | 0.6 | `medium_manual_review` | `manual_review_before_delete` | `sudo rm -rf /tmp/antigravity_restore_correct` |
| `APT-CACHE-01` | true | 0.85 | `low_standard_cache` | `command_requires_approval` | `sudo apt-get clean` |
| `JOURNAL-01` | true | 0.72 | `medium_keep_recent_logs` | `command_requires_approval` | `sudo journalctl --vacuum-size=500M` |
| `VARTMP-01` | true | 0.41 | `high_manual_review` | `manual_review_before_delete` | `sudo find /var/tmp -mindepth 1 -maxdepth 1 -mtime +7 -print` |

## Execution Rules

- This report does not delete files.
- Run command previews only after separate local cleanup approval.
- Review /tmp/antigravity_restore* contents before any rm -rf command.
- Keep using TMPDIR=/mnt/projects/.tmp until root has free space again.

No cleanup, NL writes, or SPB fallback were performed by this plan.

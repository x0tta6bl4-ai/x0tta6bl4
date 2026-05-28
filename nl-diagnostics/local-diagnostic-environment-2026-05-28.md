# Local Diagnostic Environment Audit

generated_at: `2026-05-28T01:17:09.195882+00:00`
status: `watch_root_full_tmpdir_available`
ok: `true`

## Summary

```text
root_status=critical_full
root_used_percent=94.9
root_free_gib=0.0
tmp_status=critical_full
projects_status=ok
projects_free_gib=61.36
diagnostic_tmpdir=/mnt/projects/.tmp
diagnostic_tmpdir_exists=true
diagnostic_tmpdir_writable=true
cleanup_required=true
recommended_tmpdir_prefix=TMPDIR=/mnt/projects/.tmp
nl_write_allowed=false
spb_fallback_allowed=false
automatic_failover_allowed=false
```

## Disk

| Path | Status | Used | Free GiB |
|---|---|---:|---:|
| `/` | `critical_full` | 94.9% | 0.0 |
| `/tmp` | `critical_full` | 94.9% | 0.0 |
| `/mnt/projects` | `ok` | 86.8% | 61.36 |

## Cleanup Candidates

- `/tmp/antigravity_restore` exists=true action=manual_review_before_delete
- `/tmp/antigravity_restore_correct` exists=true action=manual_review_before_delete

## Notes

- Use TMPDIR=/mnt/projects/.tmp for local Python tests and report refreshes while / is full.
- Do not delete /tmp/antigravity_restore* without separate local cleanup approval.
- This audit performs no NL writes and does not use SPB.

No NL or SPB writes were performed by this local environment audit.

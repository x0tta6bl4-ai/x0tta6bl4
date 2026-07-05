# Local Diagnostic Environment Audit

generated_at: `2026-07-02T13:55:15.266210+00:00`
status: `ok`
ok: `true`

## Summary

```text
root_status=ok
root_used_percent=85.1
root_free_gib=10.39
tmp_status=ok
projects_status=ok
projects_free_gib=320.56
diagnostic_tmpdir=/mnt/projects/.tmp
diagnostic_tmpdir_exists=true
diagnostic_tmpdir_writable=true
cleanup_required=false
recommended_tmpdir_prefix=TMPDIR=/mnt/projects/.tmp
nl_write_allowed=false
spb_fallback_allowed=false
automatic_failover_allowed=false
```

## Disk

| Path | Status | Used | Free GiB |
|---|---|---:|---:|
| `/` | `ok` | 85.1% | 10.39 |
| `/tmp` | `ok` | 85.1% | 10.39 |
| `/mnt/projects` | `ok` | 31.1% | 320.56 |

## Cleanup Candidates

- `/tmp/antigravity_restore` exists=false action=manual_review_before_delete
- `/tmp/antigravity_restore_correct` exists=false action=manual_review_before_delete

## Notes

- Use TMPDIR=/mnt/projects/.tmp for local Python tests and report refreshes while / is full.
- Do not delete /tmp/antigravity_restore* without separate local cleanup approval.
- This audit performs no NL writes and does not use SPB.

No NL or SPB writes were performed by this local environment audit.

# Local Root Cleanup Approval Packet

generated_at: `2026-07-02T13:55:15.819543+00:00`
status: `cleanup_approval_packet_no_cleanup_needed`
ok: `true`

## Summary

```text
root_status=ok
root_free_gib=10.39
diagnostic_tmpdir=/mnt/projects/.tmp
diagnostic_tmpdir_writable=true
cleanup_plan_status=no_cleanup_needed
existing_candidate_count=3
estimated_reclaim_gib=1.46
first_review_id=APT-CACHE-01
command_preview_count=3
approval_required=false
commands_executed=0
cleanup_execute_allowed=false
nl_write_allowed=false
spb_fallback_allowed=false
automatic_failover_allowed=false
```

## Precheck Commands

```bash
df -h / /tmp /mnt/projects
TMPDIR=/mnt/projects/.tmp python3 nl-diagnostics/audit_local_diagnostic_environment.py
TMPDIR=/mnt/projects/.tmp python3 nl-diagnostics/plan_local_root_cleanup.py
```

## Command Previews

| ID | Size GiB | Risk | Approval Level | May Execute Now | Command Preview |
|---|---:|---|---|---:|---|
| `APT-CACHE-01` | `0.29` | `low_standard_cache` | `single_command_approval` | `false` | `sudo apt-get clean` |
| `JOURNAL-01` | `1.12` | `medium_keep_recent_logs` | `confirm_log_retention_approval` | `false` | `sudo journalctl --vacuum-size=500M` |
| `VARTMP-01` | `0.05` | `high_manual_review` | `manual_path_review_required` | `false` | `sudo find /var/tmp -mindepth 1 -maxdepth 1 -mtime +7 -print` |

## Postcheck Commands

```bash
df -h / /tmp /mnt/projects
TMPDIR=/mnt/projects/.tmp python3 nl-diagnostics/audit_local_diagnostic_environment.py
TMPDIR=/mnt/projects/.tmp python3 nl-diagnostics/refresh_vpn_planning_reports.py --snapshot /mnt/projects/nl-diagnostics/snapshots/20260528T021824Z
```

## Execution Rules

- Do not execute any command preview without separate local cleanup approval.
- Prefer APT-CACHE-01 before manual rm -rf candidates.
- Review /tmp/antigravity_restore* contents before approving deletion.
- Keep TMPDIR=/mnt/projects/.tmp until root free space is no longer critical.
- This packet does not permit NL writes or SPB fallback.

No cleanup, NL writes, or SPB fallback were performed by this approval packet.

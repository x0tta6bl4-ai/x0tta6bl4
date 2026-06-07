# Final Report: Finish first-party VPN goal

## Outcome

Not complete yet. The restored legacy VPN path is usable locally, and the
first-party VPN code/preflight checks pass, but the production-candidate goal
gate still returns `VPN_PRODUCTION_CANDIDATE_GOAL_NOT_COMPLETE`.

## Accepted Results

- Local first-party unit suite passed: `306 passed`.
- Local static/cross-plane readiness passed: `REAL_READINESS_READY`, `70/70`.
- Fresh read-only snapshot: `/mnt/projects/nl-diagnostics/snapshots/20260606T125103Z`.
- Local VPN status in that snapshot is `PASS`: exit IP is `89.125.1.107`, no packet loss, watchdog healthy.
- NL x-ui/Reality core evidence is present: services active, listeners `443`, `2083`, and `39829` present.
- Goal preflight is ok: `389` checks, deploy status `local_ready_but_deploy_blocked`.
- Monitor-restore readiness packet is ready for approval:
  `MONITOR_RESTORE_READY_FOR_APPROVAL`, `apply_allowed_now=false`.
- Remote client reply intake is ready for safe external replies:
  `REMOTE_CLIENT_REPLIES_READY_FOR_SAFE_INTAKE`, with no reply recording
  performed.

## Rejected Results

- Do not mark the Codex goal complete. Current gate is still `3/6`.
- Do not claim production/customer readiness from local tests alone.
- Do not restart x-ui, change UFW, send profiles, or enable server timers without the separate approval phrase.

## Conflicts Resolved

- Older decision evidence showed `local_fix` and `core_evidence_present=false`.
  A fresh read-only snapshot fixed the stale core-evidence marker. The decision
  is now `restore_transport_canary_monitor`: core TCP/x-ui evidence is live, but
  runtime transport canary evidence is not configured.
- The current `transport_status=degraded` is traced to
  `/var/lib/ghost-access/vpn-service-access-agent/latest.json`, generated at
  `2026-06-06T06:39:50Z`, where Reality canary is `not-configured`.
- The canary monitor exists as `ghost-access-vpn-monitor.service`, but
  `ghost-access-vpn-monitor.timer` is `disabled` and `inactive`. Journal shows
  the timer stopped at `2026-06-06T01:52:14Z`. Earlier at `01:51 UTC`, the
  canary passed on both `443` and `2083`.

## Verification Evidence

- `python3 nl-diagnostics/build_vpn_goal_status.py --json`:
  `VPN_PRODUCTION_CANDIDATE_GOAL_NOT_COMPLETE`, `requirements_passed=3/6`.
- `python3 scripts/ops/check_real_readiness.py --skip-command-checks --skip-git-check --json`:
  `REAL_READINESS_READY`, `70/70`.
- `TMPDIR=/mnt/projects/.tmp python3 -m pytest tests/unit/network/test_firstparty_vpn_protocol_unit.py -q --no-cov`:
  `306 passed`.
- `python3 -m pytest nl-diagnostics/test_classify_vpn_snapshot.py nl-diagnostics/test_build_vpn_decision_report.py nl-diagnostics/test_build_vpn_goal_status.py tests/unit/scripts/test_restore_nl_vpn_monitor_canary_timer_unit.py -q --no-cov`:
  `38 passed`.
- `python3 -m pytest nl-diagnostics/test_build_vpn_monitor_restore_readiness.py nl-diagnostics/test_classify_vpn_snapshot.py nl-diagnostics/test_build_vpn_decision_report.py nl-diagnostics/test_build_vpn_goal_status.py tests/unit/scripts/test_restore_nl_vpn_monitor_canary_timer_unit.py -q --no-cov`:
  `42 passed`.
- `python3 -m py_compile nl-diagnostics/build_vpn_monitor_restore_readiness.py nl-diagnostics/classify_vpn_snapshot.py nl-diagnostics/build_vpn_decision_report.py nl-diagnostics/build_vpn_goal_status.py`:
  passed.
- `python3 nl-diagnostics/build_vpn_monitor_restore_readiness.py`:
  wrote `/mnt/projects/nl-diagnostics/vpn-monitor-restore-readiness-2026-06-06.json`
  and `.md`; decision is `MONITOR_RESTORE_READY_FOR_APPROVAL`, with
  `apply_allowed_now=false`.
- `python3 -m pytest nl-diagnostics/test_build_remote_client_reply_readiness.py -q --no-cov`:
  `5 passed`.
- `python3 -m pytest nl-diagnostics/test_build_remote_client_reply_readiness.py nl-diagnostics/test_build_vpn_monitor_restore_readiness.py nl-diagnostics/test_classify_vpn_snapshot.py nl-diagnostics/test_build_vpn_decision_report.py nl-diagnostics/test_build_vpn_goal_status.py tests/unit/scripts/test_restore_nl_vpn_monitor_canary_timer_unit.py -q --no-cov`:
  `47 passed`.
- `python3 nl-diagnostics/build_remote_client_reply_readiness.py`:
  wrote `/mnt/projects/nl-diagnostics/nl-anti-block-remote-client-reply-readiness-2026-06-06.json`
  and `.md`; decision is `REMOTE_CLIENT_REPLIES_READY_FOR_SAFE_INTAKE`.
- Dry-run reply validation through `record_remote_client_evidence_reply.py`:
  both `remote-client-evidence-1` and `remote-client-evidence-2` returned
  `REMOTE_CLIENT_EVIDENCE_REPLY_VALIDATED`, `recorded=false`, with
  `output_privacy_ok=true`.
- `bash scripts/ops/restore_nl_vpn_monitor_canary_timer.sh --dry-run --precheck --host nl`:
  no NL writes; confirms `ghost-access-vpn-monitor.timer` is disabled/inactive
  and latest canary evidence is `not-configured`.
- `TMPDIR=/mnt/projects/.tmp python3 nl-diagnostics/refresh_vpn_planning_reports.py --snapshot /mnt/projects/nl-diagnostics/snapshots/20260606T125103Z`:
  local refresh ran, but final exit code is `1` because readiness audit still
  has missing evidence, not because the local VPN check failed.

## Remaining Risks

- `CORE-REALITY-01`: blocked by stale/degraded canary monitor evidence until the
  NL monitor timer/service is explicitly restored and a new snapshot is taken.
- `ANTIBLOCK-CLIENTS-01`: blocked on external real-client replies for
  Happ/Hiddify mobile data and restricted/work Wi-Fi. Local intake is ready,
  but real replies have not been recorded.
- `NL-GATE-01`: intentionally blocked while `nl_write_allowed=false`.

## Reusable Follow-up

Approval-gated server step, do not run without the exact phrase
`APPLY_RESTORE_NL_VPN_MONITOR_CANARY_TIMER`:

```text
RESTORE_NL_VPN_MONITOR_CONFIRM=APPLY_RESTORE_NL_VPN_MONITOR_CANARY_TIMER \
  bash scripts/ops/restore_nl_vpn_monitor_canary_timer.sh --apply --host nl
```

Then collect a new read-only snapshot and rerun:

```text
VPN_ENABLE_BLOCKING_PROBES=1 TMPDIR=/mnt/projects/.tmp bash nl-diagnostics/collect_vpn_readonly_snapshot.sh
TMPDIR=/mnt/projects/.tmp python3 nl-diagnostics/refresh_vpn_planning_reports.py --snapshot <new_snapshot>
python3 services/nl-server/ghost-access/refresh_client_evidence_artifacts.py --write --json
python3 nl-diagnostics/build_vpn_goal_status.py --json
```

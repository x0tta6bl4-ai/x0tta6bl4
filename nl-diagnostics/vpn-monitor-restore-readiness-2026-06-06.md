# VPN Monitor Restore Readiness

generated_at: `2026-06-07T05:02:18Z`
decision: `MONITOR_RESTORE_READY_FOR_APPROVAL`
ready_for_approval: `true`
apply_allowed_now: `false`

## Commands

```text
precheck: bash scripts/ops/restore_nl_vpn_monitor_canary_timer.sh --dry-run --precheck --host nl
apply: RESTORE_NL_VPN_MONITOR_CONFIRM=APPLY_RESTORE_NL_VPN_MONITOR_CANARY_TIMER bash scripts/ops/restore_nl_vpn_monitor_canary_timer.sh --apply --host nl
rollback: ssh nl 'sudo systemctl disable --now ghost-access-vpn-monitor.timer'
```

## Gates

| ID | Status | OK | Next Step |
|---|---:|---:|---|
| `DECISION-01` | `pass` | `true` | refresh current-vpn-decision from the latest read-only snapshot |
| `GOAL-01` | `pass` | `true` | rebuild vpn-production-candidate-goal after updating current decision |
| `SCRIPT-01` | `pass` | `true` | fix restore script gating before any operator approval is accepted |
| `APPROVAL-01` | `blocked_future_approval` | `true` | run the apply command only after the exact phrase is present |

No NL or SPB writes were performed by this readiness report.

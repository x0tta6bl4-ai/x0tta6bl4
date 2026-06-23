# Packet 05: Integration

## Objective

Integrate the fresh read-only NL evidence, local classifier fixes, and gated
canary-monitor restore path into the first-party VPN goal handoff.

## Context

- Goal gate remains `VPN_PRODUCTION_CANDIDATE_GOAL_NOT_COMPLETE`.
- Current pass count is `3/6`.
- Local VPN status is `PASS`, and NL listeners `443/2083/39829` are present.
- `ghost-access-vpn-monitor.timer` is disabled/inactive, so runtime transport
  canary evidence is stale and `not-configured`.

## Do

- Keep NL writes blocked unless the exact approval phrase is present.
- Keep external client evidence as a separate blocker.
- Preserve the full original goal; do not redefine completion around local tests.

## Verification

- `python3 nl-diagnostics/build_vpn_goal_status.py --json`
- `python3 -m pytest nl-diagnostics/test_build_vpn_monitor_restore_readiness.py nl-diagnostics/test_classify_vpn_snapshot.py nl-diagnostics/test_build_vpn_decision_report.py nl-diagnostics/test_build_vpn_goal_status.py tests/unit/scripts/test_restore_nl_vpn_monitor_canary_timer_unit.py -q --no-cov`
- `python3 nl-diagnostics/build_vpn_monitor_restore_readiness.py`
- `bash scripts/ops/restore_nl_vpn_monitor_canary_timer.sh --dry-run --precheck --host nl`

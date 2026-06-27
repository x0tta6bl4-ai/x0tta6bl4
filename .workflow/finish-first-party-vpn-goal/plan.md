# Finish first-party VPN goal

## Goal

Finish the active first-party VPN goal:

> собрать с нуля новый и полноценный впн на наших разработках и протоколах. не использовать ничего чужого. только всё созданное нами

## Success Criteria

- Goal-specific report returns `VPN_PRODUCTION_CANDIDATE_GOAL_COMPLETE`.
- First-party VPN core tests pass.
- Real NL first-party services are active and externally reachable on the intended ports.
- Required external client evidence is present for Android Happ/Hiddify, mobile network, and restricted/work Wi-Fi.
- NL write/apply actions are gated by explicit operator approval and have rollback evidence.
- Public claims stay bounded: local readiness is not treated as production/customer proof.

## Current Context

- Legacy VPN/Xray/x-ui was restored after an outage.
- NL first-party services are active on `22080`, `22081`, `22082`, and `22083`.
- Current goal-specific gate returns `VPN_PRODUCTION_CANDIDATE_GOAL_NOT_COMPLETE`, `requirements_passed=3/6`.
- Local first-party core test passed once in this session: `306 passed`.
- Fresh read-only snapshot `/mnt/projects/nl-diagnostics/snapshots/20260606T125103Z` shows local VPN PASS and NL listeners `443/2083/39829` present.
- `ghost-access-vpn-monitor.timer` is currently disabled/inactive, so runtime-state reads stale canary evidence where Reality canary is `not-configured`.
- The repo has a very dirty worktree with many unrelated changes from other agents.

## Constraints

- Do not perform NL/server writes without a separate explicit apply phrase.
- Do not ask the user to paste secrets, profile links, tokens, private keys, or client reports into chat.
- Treat existing uncommitted changes as other agents' work unless changed in this workflow.
- Keep edits scoped to goal evidence, local gate code, and first-party VPN artifacts.

## Risks

- Breaking currently restored user connectivity.
- Mixing local static readiness with real production proof.
- Overwriting or reverting another agent's dirty worktree changes.
- Stale evidence making the goal look blocked or ready incorrectly.

## Approval Required

- Any NL mutation: service restart, UFW change, x-ui DB edit, systemd edit, config write.
- Any user-facing message send or subscription/profile distribution.
- Any Git destructive operation or broad cleanup.
- Restoring the canary monitor requires the explicit phrase `APPLY_RESTORE_NL_VPN_MONITOR_CANARY_TIMER`.

## Work Packets

- `packet-01-evidence-refresh`: read-only/local refresh of VPN goal evidence.
- `packet-02-goal-gate-fix`: fix local gate/report bugs that incorrectly block on stale or malformed evidence.
- `packet-03-firstparty-core-verify`: run first-party VPN focused tests and summarize failures.
- `packet-04-nl-runtime-readonly`: read-only NL service/listener/config sanity snapshot.
- `packet-05-integration`: produce final stage report and remaining gated apply steps.

## Integration Policy

- Prefer generated evidence artifacts over manual claims.
- If artifacts disagree, inspect the generator and newest runtime snapshot before choosing.
- Do not mark the Codex goal complete until all required evidence exists.

## Verification

- `python3 nl-diagnostics/build_vpn_goal_status.py --json`
- `python3 scripts/ops/check_real_readiness.py --skip-command-checks --skip-git-check --json`
- `TMPDIR=/mnt/projects/.tmp python3 -m pytest tests/unit/network/test_firstparty_vpn_protocol_unit.py -q --no-cov`
- Read-only SSH checks for `x0tta-firstparty-vpn*` services/listeners if needed.

## Reusable Artifacts

- Keep this workflow as the handoff record for future agents.
- Do not store secrets or raw client profile data here.

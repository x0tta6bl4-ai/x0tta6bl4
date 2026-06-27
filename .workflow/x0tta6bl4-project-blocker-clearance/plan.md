# x0tta6bl4 project blocker clearance

## Goal
Eliminate the current x0tta6bl4 project blockers surfaced by the authoritative
real-readiness gate.

## Success Criteria
- `python3 scripts/ops/check_real_readiness.py --write-json --write-md --json`
  returns `REAL_READINESS_READY`.
- Ghost Pulse proof gate either passes or remains fail-closed for the right
  reason without stale/stable-field mismatch.
- Release-state blocker is resolved through reviewed commit/clean worktree, not
  by reverting unrelated user or agent work.
- No NL production writes, service restarts, profile sends, or secret handling
  occur without explicit approval.

## Current Context
- On 2026-06-07 the full real-readiness gate returned
  `REAL_READINESS_BLOCKED`.
- Current blocker:
  - `git_worktree_clean`: 923 uncommitted paths in the full gate run.
- Cleared local blocker:
  - `ghost_pulse_current_runtime_boundary` now passes as a fail-closed proof
    boundary: current runtime attach remains false without a configured runtime
    interface, and historical kernel evidence cannot promote that claim.
- Dirty-worktree owner review is now actionable:
  - `.tmp/dirty-worktree-review-current.json` reports
    `DIRTY_WORKTREE_OWNER_REVIEW_READY`.
  - `unowned_path_count=0`.
  - `--require-owned` exits `0`.
  - Package handoff is still required before release cleanup.
- Current cross-plane evidence map has no open blocking gaps; one non-blocking
  tracked risk remains.

## Constraints
- Communicate in Russian.
- Treat existing dirty worktree content as user/other-agent work unless proven
  otherwise.
- Do not revert, delete, or mass-stage files blindly.
- Keep production/customer/DPI/settlement claims bounded by evidence gates.

## Risks
- Dirty worktree includes many unrelated tracks; cleaning it incorrectly could
  lose work.
- Ghost Pulse evidence can be accidentally overpromoted from historical/local
  evidence into current runtime or production claims.
- NL VPN infrastructure is production; no destructive/service-write commands.

## Approval Required
- Any NL/server write, service restart, x-ui/xray edit, UFW change, profile
  distribution, or user-facing message send.
- Any destructive Git operation.
- Any broad commit of unrelated work should be backed by dirty-worktree owner
  review and package-specific checks.

## Work Packets
- `packet-01-ghost-pulse-proof`: completed locally; verifier/gate passes with
  bounded incomplete proof.
- `packet-02-dirty-worktree-review`: completed for ownership readiness; release
  cleanup still requires package-specific handoff, checks, and reviewed commits.
- `packet-03-verification`: completed for current pass; full gate has 95/96
  passing and remains blocked only by dirty worktree.
- `packet-04-dao-governance-policy-review`: completed; package ownership is
  clean, DAO tests pass, and token reward gas settlement now fails closed when
  gas guard is unavailable or rejects cost.

## Integration Policy
- Prefer generated JSON/Markdown evidence artifacts over manual claims.
- If a script and document disagree, inspect the generator first.
- A blocker is only cleared when the authoritative gate no longer reports it.

## Verification
- `python3 scripts/ops/verify_ghost_pulse_proof_gate.py --json`
- `python3 scripts/ops/summarize_dirty_worktree_review.py --json`
- `python3 scripts/ops/summarize_dirty_worktree_review.py --require-owned --json`
- `python3 scripts/ops/check_real_readiness.py --write-json --write-md --json`

## Reusable Artifacts
- Keep this workflow as the handoff record for future blocker-clearance work.

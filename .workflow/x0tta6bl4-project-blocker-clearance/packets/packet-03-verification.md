# Packet 03: Verification

## Objective

Run checks that distinguish cleared local blockers from the remaining release
blocker.

## Do

- Run focused unit tests for the dirty-worktree review tool.
- Run Ghost Pulse proof verification.
- Run real-readiness with git and command checks skipped to confirm local static
  readiness.
- Run the full real-readiness gate to identify the remaining blocker.

## Result

Completed for this pass. The full gate returns `REAL_READINESS_BLOCKED`,
`95/96`, with only `git_worktree_clean` failing.

## Verification

- `python3 scripts/ops/check_real_readiness.py --skip-command-checks --skip-git-check --json`
- `python3 scripts/ops/check_real_readiness.py --json`

# Packet 02: Dirty Worktree Review

## Objective

Make the dirty worktree actionable without staging, committing, deleting, or
reverting unrelated work.

## Do

- Ensure every dirty path has an owner candidate.
- Split the dirty tree into reviewable packages with suggested checks.
- Keep staging examples explicit with `git add -- ...`.
- Block unsafe shortcuts such as `git add -A` and `git add .`.

## Result

Completed for owner readiness. The generated review reports
`DIRTY_WORKTREE_OWNER_REVIEW_READY`, `unowned_path_count=0`, and
`--require-owned` exits `0`.

## Verification

- `PYTHONPATH=. ./.venv/bin/pytest tests/unit/scripts/test_summarize_dirty_worktree_review.py -q --no-cov`
- `python3 scripts/ops/summarize_dirty_worktree_review.py --agent codex-implementer --require-owned --max-command-paths 3`

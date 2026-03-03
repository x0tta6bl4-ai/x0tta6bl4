# MAAS Platform Cleanup Runbook (10-Day Focus)

## Purpose
This runbook operationalizes the cleanup-first phase before any new MAAS feature work.
The objective is to remove branch noise, stabilize staging checks, and produce a release candidate path that is repeatable.

## Scope
- Stabilize and verify staging (`make up/status/test`).
- Enforce single-purpose PR discipline.
- Keep agent orchestration checks reproducible (`make agent-cycle-dry`).
- Produce a release-candidate readiness sequence.

## Non-Goals
- No new feature development.
- No broad refactors outside stability fixes.
- No API contract expansions unless required for break/fix.

## Entry Criteria
- Active branch exists with current cleanup work.
- Docker daemon available.
- Local repo state is inspectable (`git status`).

## Baseline Snapshot
```bash
make cleanup-baseline
```

Expected:
- Branch and commit printed.
- `git status --short` visible for triage.
- Staging compose services listed.

## Cleanup Gate (repeatable)
```bash
make cleanup-gate
```

This gate performs:
1. `docker compose ps`
2. `GET /health` (JSON parse)
3. `GET /metrics` (non-empty, not 404 payload)
4. `make status`
5. `make test`
6. `make agent-cycle-dry`

Pass condition:
- Script exits with `PASS`.

## RC Verification Path
```bash
make cleanup-rc-check
```

Expected:
- Staging stack starts cleanly.
- Cleanup gate passes end-to-end.

## Single-Purpose PR Rules
- One PR = one purpose.
- PR must list out-of-scope items explicitly.
- PR must include exact verification commands and rollback note.

## Exit Criteria (Definition of Done)
- `make cleanup-gate` passes on target branch.
- No restart-loop in staging core services.
- `/metrics` is exposed and scrapeable.
- `make agent-cycle-dry` is green.
- PR artifacts include risk and rollback statement.

## Rollback
If cleanup gate fails after change merge:
1. Revert the offending PR.
2. Re-run:
   ```bash
   make up
   make cleanup-gate
   ```
3. Re-open issue with failing step output.

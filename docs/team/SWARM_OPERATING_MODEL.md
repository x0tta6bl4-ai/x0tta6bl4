# Swarm Operating Model (4 Local Agents + Coordinator)

Last updated: 2026-02-21

## Purpose

This document defines a strict workflow for parallel AI agents so they do not
touch overlapping files and do not block each other in `develop`.

## Roles

1. `gemini-architect`: architecture, contracts, acceptance criteria, TODO plans.
2. `codex-implementer`: direct code implementation in assigned paths.
3. `claude-reviewer`: review/refactor inside already changed files.
4. `glm-rnd`: alternatives, stress cases, performance hypotheses in isolated scope.
5. `lead-coordinator`: merge order, ownership matrix updates, release notes.

## Fixed path ownership (current sprint)

See machine-readable matrix in `docs/team/swarm_ownership.json`.

## Pipeline

1. Design in plan/notes (`gemini-architect`).
2. Draft implementation (`codex-implementer`).
3. Alternative ideas and stress scenarios (`glm-rnd`).
4. Review and targeted fixes (`claude-reviewer`).
5. Merge and status sync (`lead-coordinator`).

## Hard rules

1. Every agent works only in its own worktree.
2. Stage files explicitly (`git add <path>`), never `git add -A`.
3. Commits may include only owned paths from ownership matrix.
4. Cross-scope change requires a handoff note in commit message or MR text.
5. `docs/STATUS.md` is maintained by a single owner per cycle (currently `agent2-ml-rag`).

## Hook-based guardrail

Use:

```bash
export SWARM_AGENT=agent1-ml-core   # or another role from swarm_ownership.json
scripts/agents/install_swarm_hook.sh
```

After that, `pre-commit` checks staged files against the ownership matrix and
blocks commits that include non-owned files.

## Conflict resolution

1. Stop commit if ownership check fails.
2. Move non-owned hunks into a handoff branch/worktree.
3. Ask owner to cherry-pick or apply.

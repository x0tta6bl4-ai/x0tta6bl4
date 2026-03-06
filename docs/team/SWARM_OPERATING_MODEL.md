# Swarm Operating Model (Current Local Agents + Coordinator)

Last updated: 2026-03-06

## Purpose

This document defines the strict workflow for parallel AI agents so they do not
touch overlapping files, and so they share one offline request channel in
`develop`.

## Roles

1. `gemini`: eBPF datapath and live-attach follow-up.
2. `codex`: 5G/Open5GS transport and integration tests.
3. `claude`: verification/evidence/compliance lane.
4. `lead-coordinator`: roadmap sync, ownership updates, release notes.

## Fixed path ownership (current sprint)

See machine-readable matrix in `docs/team/swarm_ownership.json`.

## Pipeline

1. Refresh roadmap-derived next tasks (`lead-coordinator` or any agent on demand).
2. Execute lane-specific tranche in owned paths (`gemini`, `codex`, `claude`).
3. Post blockers, evidence status, and handoffs into the shared request thread.
4. Sync the roadmap queue again when priorities or blockers change.

## Execution Contours

All work runs in one of two strict contours:

1. `verification`: reproducible checks, tests, renders, plan-only harnesses,
   evidence snapshots, and documentation alignment.
2. `validation`: live-path checks that depend on real NICs, root, CI identity,
   clusters, hardware, or external endpoints.

Rules:

1. Do not mix `verification` and `validation` in one session.
2. Every roadmap task must declare a `mode`.
3. `bash scripts/agent-coord.sh next_task <agent>` uses the agent's
   `preferred_mode` from `plans/ROADMAP_AGENT_QUEUE.json`.
4. Use `--mode verification|validation` on `session_start` or `next_task` when
   you need to override the default.
5. `session_start --mode validation` runs a lightweight preflight derived from
   validation-task prerequisites in `plans/ROADMAP_AGENT_QUEUE.json`.
6. If preflight is blocked, the session does not open unless the operator
   explicitly passes `--allow-blocked`.

## Authoritative Coordination Channel

Use one shared state only:

- lease and heartbeat state: `.git/swarm/coordination_state.json`
- stable agent front door: `scripts/agent-coord.sh`
- request thread lifecycle: `scripts/agents/swarm_coord.py`
- stable agent entrypoint: `scripts/agents/request_channel.sh`
- mandatory startup instructions: `AGENT_SYNC_INSTRUCTIONS.md`

`COORDINATION.md` is a human-facing landing page only. It is not the
authoritative mutable request state.

## Hard rules

1. Every agent works only in its own worktree.
2. Stage files explicitly (`git add <path>`), never `git add -A`.
3. Commits may include only owned paths from ownership matrix.
4. `pre-commit` auto-acquires staged-file leases and blocks collisions.
5. Cross-scope change requires a handoff note in commit message or MR text.
6. `docs/STATUS.md` is maintained by a single owner per cycle (currently `agent2-ml-rag`).

## Hook-based guardrail

Use:

```bash
scripts/agents/install_swarm_hook.sh
scripts/agents/start_swarm_session.sh agent1-ml-core
scripts/agents/swarm_coord.py status
```

After that, `pre-commit` checks staged files against the ownership matrix and
blocks commits that include non-owned files.
It also tries to lease staged files in shared `.git/swarm` state and fails
if another agent currently holds an active lease.
`start_swarm_session.sh` stores current agent marker in worktree git-dir, so
hooks work even if `SWARM_AGENT` is not exported in shell.

## Lease operations (automatic + manual)

Automatic:

1. On each commit, pre-commit runs:
   - ownership validation
   - staged lease acquire/refresh (`ensure-staged`)
2. If any staged path is leased by another agent, commit is blocked.
3. After successful commit, post-commit releases leases for committed paths.

Manual:

```bash
scripts/agents/swarm_coord.py claim --agent agent1-ml-core --paths src/ml/__init__.py
scripts/agents/swarm_coord.py heartbeat --agent agent1-ml-core
scripts/agents/swarm_coord.py release --agent agent1-ml-core
scripts/agents/swarm_coord.py status
```

Per-request sync:

```bash
bash scripts/agent-coord.sh session_start codex "short request summary"
bash scripts/agent-coord.sh next_task codex
bash scripts/agent-coord.sh roadmap_sync lead-coordinator
bash scripts/agent-coord.sh log codex intent '{"message":"what changed"}'
bash scripts/agent-coord.sh session_end codex '{"result":"done or handoff"}'
```

Rules:

1. Before each new request, run `bash scripts/agent-coord.sh session_start <agent> "summary"`.
2. During work, post short notes for intent, blockers, decisions, and handoffs.
3. Close the request with an explicit result or next action.
4. Do not create a parallel request state in `.paradox` or `.paradox.log`.
5. Use `plans/ROADMAP_AGENT_QUEUE.json` as the machine-readable dispatch layer derived from canonical roadmap sources.

## Roadmap Dispatch

Canonical planning precedence remains:

1. `plans/MASTER_100_READINESS_TODOS_2026-02-26.md`
2. `plans/EXECUTION_BACKLOG_Q1_2026_W7_W8.md`
3. `ROADMAP.md` and `plans/ROADMAP_CANONICAL_STATUS_2026-02-27.md`

Operational next-task distribution uses:

- `plans/ROADMAP_AGENT_QUEUE.json` as the curated machine-readable queue
- `scripts/agents/swarm_coord.py roadmap-sync` to sync it into shared swarm state
- `bash scripts/agent-coord.sh next_task <agent>` to show the next roadmap-derived task for that lane
- `bash scripts/agent-coord.sh dispatch_ready lead-coordinator --bucket verification-ready`
  to fan out ready tasks into agent inboxes with mode, bucket, command, and
  evidence target attached

`session_start` now prints the next roadmap task automatically for the current
agent, using either the explicitly requested mode or the queue's
`preferred_mode`.
It also prints the task's current execution bucket, so operators can distinguish
`verification-ready` work from `live-validation-only` work without opening the
queue JSON manually.

The queue now exposes three machine-readable execution buckets:

1. `verification-ready`
2. `live-validation-only`
3. `blocked-horizon-2`

Session automation:

```bash
scripts/agents/start_swarm_session.sh agent1-ml-core
scripts/agents/stop_swarm_session.sh agent1-ml-core
```

`start_swarm_session.sh` does:

1. installs hooks (`core.hooksPath=.githooks`);
2. claims all literal files from current ownership scope;
3. starts a heartbeat daemon in shared `.git/swarm`.

## Conflict resolution

1. Stop commit if ownership check fails.
2. Move non-owned hunks into a handoff branch/worktree.
3. Ask owner to cherry-pick or apply.

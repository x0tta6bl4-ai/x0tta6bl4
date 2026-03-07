# Agent Sync Instructions

## Purpose

Single offline coordination channel for every request across Codex, Claude, Gemini,
and any other local agent runtime.

Authoritative state lives in shared git-common-dir swarm state:

- `.git/swarm/coordination_state.json`

Do not use `.paradox` or `.paradox.log` as request state. They are legacy and
not authoritative here.

## Mandatory Start Of Every Request

Run exactly one session-start command before planning or editing:

```bash
bash scripts/agent-coord.sh session_start codex "short request summary"
```

This is the stable front door. Internally it reuses the shared swarm request
thread. If another agent already opened the request, it shows the active thread
instead of creating a duplicate one.

`python3 scripts/agents/run_agent_cycle.py` now mirrors cycle START/HB/END
events into this same coordination front door through `scripts/agent-coord.sh`.
Legacy `.paradox.log` sync is opt-in only via `--sync-paradox-log`.
If no active request thread exists, the cycle can auto-open one and close it
after completion.

Allowed short agent ids for the front door are:

- `codex`
- `claude`
- `gemini`
- `lead-coordinator`

The backend request thread also accepts longer ids such as:

- `codex-implementer`
- `claude-code`
- `gemini-architect`

Request notes do not require ownership-matrix membership. File leases still do.

## Execution Modes

Run each session in exactly one execution contour:

- `verification`: reproducible checks, tests, renders, evidence snapshots
- `validation`: live-path checks that depend on root, real NICs, hardware,
  clusters, CI identity, or external endpoints

Do not mix both contours in one session. If work crosses that boundary, end the
current session and start a new one with the other mode.

Examples:

```bash
bash scripts/agent-coord.sh session_start claude --mode verification "refresh release-gate evidence"
bash scripts/agent-coord.sh session_start gemini --mode validation "live XDP attach on real NIC"
bash scripts/agent-coord.sh next_task gemini --mode validation
```

`session_start` and `next_task` now read `mode` metadata from
`plans/ROADMAP_AGENT_QUEUE.json`. If `--mode` is omitted, the current agent's
`preferred_mode` from that queue is used.

Validation sessions now run a lightweight preflight before opening the request
through the front door. Current prereq checks come from validation tasks in
`plans/ROADMAP_AGENT_QUEUE.json`.

If the validation preflight is blocked, `session_start --mode validation`
returns non-zero and does not open a new session. For standby or handoff only,
you may override this explicitly:

```bash
bash scripts/agent-coord.sh session_start gemini --mode validation --allow-blocked "standby only"
```

`--allow-blocked` does not upgrade any live claim. It only allows a blocked
validation lane to coordinate without silently pretending prereqs exist.

## Optional Gemini Proxy Launcher

For local Gemini CLI sessions only, use the repo-local launcher instead of
changing global shell state:

```bash
scripts/agents/start_gemini_proxy.sh --proxy http://127.0.0.1:7890
```

Behavior:

- exports `HTTPS_PROXY` and `HTTP_PROXY` for the launched Gemini process only
- preserves `NO_PROXY=localhost,127.0.0.1,::1` and merges existing values
- adds `--use-env-proxy` unless you already passed it explicitly
- can export `NODE_OPTIONS=--max-old-space-size=...` for Gemini OOM recovery

Dry-run:

```bash
scripts/agents/start_gemini_proxy.sh --proxy http://127.0.0.1:7890 --no-exec --print-env
```

High-memory resume after Node/V8 OOM:

```bash
scripts/agents/start_gemini_proxy.sh --node-max-old-space-size 4096 -- --resume
```

Proxy + high-memory resume:

```bash
scripts/agents/start_gemini_proxy.sh --proxy http://127.0.0.1:7890 --node-max-old-space-size 4096 -- --resume
```

This launcher is an operator convenience path only. It is not release evidence
and does not change the verification state of any live networking claim.
Treat the child Gemini process as a disposable recovery subprocess, not as a
new autonomous coordination lane. It should still follow the same request
thread and ownership boundaries as the parent session.

## Isolated Smoke Tests

If you need to validate the coordination flow without touching the shared live
request thread, use environment overrides:

```bash
export X0TTA6BL4_SWARM_STATE_DIR=/tmp/x0tta6bl4-swarm-smoke
export X0TTA6BL4_AGENT_COORD_DIR=/tmp/x0tta6bl4-agent-coord-smoke
```

All `agent-coord.sh`, `request_channel.sh`, `swarm_coord.py`, and
`run_agent_cycle.py` calls inherit these overrides automatically.

## During Work

Post short notes whenever intent, blockers, decisions, or handoffs change:

```bash
bash scripts/agent-coord.sh log codex intent \
  '{"message":"hardening 5G request validation path","files":["edge/5g/upf-integration.go","test/fedml-integration_test.go"],"next":"add edge-case coverage"}'

# direct backend access is still available:
scripts/agents/request_channel.sh note \
  --agent codex \
  --kind intent \
  --message "hardening 5G request validation path" \
  --files edge/5g/upf-integration.go test/fedml-integration_test.go \
  --next "add edge-case coverage"
```

Allowed note kinds:

- `start`
- `intent`
- `progress`
- `decision`
- `blocker`
- `handoff`
- `done`
- `alert`

Read the current thread at any time:

```bash
bash scripts/agent-coord.sh status
bash scripts/agent-coord.sh next_task codex
bash scripts/agent-coord.sh dispatch_ready lead-coordinator --bucket verification-ready --dry-run
bash scripts/agent-coord.sh roadmap_sync lead-coordinator
scripts/agents/request_channel.sh show
scripts/agents/request_channel.sh tail --limit 12
```

Roadmap-derived next tasks come from:

- `plans/ROADMAP_AGENT_QUEUE.json` (machine-readable dispatch layer)
- `ROADMAP.md`
- `plans/ROADMAP_CANONICAL_STATUS_2026-02-27.md`
- `plans/MASTER_100_READINESS_TODOS_2026-02-26.md`
- `plans/EXECUTION_BACKLOG_Q1_2026_W7_W8.md`

Use `roadmap_sync` after roadmap priorities change. `session_start` already shows
the current next task for the active agent.
It now also shows the current execution bucket for that task:

- `verification-ready`
- `live-validation-only`
- `blocked-horizon-2`

Bucket summaries now print `ready / total`, and `next_task` explicitly says
when no ready tasks remain and it is only showing non-ready backlog for
visibility.

To fan out the current ready queue into agent inboxes without copying commands by
hand, use:

```bash
bash scripts/agent-coord.sh dispatch_ready lead-coordinator --bucket verification-ready
```

Useful filters:

- `--bucket verification-ready`
- `--bucket live-validation-only`
- `--agent codex`
- `--mode verification`
- `--dry-run`

Roadmap tasks are tagged with one of:

- `verification`
- `validation`

Queue contract:

- duplicate task ids are invalid
- `live-validation-only` tasks must not be marked `completed` without an
  explicit `completed_evidence` field
- allowed execution buckets are:
  - `verification-ready`
  - `live-validation-only`
  - `blocked-horizon-2`

Autonomous execution rule:

- if a task is not present in `plans/ROADMAP_AGENT_QUEUE.json`, it is not an
  active execution lane
- references in old docs, archive notes, or ad-hoc exploration do not activate
  a task by themselves
- current example: `k6 load test` remains `NOT VERIFIED YET` and must not be
  started as an autonomous tranche unless it is explicitly queued
- `session_start` now blocks summaries that explicitly ask for `k6/load test`
  work when no queued lane for that agent covers it; use `--allow-blocked`
  only for standby/handoff, not for evidence promotion
- `blocked-horizon-2` tasks must keep `status=blocked`

## Completion Or Handoff

Close the request when the working slice is complete or explicitly handed off:

```bash
bash scripts/agent-coord.sh session_end codex \
  '{"result":"5G verify harness added; live Open5GS still not verified","next":"operator can run bash scripts/verify-5g-path.sh"}'

# direct backend access is still available:
scripts/agents/request_channel.sh close \
  --agent codex \
  --result "5G verify harness added; live Open5GS still not verified" \
  --next "operator can run bash scripts/verify-5g-path.sh"
```

## Contract

1. One active request thread at a time in shared swarm state.
2. Every agent reads the active thread before doing new work.
3. Every agent posts at least one note before or during edits.
4. Close the thread with an explicit result or handoff.
5. Keep `VERIFIED`, `SIMULATED`, and `NOT VERIFIED` wording exact in notes.

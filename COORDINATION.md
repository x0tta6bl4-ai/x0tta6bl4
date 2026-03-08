# x0tta6bl4 Coordination Landing Page

This file is generated from `docs/team/coordination-landing.template.md`.
Do not edit it manually. Regenerate with:

- `bash scripts/agents/render_coordination_landing.sh`

This file is a human-facing entrypoint only.

Authoritative request state lives in shared swarm state:

- `.git/swarm/coordination_state.json`

Stable front door for every local agent:

- `bash scripts/agent-coord.sh session_start <agent> "short request summary"`
- `bash scripts/agent-coord.sh next_task <agent>`
- `bash scripts/agent-coord.sh roadmap_sync lead-coordinator`
- `bash scripts/agent-coord.sh log <agent> <event> '{"message":"..."}'`
- `bash scripts/agent-coord.sh session_end <agent> '{"result":"done or handoff","next":"next action"}'`

Compatibility artifacts still exist for local tooling:

- `.agent-coord/state.json`
- `.agent-coord/log.jsonl`
- `.agent-coord/inbox/<agent>.jsonl`

`python3 scripts/agents/run_agent_cycle.py` mirrors `cycle_start`, `cycle_result`,
and `cycle_end` into this same front door through `scripts/agent-coord.sh`.

Legacy `.paradox` and `.paradox.log` are not authoritative request state.
Do not open a parallel coordination flow there.

Use these documents for the current operating model:

- `AGENT_SYNC_INSTRUCTIONS.md`
- `AGENTS.md`
- `docs/team/SWARM_OPERATING_MODEL.md`
- `plans/ROADMAP_AGENT_QUEUE.json`

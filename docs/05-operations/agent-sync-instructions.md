# x0tta6bl4 Multi-Agent Sync Instructions

## Scope

Current offline coordination playbook for local agents. Historical references to
`.paradox` and `.paradox.log` are deprecated for request-level coordination.

## Source Of Truth

Authoritative request state:

- `.git/swarm/coordination_state.json`

Stable front door:

- `bash scripts/agent-coord.sh`

Compatibility artifacts used by local tooling:

- `.agent-coord/state.json`
- `.agent-coord/log.jsonl`
- `.agent-coord/inbox/<agent>.jsonl`

Primary companion docs:

- `AGENT_SYNC_INSTRUCTIONS.md`
- `AGENTS.md`
- `docs/team/SWARM_OPERATING_MODEL.md`

## Fast Execution

- Run parallel cycle with skill context generation:
  - `python3 scripts/agents/run_agent_cycle.py`
- Strict gate mode:
  - `python3 scripts/agents/run_agent_cycle.py --strict`
- Dry-run planning:
  - `python3 scripts/agents/run_agent_cycle.py --dry-run`
- Disable all coordination sinks for isolated local experiments:
  - `python3 scripts/agents/run_agent_cycle.py --no-sync-agent-coord --no-sync-paradox-log`
- Enable legacy paradox log mirror only if a specific external consumer still needs it:
  - `python3 scripts/agents/run_agent_cycle.py --sync-paradox-log`

## Communication Scheme

1. Session start:
- Run `bash scripts/agent-coord.sh session_start <agent> "summary"`.
- Read the active request thread and inbox before editing.

2. During work:
- Post short progress, blocker, decision, or handoff notes through `agent-coord.sh log`.
- Keep file leasing and ownership checks in shared swarm state.

3. Completion or handoff:
- Run `bash scripts/agent-coord.sh session_end <agent> '{"result":"...","next":"..."}'`.
- If another agent needs context, use `bash scripts/agent-coord.sh send ...`.

## Lock And Lease Rules

- Shared request thread and file leases are separate concerns.
- Request notes live in shared swarm request state.
- File lease ownership remains enforced through swarm hooks and `swarm_coord.py`.
- Do not recreate a second mutable request ledger in `.paradox` or `.paradox.log`.

## Minimal Templates

Start:

```bash
bash scripts/agent-coord.sh session_start codex "short request summary"
```

Progress:

```bash
bash scripts/agent-coord.sh log codex progress '{"message":"what changed","next":"next action"}'
```

End:

```bash
bash scripts/agent-coord.sh session_end codex '{"result":"done or handoff","next":"next action"}'
```

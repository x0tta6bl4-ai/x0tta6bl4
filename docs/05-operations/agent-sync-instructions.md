# x0tta6bl4 Multi-Agent Sync Instructions

## Scope
Operational playbook for exactly 4 agents working in parallel.
Use with `.paradox` (authoritative state) and `.paradox.log` (append-only timeline).
Current runtime mode: `normal` (4 active agents: `agent-1`, `agent-2`, `agent-3`, `agent-4`; restored by `D025/V025` on 2026-02-16).

## Source Of Truth
- `.paradox`: roles, locks, tasks, discussions, votes, session log.
- `.paradox.log`: chronological communication events.
- `AGENT_SYNC_PROTOCOL_4_AGENTS.md`: stable protocol details and templates.

## Fast Execution
- Run parallel cycle with skill context generation:
  - `python3 scripts/agents/run_agent_cycle.py`
- Strict gate mode (any agent failure blocks):
  - `python3 scripts/agents/run_agent_cycle.py --strict`
- Dry-run planning (no command execution):
  - `python3 scripts/agents/run_agent_cycle.py --dry-run`
- Disable protocol log sync for local experiments:
  - `python3 scripts/agents/run_agent_cycle.py --no-sync-paradox-log`

## Current Snapshot (2026-02-16)
Agent | Role | Ownership | Current Focus
--- | --- | --- | ---
agent-1 | Architect | `src/core/`, `src/api/`, `src/config/`, `libx0t/core/` | architecture/API compatibility review + T006 design support
agent-2 | Security | `src/crypto/`, `src/security/`, `src/network/obfuscation/`, `libx0t/crypto/` | T006 security regression + risk gate
agent-3 | Network | `src/network/`, `src/mesh/`, `src/consensus/`, `src/swarm/`, `libx0t/network/` | T006 network/obfuscation validation + integration follow-up
agent-4 | Quality | `tests/`, `src/testing/`, `src/quality/`, `src/monitoring/` | T006 coverage push + CI quality gate

## Current Task State
- `T001` done
- `T002` done
- `T003` done
- `T004` done
- `T005` done
- `T006` done
- `T007` done
- `T008` done
- `T009` done
- `T010` done
- `T011` done
- `T012` done

## Communication Scheme
1. Session start:
- Read `.paradox` completely.
- Add `[START]` entry to `.paradox.log` with task, files, ETA.
- Claim task / update status in `.paradox` before editing.

2. During work:
- Heartbeat every 30 minutes: `[HB] task=<id> done=<...> blocked=<yes/no> next=<...>`.
- Add or renew lock entries in `.paradox` for edited files.
- If blocked >15 minutes, open a `DISCUSSIONS` entry (`Dxxx`).

3. On completion or handoff:
- Update task status and locks in `.paradox`.
- Add `[END]` entry in `.paradox.log` with result and next owner/action.
- Keep code and `.paradox` updates atomic in the same commit.

## Discussion And Voting
- Dispute flow: `DISCUSSIONS (Dxxx)` -> two rounds -> `VOTES (Vxxx)` if unresolved.
- Quorum: 3/4 in normal mode, 2/2 in degraded mode; winner: simple majority.
- Tie-break: `agent-1` for architecture/process.
- Security veto: `agent-2` can block security-regressing options.
- Decisions D010-D025 and votes V010-V025 are resolved and active.

## File Lock Rules
- Lock before editing and release immediately after commit/handoff.
- Lock TTL: 120 minutes.
- Never edit files under another active lock.

## Message Templates
`[TIMESTAMP] agent-X: [START] task=T00Y files=<paths> eta=<minutes>`

`[TIMESTAMP] agent-X: [HB] task=T00Y done=<summary> blocked=<yes/no> next=<action>`

`[TIMESTAMP] agent-X: [DISCUSSION D0ZZ] position=<one line> risk=<one line> proposal=<one line>`

`[TIMESTAMP] agent-X: [VOTE V0ZZ] option=<A|B|C> reason=<one line>`

`[TIMESTAMP] agent-X: [END] task=T00Y result=<done|partial|blocked> handoff=<next owner>`

## Immediate Next Actions
1. `agent-4`: run consolidated CI quality gate and attach updated coverage artifacts.
2. `agent-2`: perform security regression sweep for the newly covered modules and sign off.
3. `agent-3`: validate remaining network integration edges after T007/T006 closure.
4. `agent-1`: prepare next execution backlog and moderate cross-agent planning in normal mode.

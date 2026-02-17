# x0tta6bl4 Four-Agent Sync Protocol

Baseline read: `.paradox` (2026-02-16).
This file is the coordination guide for exactly 4 working agents.
Current runtime mode: `normal` (4 active agents: `agent-1`, `agent-2`, `agent-3`, `agent-4`; restored in `D025/V025`).

## 1. Roles and ownership

| Agent | Role | Owns | Current tasks |
|---|---|---|---|
| `agent-1` | Architect | `src/core/`, `src/api/`, `src/config/`, `libx0t/core/` | architecture/API compatibility review + T006 design support |
| `agent-2` | Security | `src/crypto/`, `src/security/`, `src/network/obfuscation/`, `libx0t/crypto/` | T006 security regression + risk gate |
| `agent-3` | Network | `src/network/`, `src/mesh/`, `src/consensus/`, `src/swarm/`, `libx0t/network/` | T006 network/obfuscation validation + integration follow-up |
| `agent-4` | Quality | `tests/`, `src/testing/`, `src/quality/`, `src/monitoring/` | T006 coverage push + CI quality gate |

## 2. Task sync map

| Task | Owner | Status | Can start when |
|---|---|---|---|
| `T001` | `agent-1` | done | completed |
| `T005` | `agent-2` | done | completed |
| `T002` | `agent-1` | done | completed |
| `T003` | `agent-3` | done | completed |
| `T004` | `agent-4` | done | completed |
| `T006` | `agent-2` (with `agent-4` quality support) | done | completed |
| `T007` | `agent-1` + `agent-3` | done | completed |
| `T008` | `agent-2` | done | completed |
| `T009` | `agent-2` + `agent-1` | done | completed |
| `T010` | `agent-3` + `agent-2` | done | completed |
| `T011` | `agent-2` | done | completed |

Execution rule: before any work unit, update task status and lock entries in `.paradox`.

## 3. Communication scheme

Primary state: `.paradox`  
Chronological log: `.paradox.log`

Required cadence:
1. Session start: one `[START]` log line + task claim in `.paradox`.
2. Heartbeat every 30 minutes: one `[HB]` line with progress or blocker.
3. Immediate `[ALERT]` line for hard blockers or conflicts.
4. Handoff on pause/finish: one `[END]` line + task/lock update in `.paradox`.

Message format:
`[TIMESTAMP] agent-X: [TAG] task=<id> files=<paths> status=<state> next=<action>`

## 4. Discussion and dispute protocol

Use this whenever architecture, security, or dependency order is contested.

1. Open `DISCUSSIONS` item in `.paradox` with id `Dxxx`.
2. Round A (position): each agent posts one short stance.
3. Round B (dispute): each agent challenges one risk or assumption.
4. Moderator summarizes options in 3 bullets max.
5. If still unresolved, start `VOTES` item `Vxxx`.

Moderator rotation: `agent-1 -> agent-2 -> agent-3 -> agent-4` (per decision).

## 5. Voting rules

1. Quorum: 3 of 4 agents in normal mode; 2 of 2 active agents in degraded mode.
2. Winner: simple majority.
3. Tie: moderator decides for process issues, `agent-1` decides for architecture issues.
4. Security veto: `agent-2` can block decisions that reduce security posture.
5. Vote timeout: 2h for urgent items, 24h for normal items.
6. Decision must be written back to `.paradox` with rationale and follow-up actions.

## 6. Kickoff decisions (completed)

Decisions recorded in `.paradox`:
1. `D010` + `V010`: security-first order approved.
2. `D011` + `V011`: `T009` split approved (agent-2 crypto core, agent-1 compatibility layer).
3. `D012` + `V012`: full quality gate approved before `T007`.
4. `D013` + `V013`: architect focus moved to `T006` support and sync cleanup.
5. `D014` + `V014`: switched to degraded two-agent operation mode (`agent-2`, `agent-4`).
6. `D015` + `V015`: confirmed strict two-agent mode after conflicting reactivation update.
7. `D025` + `V025`: restored full four-agent normal mode by explicit user command.

Current execution queue:
1. `agent-4`: run consolidated CI quality gate and publish updated coverage artifacts.
2. `agent-2`: complete security regression sign-off for the newly covered modules.
3. `agent-3`: execute remaining network integration checks post T007/T006 closure.
4. `agent-1`: coordinate next backlog and facilitate cross-agent planning.

## 7. Locking protocol

1. Add lock in `.paradox` before editing any file.
2. Lock TTL: 120 minutes.
3. Renew on heartbeat if still active.
4. Never edit files in another active lock.
5. Remove lock immediately after commit/handoff.

## 8. Copy-paste templates

Start:
`[TIMESTAMP] agent-X: [START] task=T00Y files=<paths> eta=<minutes>`

Heartbeat:
`[TIMESTAMP] agent-X: [HB] task=T00Y done=<summary> blocked=<yes/no> next=<action>`

Dispute:
`[TIMESTAMP] agent-X: [DISCUSSION D0ZZ] position=<one line> risk=<one line> proposal=<one line>`

Vote:
`[TIMESTAMP] agent-X: [VOTE V0ZZ] option=<A|B|C> reason=<one line>`

End:
`[TIMESTAMP] agent-X: [END] task=T00Y result=<done|partial|blocked> handoff=<next owner>`

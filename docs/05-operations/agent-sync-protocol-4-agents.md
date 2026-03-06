# x0tta6bl4 Four-Agent Sync Protocol

Historical role/ownership guide for 4-agent mode.
Current request coordination no longer uses `.paradox` as authoritative state.
Use `bash scripts/agent-coord.sh ...` backed by shared swarm state.

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

Execution rule: before any work unit, open or join the active request thread and
respect file ownership / lease rules from shared swarm state.

## 3. Communication scheme

Primary request state: `.git/swarm/coordination_state.json`  
Stable front door: `scripts/agent-coord.sh`

Required cadence:
1. Session start: `bash scripts/agent-coord.sh session_start <agent> "summary"`.
2. During work: `bash scripts/agent-coord.sh log <agent> <event> '{"message":"..."}'`.
3. Hard blocker or conflict: post a blocker note or handoff note immediately.
4. Pause/finish: `bash scripts/agent-coord.sh session_end <agent> '{"result":"...","next":"..."}'`.

Message format:
`agent-coord.sh` and the swarm-backed request thread record timestamps and agent metadata automatically.

## 4. Discussion and dispute protocol

Use this whenever architecture, security, or dependency order is contested.

1. Open a request-thread note that clearly states the contested decision.
2. Round A (position): each agent posts one short stance.
3. Round B (dispute): each agent challenges one risk or assumption.
4. Moderator summarizes options in 3 bullets max.
5. If still unresolved, escalate outside the request thread with an explicit owner.

Moderator rotation: `agent-1 -> agent-2 -> agent-3 -> agent-4` (per decision).

## 5. Voting rules

1. Keep one active request thread, not parallel ledgers.
2. Record the decision and next owner in the request thread.
3. If a security veto or ownership conflict exists, leave the thread open with a blocker note.

## 6. Kickoff decisions (completed)

Historical decisions recorded in older coordination artifacts:
1. `D010` + `V010`: security-first order approved.
2. `D011` + `V011`: `T009` split approved (agent-2 crypto core, agent-1 compatibility layer).
3. `D012` + `V012`: full quality gate approved before `T007`.
4. `D013` + `V013`: architect focus moved to `T006` support and sync cleanup.
5. `D014` + `V014`: switched to degraded two-agent operation mode (`agent-2`, `agent-4`).
6. `D015` + `V015`: confirmed strict two-agent mode after conflicting reactivation update.
7. `D025` + `V025`: restored full four-agent normal mode by explicit user command.

Current execution queue:
Current execution priorities should be taken from the active request thread and
the current ownership matrix, not from legacy `.paradox` tasks.

## 7. Locking protocol

1. Use swarm leases / ownership checks before editing.
2. Never edit files in another active lease without handoff.
3. Request-thread notes do not replace file lease rules.

## 8. Copy-paste templates

Start:
`bash scripts/agent-coord.sh session_start codex "short request summary"`

Progress:
`bash scripts/agent-coord.sh log codex progress '{"message":"what changed","next":"next action"}'`

End:
`bash scripts/agent-coord.sh session_end codex '{"result":"done or handoff","next":"next action"}'`

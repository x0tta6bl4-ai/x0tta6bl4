---
name: agent-sync-efficiency
description: >
  Runs a fast, skill-aware 4-agent execution cycle for x0tta6bl4 with
  parallel checks, generated per-agent contexts, and a consolidated report.
  Use when user asks to continue development faster with agents, accelerate
  execution, or run coordinated architect/security/network/quality loops.
---

# Agent Sync Efficiency

## Purpose

Use this skill to execute one coordinated cycle across 4 agent roles:
- `agent-1` architect
- `agent-2` security
- `agent-3` network
- `agent-4` quality

The cycle is optimized for speed:
- parallel execution by default
- auto-generated context files per agent
- machine-readable + human-readable summaries

## Commands

Quick cycle:

```bash
python3 scripts/agents/run_agent_cycle.py
```

Strict cycle (any agent failure blocks):

```bash
python3 scripts/agents/run_agent_cycle.py --strict
```

Dry-run (show planned commands and generate contexts only):

```bash
python3 scripts/agents/run_agent_cycle.py --dry-run
```

Custom agent set and profile config:

```bash
python3 scripts/agents/run_agent_cycle.py \
  --agents agent-1,agent-4 \
  --profile-file scripts/agents/agent_cycle_profiles.json
```

## Artifacts

Each run creates:
- `.tmp/agent_runs/<timestamp>/contexts/*.context.txt`
- `.tmp/agent_runs/<timestamp>/logs/*.stdout.log`
- `.tmp/agent_runs/<timestamp>/logs/*.stderr.log`
- `.tmp/agent_runs/<timestamp>/summary.json`
- `.tmp/agent_runs/<timestamp>/summary.md`
- optional sync events in `.paradox.log`

## Notes

- Security agent is advisory in non-strict mode; use `--strict` for hard-gating.
- Context files include current sprint pending tasks, sync instructions, role file (if present), and skill instructions.
- Disable paradox sync if needed: `--no-sync-paradox-log`.

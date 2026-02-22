---
name: x0tta6bl4-80-20-executor
description: Run an 80/20 automation cycle for x0tta6bl4 with preconfigured agent profiles and prioritized checks. Use when the user asks to maximize speed and effectiveness, run agents and skills automatically, continue development efficiently, or get fast signal on regressions with minimal compute.
---

# x0tta6bl4 80/20 Executor

## Overview

Execute a high-leverage cycle that focuses on the small set of checks giving most value:
- MaaS API regression (`nodes + escrow + analytics`)
- security crypto scan
- coverage-gap prioritization

Use this skill for automation-first execution when breadth should be traded for fast actionable signal.

## Workflow

1. Choose mode:
- `auto`: pick `quick/focused/full` from current changed files (default; falls back to `focused` if git scan times out)
- `quick`: security + coverage only (fastest)
- `focused`: MaaS regression + security + coverage (default manual 80/20)
- `full`: focused + network regression

Built-in per-agent timeouts:
- `quick`: 900s
- `focused`: 2100s
- `full`: 2700s

Contention-aware behavior:
- If external `pytest` processes are detected, the runner auto-increases timeout (up to +900s) and reduces parallelism by 1.

2. Run the cycle script:

```bash
skills/x0tta6bl4-80-20-executor/scripts/run_80_20_cycle.sh auto
```

3. Read generated run summary from `scripts/agents/run_agent_cycle.py` output:
- `.../summary.md` for operator view
- `.../summary.json` for machine-readable post-processing

4. Prioritize fixes from blocking failures first, then rerun in `focused` mode.

## Commands

Quick signal:

```bash
skills/x0tta6bl4-80-20-executor/scripts/run_80_20_cycle.sh quick
```

Auto-selected cycle:

```bash
skills/x0tta6bl4-80-20-executor/scripts/run_80_20_cycle.sh auto
```

Default manual 80/20 cycle:

```bash
skills/x0tta6bl4-80-20-executor/scripts/run_80_20_cycle.sh focused
```

Full cycle:

```bash
skills/x0tta6bl4-80-20-executor/scripts/run_80_20_cycle.sh full
```

Pass extra runner flags through to the agent cycle:

```bash
skills/x0tta6bl4-80-20-executor/scripts/run_80_20_cycle.sh focused --strict
```

Optional modular billing sanity check:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q -o addopts='' --confcutdir=/mnt/projects/tests/unit/api tests/unit/api/test_maas_services_billing_unit.py
```

## References
- `references/agent_cycle_profiles_80_20.json`: curated commands and mapped skills per agent.

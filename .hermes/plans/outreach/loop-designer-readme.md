# x0tta6bl4 Loop Designer

**A port of [Looper](https://github.com/ksimback/looper) (Kevin Simback) for Hermes Agent.**

Design agent loops **before running them**: formalize the goal, type-check verification criteria, add a cross-model judge, set iteration limits and gates, draw an ASCII flow, and save a portable plan.

## Why

AI agents generate code 10× faster than humans. The bottleneck shifted from *writing* to *verification*.

Loop Designer gives you a repeatable process to design agents loops that don't drift, don't burn budget, and don't lie about being "done."

## How it's different from Looper

| Aspect | Looper (original) | Loop Designer (this port) |
|:-------|:-----------------:|:-------------------------:|
| Platform | Claude Code CLI | Any Hermes Agent provider |
| Judge model | `claude -p` from PATH | `delegate_task` (different provider) |
| Runtime | `run-loop.py` | Hermes `/goal` + `todo` |
| Plan format | `loop.yaml` + JSON | `.hermes/plans/<name>.md` |
| Gates | built into runner | `todo` checklist + delegate_task |
| Models | probe PATH | current provider + fallback |

## Rubrics (loaded on demand)

- `goal` — how to formulate a verifiable goal
- `verification` — typed criteria (programmatic / judge / human)
- `council` — reviewer and judge selection
- `control` — iteration limits, budgets, no-progress detection, auto-PR, worktree mode

## The 7-stage workflow

1. **Goal** — define a concrete, verifiable outcome
2. **Verification** — convert "done" into typed criteria (≥1 programmatic check)
3. **Host** — which model executes (default: current provider)
4. **Council** — add a reviewer (non-blocking) and a judge (structured verdict)
5. **Gates & control** — set `max_iterations`, `max_revisions`, no-progress, budget, auto-PR
6. **Confirmation** — render ASCII flow diagram, confirm
7. **Emit** — save plan, set `/goal` and `todo`, suggest run now

## Judge structured verdict

```json
{
  "verdict": "pass",
  "blocking_issues": [],
  "confidence": 0.86,
  "notes": "Artifact satisfies rubric."
}
```

Valid verdicts: `pass`, `revise`. Unparseable → `revise` + warning.

## Storage

Plans go to `.hermes/plans/<name>/`:
```
.hermes/plans/<name>/
├── loop.yaml              # loop description (YAML frontmatter)
├── plan.md                # execution plan
├── state.json             # current state
├── state.md               # human-readable state
└── run-log.md             # execution log
```

## Prerequisites

- Hermes Agent (any provider)
- git (for worktree mode)
- gh CLI (for auto-PR mode)

## Getting started

```bash
# Load the skill in a Hermes session
load x0tta6bl4-loop-designer

# Or just start with the trigger phrase:
"спроектируй цикл для задачи X"
"design a loop for Y"
"agent loop for Z"
```

## Links

- **Original Looper:** https://github.com/ksimback/looper
- **x0tta6bl4 project:** https://github.com/x0tta6bl4-ai/x0tta6bl4
- **Author:** Daniel Azarov (@X0TTa6bl4 on Telegram)
- **License:** MIT

---

*Built on ideas from Looper by Kevin Simback. Rubrics (goal, verification, council, control) ported, workflow preserved. Orignal: [ksimback/looper](https://github.com/ksimback/looper).*

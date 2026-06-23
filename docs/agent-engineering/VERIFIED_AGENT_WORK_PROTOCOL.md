# Verified Agent Work Protocol

Verified Agent Work Protocol defines the minimum evidence an AI agent must
leave before a task can be accepted.

## Required Receipt Shape

- `task`: the requested work.
- `agent`: the agent that performed the work.
- `tool_audit`: source-truth, memory, MCP, skill, subagent, and manual-path
  fields.
- `verification`: concrete commands with exit codes.
- `verification_summary`: total, passed, and failed counts matching
  `verification`.
- `checklist`: requirement rows with status and evidence.
- `remaining_gaps`: a list, even when empty.

## Acceptance Boundary

A receipt can prove a repo-local package is ready for review or installation.
It cannot prove unrelated runtime, production, customer, payment, or external
service claims.

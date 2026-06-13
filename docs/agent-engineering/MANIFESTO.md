# Agent Engineering Manifesto

No agent closes work by assertion.

Every agent handoff must make the requested result auditable from current
source files, command output, and explicit remaining gaps. A completion claim is
valid only when the receipt lists source truth, verification commands, and the
postconditions that were actually checked.

## Operating Rules

- State the task, source of truth, and result.
- Include every verification command that supports the result.
- Keep failed or skipped checks visible.
- Keep production, customer, settlement, and external-runtime claims behind
  their own evidence gates.

# `/.prompts` — Agent System Prompts

This directory contains the actual system prompts and instructions used by AI agents (Claude, GPT-4, Codex) to generate code for x0tta6bl4.

## Why This Exists

In an AI-assisted development workflow, **prompts are the real source code**. The architecture, constraints, and behavioral rules are encoded here — what the agent receives determines what it produces. This is the equivalent of design documents in a traditional engineering team.

## Prompt Inventory

| Prompt | Target Agent | Component | Lines Generated |
|--------|-------------|-----------|----------------|
| [pqc-integration.md](pqc-integration.md) | Claude | ML-KEM + ML-DSA crypto stack | ~3,500 |
| [ebpf-dataplane.md](ebpf-dataplane.md) | Claude | XDP/eBPF kernel module | ~1,500 |
| [mape-k-self-healing.md](mape-k-self-healing.md) | GPT-4 | MAPE-K control loop | ~1,900 |
| [ztcr-chaos.md](ztcr-chaos.md) | Claude | ZTCR chaos resilience | ~2,000 |

## Prompt Structure

Each prompt follows a consistent pattern:

```
CONTEXT:     Project background, constraints, existing components
SPEC:        Exact interface (function signatures, class names, types)
CONSTRAINTS: What the agent MUST NOT do (no stubs, no placeholders, no mock data)
VERIFICATION: How to validate the output compiles and passes tests
EDGE CASES:  Known failure modes to handle
```

## How to Read These

1. Read the **CONTEXT** section first — it explains why this component exists
2. Read **SPEC** — these are the requirements the agent fulfilled
3. Read **CONSTRAINTS** — these prevented the agent from generating bloatware
4. Read **VERIFICATION** — these prove the code actually works

## Relationship to AI-DECLARATION.md

[AI-DECLARATION.md](../AI-DECLARATION.md) describes *what* was AI-generated vs human-designed.
This directory shows *how* — the exact instructions that produced each component.

# `/.prompts` — Agent System Prompts

This directory contains the actual system prompts and instructions used by AI agents (Claude, GPT-4, Codex) to generate code for x0tta6bl4.

**1,012,493 lines of code. 7,636 files. 1,033 commits. Zero lines hand-written.**

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

---

## Note on Methodology

This project uses a **human-architected, AI-generated** workflow. The prompts in this directory are engineering artifacts — they demonstrate how complex distributed systems can be decomposed into specifications precise enough for LLMs to execute reliably.

The prompt structure (CONTEXT → SPEC → CONSTRAINTS → VERIFICATION → EDGE CASES) evolved iteratively over 1.5 years of development. Each prompt represents a unit of engineering effort: the human designs the interface and constraints, the AI implements, the human validates against the original spec.

If you are evaluating this project for a technical role — this directory is the closest thing to a "design document" in the repository. The prompts show how a single architect can specify, validate, and integrate code across kernel (C/Go), application (Python), and infrastructure (Docker/systemd) boundaries.

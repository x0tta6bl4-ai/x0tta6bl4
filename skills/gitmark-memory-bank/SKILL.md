---
name: gitmark-memory-bank
description: >
  Build, inspect, and use the GitMark-style RAG Memory Bank for this repo.
  Use when the user asks for project memory, RAG context, visual documentation
  graphs, GitMark-like docs navigation, or agent context retrieval.
---

# GitMark Memory Bank

## Purpose

Use this skill to turn the repo's Markdown knowledge surface into:
- `.gitmark-memory/index.json` for deterministic search/context retrieval
- `.gitmark-memory/graph.html` for a GitMark-like visual graph

The graph is a navigation and agent-context tool. It is not production evidence.

## Commands

Build the maintained RAG graph:

```bash
python3 scripts/gitmark_memory_bank.py build --root /mnt/projects --out-dir /mnt/projects/.gitmark-memory --profile rag
```

Open the visual graph:

```bash
python3 -m http.server 8765 --bind 127.0.0.1
```

Then open:

```text
http://127.0.0.1:8765/.gitmark-memory/graph.html
```

Search the memory bank:

```bash
python3 scripts/gitmark_memory_bank.py search "Horizon-2 RAG"
```

Render agent-ready context:

```bash
python3 scripts/gitmark_memory_bank.py context "VPN routing evidence" --limit 5
```

## Workflow

1. Run `build --profile rag` after changing docs, skills, agent instructions, or runbooks.
2. Use `search` first for focused questions.
3. Use `context` before doing architecture, RAG, VPN, verification, or planning work.
4. Use `--include-archive` only when the user explicitly asks for historical/archived context.
5. Do not treat graph presence as proof of readiness, production status, external DPI evidence, or VPN health.

## Scope

The `rag` profile indexes root agent files plus `docs`, `services`, `src`, `scripts`, `skills`, `.gemini`, `.claude`, `plans`, `infra`, `deploy`, `deployment`, `monitoring`, `sdk`, and `examples`.

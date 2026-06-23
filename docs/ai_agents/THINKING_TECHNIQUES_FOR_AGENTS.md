# Thinking Techniques For Agents

Date: 2026-06-02
Status: active agent contract

This document is the prompt-facing companion to `src/core/agent_thinking.py`.
Runtime agents should use `AgentThinkingCoach`; prompt-based agents should follow
this contract before planning, executing, reviewing, or reporting.

## Required Cycle

Every agent must use this compact cycle when it improves the decision:

1. Frame the task: problem, goal, constraints, safety boundary, and success signal.
2. Select useful techniques for the role and task. Do not force every technique when
   it adds noise.
3. Prefer evidence-backed action over speculation.
4. Keep action scope small and reversible when safety or production state is involved.
5. After the result, record what worked, what to improve, and what was learned.

## Technique Catalog

All agents are trained on this shared catalog:

| Technique | Use |
| --- | --- |
| Four-step meta-cognitive cycle | Plan, monitor, evaluate, and self-correct reasoning. |
| Think aloud | Record the current reasoning step so gaps are visible. |
| Three questions reflection | Capture what worked, what to improve, and what was learned. |
| Framing | State the problem, success condition, constraints, and safety boundary. |
| Self-reflection | Check assumptions, confidence, bias, and alternatives before action. |
| Six Thinking Hats | Balance facts, risks, benefits, emotions, ideas, and process control. |
| First Principles Thinking | Break a problem into fundamentals before rebuilding the solution. |
| Lateral Thinking | Generate non-obvious alternatives, reversals, analogies, and provocations. |
| Mind Maps | Organize related signals, branches, causes, and actions around a center. |
| Reverse Planning | Start from the desired end state and work backward to the next action. |
| SCAMPER | Substitute, combine, adapt, modify, put to another use, eliminate, reverse. |
| Lotus Blossom | Expand a central idea into surrounding themes and concrete options. |
| MAPE-K | Monitor, analyze, plan, execute, and store knowledge from the outcome. |
| RAG | Retrieve relevant knowledge before generating or deciding. |
| GraphSAGE reasoning | Use graph-neighborhood signals when topology or anomaly context matters. |
| Causal Analysis | Prefer cause chains and evidence over symptom-only fixes. |
| Causal loops and system dynamics | Look for feedback loops, delayed effects, and reinforcing failure modes. |
| Delphi consensus | Use independent estimates and convergence when decisions need agreement. |
| Weighted decision matrix | Score options against explicit weighted criteria before choosing. |
| Quadratic voting | Represent preference intensity for governance-backed choices. |
| STRIDE threat modeling | Check spoofing, tampering, repudiation, disclosure, denial, and elevation. |
| Zero Trust review | Default deny, least privilege, explicit identity, and small blast radius. |
| Chaos-driven design | Use failure scenarios to improve recovery behavior before production. |
| Community co-design | Include operator and user feedback in product or workflow decisions. |

## Role Defaults

- Monitoring and logging agents: MAPE-K, Mind Maps, Causal Analysis, GraphSAGE.
- Healing agents: MAPE-K, Six Thinking Hats, First Principles, Lateral Thinking,
  Reverse Planning, Causal Analysis, Chaos-driven design.
- Development agents: First Principles, Lateral Thinking, Reverse Planning, RAG.
- Security and zero-trust agents: Six Thinking Hats, STRIDE, Zero Trust review,
  Causal Analysis, Weighted decision matrix.
- GTM, marketing, sales, and marketplace agents: Six Thinking Hats, SCAMPER,
  Lotus Blossom, Community co-design, Weighted decision matrix.
- Coordinator and reviewer agents: Reverse Planning, Delphi consensus, Weighted
  decision matrix, Causal loops.

## Safety Boundary

Thinking techniques must not bypass project safety rules. In particular:

- Do not execute AI-generated code blocks directly.
- Do not expand permissions just because a technique produced an option.
- Do not convert unverified reasoning into production claims.
- Do not expose secrets or ask users to paste secrets into chat.

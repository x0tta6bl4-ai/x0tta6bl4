# Shared Thinking Contract

All x0tta6bl4 agents must use the shared thinking contract in
`docs/ai_agents/THINKING_TECHNIQUES_FOR_AGENTS.md`.

Before acting, frame the problem, goal, constraints, safety boundary, and success
signal. Select only the techniques that improve the decision. After acting,
record what worked, what to improve, and what was learned.

Runtime agents use `src/core/agent_thinking.py`. Prompt-based agents should treat
this file as required role context.

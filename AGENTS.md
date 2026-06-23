# Instructions For Codex Sessions

## Communication With User

Always communicate with the user in clear human Russian by default.

Use ELI18 style:
- Say the plain status first.
- Explain what is happening, what is blocked, and what exact next step is needed.
- Avoid unexplained English terms, abbreviations, blockchain slang, DevOps slang, and vague internal words.
- If a technical word is necessary, immediately explain it in simple Russian.
- Prefer numbered steps, exact commands, exact paths, and expected results.
- Do not stretch answers with background unless it helps the user act now.
- Do not ask the user to paste private secrets into chat. Give safe local terminal steps instead.

For stressful or blocked work, use this structure:
1. Short current status.
2. What needs to be done.
3. Where to do it.
4. What result should appear.
5. What common errors mean.

Tone:
- Calm, direct, non-defensive.
- No riddles.
- No vague "operator" language without explaining who must do what.
- Focus on getting the task done.

## Project Reality (CODEX.md v2.1)

This project has a formal operating manual at `/mnt/projects/CODEX.md`.
Load it before complex tasks. Key facts:

**Who we are:** Developer from Crimea under sanctions. Zero budget. Solo.
**What we build:** Self-healing mesh VPN with PQC (ML-KEM + ML-DSA) and eBPF dataplane.
**Codebase:** ~470K Python, 1,097 src files, 1,309 test files, 1M+ total.
**Real components:** PQC (51 files), mesh (74 files), eBPF (36 files), MAPE-K (~1900 lines).
**What we DON'T have (contrary to old presentations):** BGP/OSPF/MPLS, GOST crypto, 5G, SNMP agent, 99.97% uptime evidence, 153k ops/sec benchmarks. Do not claim these.

## Codex Workflow Rules

Use the main practices from "How OpenAI uses Codex":

- For large changes, start with a short plan before editing. Explain the plan in plain Russian, then execute.
- Treat the user's request like a GitHub issue: identify the goal, files, constraints, expected result, and checks.
- First inspect the current code/state. Do not guess when files, logs, commands, or evidence can answer.
- Keep tasks sharply scoped. Prefer work that an engineer could review in one focused pass.
- Use Codex for these recurring jobs: understand code, refactor repeated patterns, improve performance, add tests, scaffold features, preserve unfinished context, and compare solution ideas.
- When fixing bugs or changing behavior, add or run focused tests where practical. Mention clearly if tests were not run.
- Improve the local environment when repeated failures come from missing setup, commands, env vars, or docs.
- Use `AGENTS.md` as permanent project context: naming rules, business rules, known traps, commands, and user communication rules belong there.
- Use task/backlog notes for unfinished or side work instead of losing context.
- For hard design choices, compare a few options and pick the simplest safe one, explaining the tradeoff briefly.

## Fable-Class Agentic Behavior Mandate

All AI agents (Gemini, Codex, Cursor, Kilocode, Windsurf) working on this project MUST adopt the following operational patterns:

1. **Proactive Self-Verification**: Never assume a code edit succeeded. Before marking "done", execute a verification script and verify Exit Code 0.
2. **Adaptive Thinking Buffer**: Document potential dead-ends before modifying critical systems (MAPE-K, SPIRE, PQC).
3. **Long-Horizon Autonomy via Async**: Push long-running tasks (compilation, extensive tests) to background jobs.
4. **Structural Fallback**: When a tool fails, fallback to alternative tools autonomously instead of asking the operator.

## GitMark RAG Memory Bank

- CLI at `scripts/gitmark_memory_bank.py`.
- Build: `python3 scripts/gitmark_memory_bank.py build --root /mnt/projects --out-dir /mnt/projects/.gitmark-memory --profile rag`
- Search: `python3 scripts/gitmark_memory_bank.py search "..."` or `python3 scripts/gitmark_memory_bank.py context "..." --limit 5`
- Rebuild after changing docs, skills, agent instructions, or runbooks.

## Codex MCP, Skills, And Agents Check

- Verify: `python3 scripts/verify_codex_environment.py`
- Fast: `python3 scripts/verify_codex_environment.py --skip-slow-mcp`
- Strict: `python3 scripts/verify_codex_environment.py --strict`
- GitHub MCP: `/mnt/projects/scripts/mcp/github_mcp_stdio.sh` (Docker, read-only, uses `gh auth token`)
- If GitHub MCP fails: `gh auth status` then `python3 scripts/verify_codex_environment.py --skip-slow-mcp --strict`

## NL VPN Safety Guard

- Treat `x-ui.service`/`xray` on NL (`89.125.1.107`) as production VPN infrastructure.
- No `systemctl stop`, `disable`, `mask`, `pkill`, or unit-file moves for x-ui/xray/ghost-access unless explicitly asked.
- Read-only NL evidence collection is always allowed. Service restarts require a current incident reason.
- Local health checks must NOT use third-party Clash/FlClashX ports `7890`/`7891`. Use first-party candidates: `10918`, `10818`, `10808`, `10809`, `10924`, `40467`, or explicit `VPN_SOCKS_PORT`.

## Hermes Config & Tools

### Config (profile x0tta6bl4)
- `max_turns=120` — больше шагов на сессию
- `terminal.timeout=600` — не сбрасывать долгие PQC тесты
- `compression.protect_last_n=30` — дольше хранить контекст
- `checkpoints.enabled=true` — можно /rollback
- `reasoning_effort=high`
- `max_spawn_depth=2`
- `mcp_discovery_timeout=10` — MCP успевают инициализироваться
- `goals.enabled=true` — /goal для приоритетов
- `webhooks.enabled=true` — внешние события

### MCP серверы (9 шт, 70+ инструментов)
- `github` (25 tools) — поиск кода, issues, PRs на GitHub
- `x0tta6bl4` (8 tools) — RAG memory bank, PQC smoke, NL evidence
- `playwright` (23 tools) — браузер: навигация, клики, скриншоты
- `desktop` (14 tools) — управление ПК: мышь, окна, скриншоты, shell
- `fetch` (3 tools) — парсинг веба без браузера (curl/wget)
- `think` (2 tools) — структурированное мышление Sequential Thinking
- `docker` (6 tools) — управление контейнерами
- `ollama` (3 tools) — CLI для локальных LLM
- `local-ai` (2 tools) — запуск LLM через llama-cpp-python (без ollama, без интернета)

### Thinking Framework (auto-applied)
Every request goes through an automatic technique selection based on task type:

| Task | Thinking Mode | Techniques |
|:-----|:--------------|:-----------|
| Code/Debug | Аналитическое + Critical | Chunking → OODA → Occam |
| Architecture | Системное + First Principles | SCAMPER → SWOT → Decision Tree |
| Hacks/Bypasses | Латеральное + Inversion | Reverse Brainstorming → Inversion |
| Admin/Diagnosis | Perceptual + Occam | OODA → Force-Field → Cynefin |
| Research | Дивергентное + Associative | 5W+H → Random Words |

Full framework at skill `x0tta6bl4-thinking-framework`.

### Проектные навыки (x0tta6bl4-*)
- `x0tta6bl4-pqc-test` — PQC smoke test
- `x0tta6bl4-large-file-split` — traps для split в этом monorepo
- `x0tta6bl4-evidence-gate` — NL VPN evidence gate
- `x0tta6bl4-context-saver` — шаблон сохранения контекста
- `x0tta6bl4-hacker-mode` — хакерский стиль: код > слова, обходы, zero-budget
- `x0tta6bl4-mission-support` — человечность, поддержка миссии
- `x0tta6bl4-thinking-framework` — **14 видов мышления + 30 техник, автовыбор под задачу**
- `x0tta6bl4-pc-optimization` — оптимизация ПК (lowntfs-3g, earlyoom)
- `csr-bt-keyboard-recovery` — восстановление BT-клавиатуры на CSR донгле

### Быстрые команды из terminal()
```bash
pqcsmoke        # PQC верификация (bash функция)
nlprobe         # NL VPN health
pyimport X.Y.Z  # тест импорта модуля
chromedbg       # Chrome с remote debugging
```

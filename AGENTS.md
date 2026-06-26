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

## Project Reality (CODEX.md v2.4)

This project has a formal operating manual at `/mnt/projects/CODEX.md`.
Load it before complex tasks. Key facts:

**Who we are:** Developer from Crimea under sanctions. Zero budget. Solo.
**What we build:** Self-healing mesh networking platform with PQC (ML-KEM + ML-DSA) and eBPF dataplane.
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

## Справочник навыков (skills)

> **Правило:** навыки — это специализированные процедуры. Если задача совпадает
> с триггером навыка — загрузи его. Не гадай, не импровизируй, не изобретай
> велосипед. Навыки содержат выверенные команды, traps и pitfalls.

### Какой навык когда загружать

#### 🔵 АРХИТЕКТУРА И АНАЛИЗ — загружать ПЕРВЫМ при входе в тему

| Навык | Когда | Зачем |
|:------|:------|:------|
| **x0tta6bl4-depin-architecture** | Любая архитектурная работа, ревью дизайна, planning | Даёт полную карту 11 слоёв, связи, границы. Без него — вслепую |
| **x0tta6bl4-architecture-audit** | Перед утверждением "компонент работает" | Проверяет что реально живо, а что мёртво (docker ps, systemctl, ps aux) |
| **x0tta6bl4-code-autopsy** | Сомневаешься — код реальный или заглушка? | Находит пустые returns, disabled middleware, stubs |
| **x0tta6bl4-project-analysis-snapshot** | Первичный вход в репозиторий | Быстрый срез: LOC, тесты, CI status |
| **x0tta6bl4-ztcr-audit** | Аудит безопасности, threat modeling | Zero-Trust + STRIDE + Chaos + Causal |
| **x0tta6bl4-user-preferences** | Любая сессия | Предпочтения пользователя, конфиг ПК, ограничения |

#### 🟢 КАЧЕСТВО КОДА И ТЕХДОЛГ

| Навык | Когда | Зачем |
|:------|:------|:------|
| **x0tta6bl4-tech-debt-elimination** | subprocess safety, `__init__.py`, `from __future__ import annotations`, allowlist sync, CVE patching | Выверенный 5-фазный процесс, traps (legacy shadow, starlette compat, swarm blocks) |
| **techdebt-bulk-refactoring** | Массовый рефакторинг (50+ файлов) | Параллельные агенты, git cleanup после массовых изменений |
| **repo-hygiene-audit** | Надо почистить репозиторий | Фейковые claims, мёртвые файлы, утекшие credentials, stale CI |
| **repo-cleanup-patterns** | После repo-hygiene-audit | Проверенные паттерны: Green Baseline, CodeQL dismiss, branch protection bypass |
| **repo-audit-extensions** | Расширенный аудит | Session-specific дополнения к repo-hygiene-audit |
| **x0tta6bl4-codeql-fix-workflow** | CodeQL алерт в CI | Анализ → классификация → фикс → suppress → dismiss. traps: diagnostic write_text, SHA256 false positives |
| **x0tta6bl4-security-automation** | Batch security audit | bandit, nmap, trufflehog — bootstrap под санкциями |
| **x0tta6bl4-security-hardening** | Batch security hardening | CodeQL triage, CI cleanup, parallel-agent conflict recovery |

#### 🟠 ИНФРАСТРУКТУРА И ДЕПЛОЙ

| Навык | Когда | Зачем |
|:------|:------|:------|
| **x0tta6bl4-mesh-local-deploy** | Надо поднять mesh локально | Docker Compose, SVID, SPIRE — 2 режима |
| **x0tta6bl4-remote-deploy** | Деплой на NL VPS (89.125.1.107) | SPIRE lifecycle, systemd, rsync, health, chaos |
| **x0tta6bl4-evidence-gate** | Проверить production readiness NL VPN | source audit, snapshot, decision, goal |
| **x0tta6bl4-browser-automation** | Навигация по веб-UI, админки, скриншоты | Playwright MCP + Desktop Commander (если нет npm) |
| **x0tta6bl4-desktop-commander** | Полный контроль ПК (мышь, клавиатура, окна) | Pure Python — работает без npm под санкциями |
| **x0tta6bl4-pc-optimization** | Оптимизация этого ПК (Athlon 3000G, 13GB) | ntfs3 → lowntfs-3g, earlyoom, BT keyboard, disk rescue |
| **disk-cleanup-workflow** | `/` заполнен на 100% | Когда du/find висят — точная последовательность |
| **csr-bt-keyboard-recovery** | BT клавиатура не коннектится | CSR донгл 0a12:0001, rotating MAC, SMP failure |

#### 🔴 МАШИННОЕ ОБУЧЕНИЕ

| Навык | Когда | Зачем |
|:------|:------|:------|
| **mesh-gnn-complete** | GNN, аномалии mesh, MAPE-K ML | Полный стек: autograd → GNN → MAPE-K → edge deployment |
| **micro-tensor-implementation** | Надо понять/поправить autograd engine | Pure NumPy, SAGEConv, gradient check |

#### 🟣 ПОИСК РАБОТЫ И ВИДИМОСТЬ

| Навык | Когда | Зачем |
|:------|:------|:------|
| **x0tta6bl4-job-search-strategy** | Стратегия поиска, portfolio, CV | Позиционирование AI Architect, этичный job search |
| **x0tta6bl4-job-hunting** | Автоматизация откликов | HH.ru + RemoteOK — проверенные селекторы, EPIPE trap |
| **hh-job-automation** | Только HH.ru | Playwright + browser_cookie3 |
| **web-market-research** | Исследование рынка вакансий | React SPA парсинг через браузер |
| **ai-recruitment-adversarial** | Защита от AI-скрининга резюме | Prompt injection в PDF, white-text, LLM-as-a-Judge evasion |

#### 🟡 ИНСТРУМЕНТЫ И ОБХОДЫ

| Навык | Когда | Зачем |
|:------|:------|:------|
| **x0tta6bl4-local-ai** | Нет интернета, ollama сломан | llama-cpp-python fallback, qwen2.5-coder 1.5b |
| **x0tta6bl4-python-mcp-pattern** | Нужен MCP сервер, нет npm | Чистый Python stdlib, stdin/stdout |
| **x0tta6bl4-hermes-config-diagnostics** | Hermes не работает (vision, compression, model) | Диагностика auxiliary provider, custom provider quirks |
| **mimo-device-fingerprint-spoof** | Xiaomi MimoCode 441 risk_control | Spoof machine-id, hostname, installation_id |

#### ⚪ МЕТА-НАВЫКИ

| Навык | Когда | Зачем |
|:------|:------|:------|
| **x0tta6bl4-thinking-framework** | **AUTO-APPLIED** — загружается автоматически | 14 видов мышления + 30 техник. Не загружать руками |
| **x0tta6bl4-loop-designer** | Надо спроектировать агентский цикл | Цель → верификация → советник → гейты → план. Портал Looper (ksimback) |
| **context-saver** | Контекст теряется, сессия длинная | Сохранить прогресс, восстановить после потери контекста |

### Алгоритм выбора навыка

```
1. Определи тип задачи (см. таблицу выше по цветам)
2. Загрузи базовый навык для этого типа (первый в группе)
3. Если задача сложная (5+ шагов) — загрузи x0tta6bl4-loop-designer
4. Если сомневаешься в реальности кода — x0tta6bl4-code-autopsy
5. Если сомневаешься в архитектуре — x0tta6bl4-depin-architecture
6. В конце сессии — сохрани новый навык через skill_manage
```

### Быстрые команды из terminal()
```bash
pqcsmoke        # PQC верификация (bash функция)
nlprobe         # NL VPN health
pyimport X.Y.Z  # тест импорта модуля
chromedbg       # Chrome с remote debugging
```

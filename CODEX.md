# x0tta6bl4 CODEX — AI Agent Operating Manual

> **Version:** 2.4  
> **Last updated:** 2026-06-24  
> **Purpose:** Фактологический слой для AI-агентов: что есть, чего нет, как не налажать.  
> **Не повторяет AGENTS.md** — здесь только рабочие инструкции с артефактами.

---

## 1. ИДЕНТИЧНОСТЬ

**Кто мы:** Solo-разработчик из Крыма под санкциями, zero budget.  
**Что строим:** Само-восстанавливающаяся mesh VPN с PQC (ML-KEM + ML-DSA) и eBPF dataplane.  
**Репозиторий:** `/mnt/projects` — Python monorepo.

---

## 2. ЧТО ЕСТЬ РЕАЛЬНО (RC1 Baseline)

| Компонент | Статус | Проверено | Доказательство |
|-----------|--------|-----------|---------------|
| **PQC стек** | ✅ Verified | 2026-06-15 | ML-KEM-768 + ML-DSA-65, `docs/verification/HYBRID_TLS_VALIDATION_LATEST.md` |
| **XDP/eBPF dataplane** | ✅ Attached | 2026-06-15 | 142k PPS TX, 49k PPS RX на r8169, `docs/verification/xdp-live-attach-*` |
| **MAPE-K self-healing** | ✅ Local loop | 2026-06-15 | monitor→execute→verify, <20s MTTD, ~3min MTTR (локально) |
| **SPIFFE/SPIRE mTLS** | ✅ Integrated | 2026-06-15 | документировано, есть тесты |
| **Ghost Access transport** | ⚡ Experimental | 2026-06-15 | STL-упаковка, требует полевой валидации |
| **x402 Payment** | ✅ Deployed | 2026-06-15 | USDC на Base mainnet, HTTP 402 enforced |
| **API gateway** | ✅ Deployed | 2026-06-15 | health: HTTP 200, 8 сервисов, ~25ms latency |
| **Real-readiness gate** | ✅ 70/70 checks | 2026-06-15 | `scripts/ops/check_real_readiness.py --json` |

### VPS Production Evidence (2026-06-15)
- VPS: `89.125.1.107:8000/health` → HTTP 200, v3.4.0
- x402 Paid API: `89.125.1.107:8120`
- Open5GS: `89.125.1.107:18080/health` → HTTP 200
- Agent earnings: AgentPact, x402 Directory, Income Watch запущены

---

## 3. ЧЕГО НЕТ (НЕ ЗАЯВЛЯТЬ В КОДЕ/ДОКАХ)

| Утверждение | Статус |
|-------------|--------|
| BGP/OSPF/MPLS | ❌ Не реализовано |
| GOST криптография | ❌ Не реализовано |
| 5G standalone | ❌ Не реализовано |
| SNMP агент | ❌ Не реализовано |
| 99.97% uptime | ❌ Нет доказательств |
| 153k ops/sec | ❌ Устаревшие цифры |
| Production customer traffic | ❌ Кошелёк 0 USDC, платящих клиентов нет |
| Compliance сертификация | ❌ Нет pentest |

**Правило:** Любое из этих утверждений требует **прямой ссылки на текущий артефакт**. Наличие кода ≠ полевой валидации.

---

## 4. АРХИТЕКТУРА (СЛОИ)

Снизу вверх:

| Слой | Компоненты |
|------|-----------|
| **Kernel/Dataplane** | eBPF/XDP, AF_XDP rings, DPI bypass |
| **Transport** | PQC Hybrid TLS 1.3 (ML-KEM + ML-DSA), SPIRE mTLS |
| **Mesh** | DHT discovery, CRDT sync, First-party VPN, WireGuard |
| **Control** | MAPE-K (self-healing), EventBus, SafeActuator |
| **API** | FastAPI, MaaS (Mesh-as-a-Service), REST/gRPC |
| **Payment** | x402, USDC Base mainnet, Stripe webhooks |

---

## 5. КОДОВАЯ БАЗА

**Язык:** Python 3.12  
**Пакетный менеджер:** `uv` (предпочтительно), `pip` (fallback)  
**Dependencies:** 72 (было 342, почищено в PR #127)  
**Венв:** `/mnt/projects/.venv/`

> **Точные счётчики файлов** — запускай `pygount` или `cloc` при необходимости. Числа в этом доке были бы stale через неделю.  
> Пример: `pygount --format=summary src/ tests/`

---

## 6. РАБОЧИЕ ПРОЦЕДУРЫ (агентские)

### Dependency install
```bash
# Всегда через uv:
uv sync

# Если uv нет:
pip install -r requirements.txt

# Если падает — указать fallback:
pip install -r requirements.txt --no-build-isolation
```

### Git с branch protection
```bash
# Не git push origin ветку напрямую — main защищён.
# Формат-патч:
git format-patch HEAD~N --stdout > /tmp/fix.patch
git checkout -b fix/xxx origin/main
git am --signoff < /tmp/fix.patch
git push origin fix/xxx
gh pr create --base main --head fix/xxx --fill
```

### Что делать когда команда упала
```
1. Попробовать с флагом --no-build-isolation / --skip-git-check
2. Попробовать fallback версию (uv → pip)
3. Если всё те же ошибки — сказать пользователю точный exit code + последние 10 строк stderr
```

### Quality gates (обязательные перед "готово")
| Gate | Команда | Критерий |
|------|---------|----------|
| **READINESS** | `python3 scripts/ops/check_real_readiness.py --skip-git-check --json` | `REAL_READINESS_READY` |
| **TESTS** | `python3 -m pytest tests/unit/direct/... -q --no-cov` | exit code 0 |
| **SYNTAX** | `python3 -m py_compile src/changed_file.py` | exit code 0 |
| **BROKEN** | `git status --porcelain` | нет конфликтов (`UU`) |

> Если gate не пройден — **не говорить «готово»**. Либо починить, либо сказать что заблокировано и почему.

---

## 7. ДОКАЗАТЕЛЬСТВЕННАЯ ДИСЦИПЛИНА

- **Не утверждать** production/customer/dataplane readiness без артефакта
- Readiness = `check_real_readiness.py --json` → `REAL_READINESS_READY`
- Локальный `healing.verified` ≠ production readiness
- Любое числовое утверждение (PPS, uptime, handshake latency) — с ссылкой на артефакт

### Self-verification hook (ОБЯЗАТЕЛЬНО после каждого действия)

После ЛЮБОГО изменения кода/доков/config:

```
1. git diff --stat                   # точно то что хотел?
2. python3 -m py_compile changed.py  # синтаксис
3. python3 scripts/ops/check_real_readiness.py --skip-git-check --json  # readiness не сломал?
4. git status --porcelain            # нет мусора?

Если хоть один пункт упал:
- git checkout -- . (откат)
- найти причину
- повторить
```

> **Исключение:** черновики (.hermes/plans/*, временные заметки) — verify не требуется.

---

## 8. KNOWN TRAPS

| Ситуация | Что делать |
|----------|-----------|
| `pqcsmoke` alias не найден | Не установлен. Вызывать `python3 scripts/benchmark_pqc.py` |
| NTFS dirty flag при монтировании | `lowntfs-3g`, kernel ntfs3 не принимает dirty том |
| sing-box TUN заблокировал SaaS | SOCKS5 :10818 в обход, или `pkill sing-box` |
| `pip install` падает на native-extension | `pip install --no-build-isolation` или `uv sync` |
| git push rejected (protected branch) | format-patch → новая ветка → gh pr |
| pytest падает на cov/plugins | `python3 -m pytest ... -q --no-cov -p no:cov -p no:cacheprovider` |
| Проверка `check_real_readiness.py` | Если нет скрипта — readiness не доказана, не утверждать |
| Не уверен в факте | Не выдавать. `python3 scripts/gitmark_memory_bank.py search "тема"` |

---

## 9. QUICK COMMANDS

```bash
cd /mnt/projects
source .venv/bin/activate

# тесты
python3 -m pytest tests/unit/security/test_dependency_security_pins_unit.py -q --no-cov

# readiness
python3 scripts/ops/check_real_readiness.py --skip-git-check --json

# PQC smoke
python3 scripts/benchmark_pqc.py

# gitmark memory bank
python3 scripts/gitmark_memory_bank.py build --root /mnt/projects --out-dir /mnt/projects/.gitmark-memory --profile rag

# NL VPN health
curl -s http://89.125.1.107:8000/health
```

---

## 10. ССЫЛКИ (читай в этом порядке при загрузке контекста)

1. **CODEX.md** ← этот файл. Содержит сжатую фактологию остальных доков
2. **AGENTS.md** — коммуникация, workflow, Hermes config
3. **GEMINI.md** — readiness gate safety (для всех агентов, не только Gemini)
4. **SECURITY.md** — security policy
5. `docs/architecture/CURRENT_AUTONOMOUS_MESH_REALITY_MAP.json`
6. `docs/architecture/CURRENT_CROSS_PLANE_EVIDENCE_MAP.json`

---

## 11. ЭКСТРЕННЫЕ ПРОЦЕДУРЫ

### Когда контекст сжимается или теряешь нить

| Ситуация | Действие |
|----------|----------|
| Контекст сжат, забыл что делал | Перечитать CODEX.md + AGENTS.md. `session_search("последняя задача")` |
| Зациклился, выдаёшь одно и то же | Остановиться. `python3 scripts/gitmark_memory_bank.py context "recent changes" --limit 3`. Потом `git diff --stat` чтобы вспомнить что менял |
| Команда не работает 3 попытки подряд | НЕ пытаться 4-й. Сохранить контекст (см. ниже). Сказать пользователю точный exit code |
| Не уверен в факте | Не гадать. `python3 scripts/gitmark_memory_bank.py search "тема"`. Если ничего — спросить «проверь» |

### Контекстный handoff (при сжатии >80%, перед перерывом, или по команде «сохрани»)

```markdown
# Session Continuation — YYYY-MM-DD

## Current Branch
`git branch --show-current`

## Files Modified
```
git diff --stat
```

## In-Progress Work
- Task: что делал, где, следующий шаг

## Blockers
- Блокер и почему

## Key Decisions
- Что решил и почему
```

Сохранять в `.hermes/plans/YYYY-MM-DD_taskname.md`.

---

## 12. СОВМЕСТИМОСТЬ С АГЕНТАМИ

| Агент | Уровень | MCP | Ограничения |
|-------|---------|-----|-------------|
| **Hermes** | 🟢 Полная | 9 серверов | CODEX.md читает, MCP использует, полный контроль |
| **Codex** | 🟡 Частичная | Нет | Команды через shell. Не может делать browser/desktop |
| **Gemini** | 🟡 Частичная | ACP мёртв | Только shell. Не может читать MCP-инструменты |
| **Cursor** | 🔴 Ограниченная | Нет | CODEX.md читает, но MCP/skills недоступны |
| **Windsurf** | ⚫ Не тестировался | Неизвестно | Предполагать что CODEX.md читает, остальное — нет |

> **Правило:** Если агент не имеет MCP — все процедуры, требующие browser/desktop, недоступны. Агент должен явно сказать «у меня нет доступа к браузеру, нужно через shell» вместо того чтобы делать вид что работает.

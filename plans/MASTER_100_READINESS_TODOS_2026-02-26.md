# MASTER TODOs — доведение до максимальной готовности (target 100%)

Дата: 2026-02-26  
Владелец: `codex-implementer`  
Режим: безопасные, пошаговые изменения с обязательной верификацией.

## 0) Definition of Done (DoD) для уровня “готово”

- [ ] `main/develop` без незавершённых конфликтов и без schema drift.
- [x] `alembic upgrade head` проходит на чистой БД без ручных правок.
- [ ] Все P0/P1 тестовые сьюты зелёные в локали и CI.
- [ ] Покрыты критические API-контракты негативными кейсами.
- [ ] Секреты/политики безопасности валидируются на старте.
- [ ] Наблюдаемость (метрики, логи, трейсы) покрывает критический путь.
- [ ] Есть rollback/runbook на релиз и миграции.
- [ ] Выполнен dry-run релиза + smoke в окружении pre-prod.

## 1) P0 — критические задачи (блокеры релизной готовности)

- [ ] Закрыть все flaky тесты в `tests/api` и `tests/unit/api` с воспроизводимостью.
- [x] Зафиксировать стабильный “golden smoke” набор и запускать перед каждым merge.
- [ ] Убрать оставшиеся расхождения между ORM и Alembic (автопроверка в CI).
- [ ] Проверить все новые поля в API-моделях на совместимость backward/forward.
- [ ] Довести idempotency для create/rent/release/refund критичных endpoint’ов.
- [ ] Привести ошибки API к единому формату (`status`, `detail`, код, trace id).
- [ ] Гарантировать типовую совместимость `id` (str/int) в auth/VPN/MaaS путях.
- [ ] Закрыть угрозу “тихого skip” в диагностических тестах (ловить только expected exceptions).
- [ ] Провести полный секрет-аудит env переменных и fallback поведения.
- [ ] Проверить запрет опасных default-конфигов в production режиме.

## 2) P0 — база данных, миграции, данные

- [ ] Проверить полный bootstrap chain на SQLite и PostgreSQL.
- [ ] Проверить downgrade-стратегию для последних ревизий (non-destructive где нужно).
- [x] Добавить smoke-проверку: ORM tables == DB tables (исключая системные).
- [ ] Проверить nullable/non-nullable переходы на реальных старых слепках.
- [ ] Зафиксировать политику миграций для “already exists” (idempotent migration style).
- [ ] Добавить проверку индексов/unique ограничений для критичных таблиц.
- [ ] Подготовить runbook аварийного rollback миграции.

## 3) P0 — API-компоненты (функциональная готовность)

- [ ] MaaS Marketplace: согласовать ценообразование, фильтры и escrow-расчёт.
- [x] MaaS Telemetry: подтвердить контракт heartbeat и совместимость legacy/modular.
- [x] MaaS Nodes: проверить auto-release escrow и статусные переходы node lifecycle.
- [x] MaaS Governance: проверить edge-cases quorum/finality/execute.
- [ ] MaaS Playbooks: проверить подписи/сроки/ack жизненный цикл.
- [ ] MaaS Billing: проверить mapping mesh<->node и критические ветки MAPE-K событий.
- [ ] VPN API: унифицировать доступ к user_id и проверить authz boundary.
- [ ] Auth API: проверить scope enforcement и регрессию permissive путей.

## 4) P1 — безопасность и комплаенс

- [ ] Полный проход SAST/dep-аудита для Python/JS зависимостей.
- [ ] Проверить отсутствие чувствительных данных в логах и audit payload.
- [ ] Проверить rate limiting для дорогих endpoint’ов.
- [ ] Проверить CSRF/CORS настройки и реальные trusted origins.
- [ ] Проверить mTLS/PKI ветки и поведение при частичном отказе.
- [ ] Включить проверки заголовков безопасности на gateway уровне.
- [ ] Проверить права оператор/admin/user на всех критических endpoint’ах.

## 5) P1 — надёжность, отказоустойчивость, восстановление

- [ ] Добавить сценарии отказа Redis/DB и проверить graceful degradation.
- [ ] Проверить circuit-breaker поведение на внешних интеграциях.
- [ ] Проверить таймауты и retry policy для внешних клиентов.
- [ ] Провести fault injection для ключевых бизнес-потоков.
- [ ] Проверить корректность shutdown/startup hooks и cleanup ресурсов.
- [ ] Подготовить и прогнать DR-сценарий восстановления БД из backup.

## 6) P1 — производительность

- [ ] Зафиксировать baseline latency/throughput по критическим endpoint’ам.
- [ ] Поставить SLO цели (`p95`, `p99`, error rate) и алерты.
- [ ] Устранить горячие точки SQL (N+1/без индексов/долгие запросы).
- [ ] Проверить memory profile на долгих прогонах API.
- [ ] Прогнать нагрузочные сценарии на Marketplace/Telemetry/Nodes.

## 7) P1 — тестовая стратегия до релизного качества

- [x] Сформировать обязательный pre-merge набор тестов (быстрый).
- [x] Сформировать nightly набор (полный интеграционный).
- [ ] Вынести самые долгие тесты в отдельный schedule/parallel lane.
- [ ] Добавить regression-тесты для последних инцидентов и багфиксов.
- [ ] Включить проверку на неиспользуемые/мертвые тестовые фикстуры.
- [ ] Проверить, что все тесты deterministic и не зависят от локального мусора.

## 8) P1 — observability и операционная эксплуатация

- [ ] Привести логи к единому JSON-формату для критичных сервисов.
- [ ] Добавить correlation/request id в API и фоновые задачи.
- [ ] Проверить полноту метрик Prometheus по компонентам MaaS/VPN.
- [ ] Довести Grafana dashboard до операционного минимума on-call.
- [ ] Настроить алерты на SLO breach и критические бизнес-ошибки.
- [ ] Подготовить runbooks на частые инциденты.

## 9) P1 — CI/CD и release engineering

- [ ] Зафиксировать pipeline stages: lint, type, unit, integration, smoke.
- [ ] Добавить gate на миграции (bootstrap check перед merge).
- [ ] Проверить build reproducibility Docker образов.
- [ ] Проверить Helm chart install/upgrade/uninstall сценарии.
- [ ] Провести dry-run релиза с отметкой контрольных точек.
- [ ] Проверить canary rollout + быстрый rollback.

## 10) P2 — документация и DX

- [ ] Обновить архитектурную схему по фактическому коду.
- [ ] Обновить API docs с новыми полями/кодами ошибок.
- [ ] Добавить “known limitations” раздел для текущей версии.
- [ ] Обновить onboarding для разработчиков и тестовый quickstart.
- [ ] Добавить checklist релиз-менеджера “go/no-go”.

## 11) Порядок выполнения (execution queue)

- [ ] Шаг 1: закрыть P0 по API/DB/тестам.
- [ ] Шаг 2: закрыть P1 по security/reliability/perf.
- [ ] Шаг 3: закрыть P1 по observability/CI-CD/release.
- [ ] Шаг 4: закрыть P2 по документации и DX.
- [ ] Шаг 5: провести финальный `go/no-go` аудит и зафиксировать релизный отчёт.

## 12) Контрольные метрики “готовности”

- [x] API smoke pass rate: 100%.
- [ ] Unit pass rate: 100%.
- [x] Migration bootstrap success rate: 100%.

## 13) Progress Log (2026-02-26)

- [x] Добавлен и зафиксирован pre-merge gate: `scripts/golden_smoke_premerge.sh` (`quick|full`).
- [x] Починена bootstrap миграция `1b073048a58f` (idempotent guard для `ip_address`/index).
- [x] Убран синтаксический дефект в `src/api/maas_telemetry.py`, восстановлен heartbeat flow.
- [x] Сделан heartbeat test fix для самодостаточности (`test_heartbeat_auto_releases_escrow`).
- [x] `quick` smoke: PASS (`fail: 0`).
- [x] `full` smoke: PASS (`fail: 0`, 20/20 шагов после расширения reliability/security + auth).
- [x] `quick` smoke усилен reliability/security шагами (`connection_retry`, `redis_sentinel`, `vpn_security_unit`, `resilience_advanced`) и повторно PASS (`fail: 0`, 10/10 шагов).
- [x] Устранен flaky timeout в Geneva security тесте через lazy imports в `scripts/run_geneva_poc.py`.
- [x] Добавлен nightly CI workflow для `full` smoke (`.github/workflows/golden-smoke-nightly.yml`).
- [x] `quick` smoke workflow запускается и на `pull_request`, и на `push` в `main/develop`.
- [x] Зачищен dependency baseline для security gate: из `requirements*` убраны `diskcache` и `llama_cpp_python` (источник транзитивного CVE), `nltk` обновлён до `3.9.3`, локальный LLM вынесен в optional extra `local-llm`.
- [x] В `quick/full` gate добавлена проверка синхронизации `requirements.txt` ↔ `requirements.lock`; устранено фактическое рассогласование по `click`, `quick` снова PASS (`fail: 0`, 11/11 шагов).
- [x] Повторный `full` smoke после добавления lock-sync шага: PASS (`fail: 0`, 22/22 шагов).
- [x] Nightly workflow разделён на parallel lanes (`full-core`, `full-heavy`) с агрегирующим gate job, чтобы сократить wall-clock и сохранить blocking-семантику.
- [x] Локально подтверждён профиль `full-core`: PASS (`fail: 0`, 18/18 шагов); `full-heavy` набор валиден (`116 tests collected`) и отдан в nightly lane.
- [x] В nightly добавлены артефакты таймингов по lane и итоговый summary (`duration_seconds`, `start/end UTC`) для отслеживания деградаций по времени.
- [x] В nightly включены duration guardrails (warn/hard thresholds) для `full-core` и `full-heavy`; критичная деградация по времени теперь блокирует nightly gate.
- [ ] Regression reopen rate: < 2%.
- [ ] Critical incident MTTR: целевой < 30 минут.
- [ ] Release rollback time: целевой < 10 минут.

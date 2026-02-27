# Golden Pre-Merge Smoke

Дата: 2026-02-26

## Цель

Единый pre-merge gate для критичных MaaS/VPN путей, который проверяет:

- bootstrap миграций на чистой БД;
- соответствие ORM-схемы и фактической DB-схемы;
- синхронизацию `requirements.txt` и `requirements.lock`;
- минимальный быстрый набор API/интеграционных тестов (`quick`);
- расширенный набор регрессионных тестов (`full`).

Скрипт: `scripts/golden_smoke_premerge.sh`

## Профили

- `quick`: обязательный pre-merge прогон (быстрый gate).
- `full`: полный прогон (объединяет `full-core` + `full-heavy`).
- `full-core`: основной nightly lane (все критичные наборы кроме самых долгих governance/marketplace тестов).
- `full-heavy`: длинный nightly lane (`marketplace`, `escrow`, `governance`, `governance_edge`).

### Состав профилей (кратко)

- `quick`:
  - миграции + schema parity + dependency lock sync;
  - marketplace-модульный smoke;
  - reliability/security smoke (`connection_retry`, `redis_sentinel`, `resilience_advanced`, `vpn_security_unit`);
  - API smoke (`maas_telemetry`, `maas_nodes heartbeat`, `vpn_api`).
- `full`:
  - всё из `quick` + `full-core` + `full-heavy`;
  - расширенные reliability/security наборы (`graceful_shutdown`, `maas_security_unit`);
  - API/regression наборы (`mesh_endpoints`, `playbooks`, `marketplace`, `escrow`, `governance`, `governance_edge`, `maas_auth`, `analytics`, `mesh_fl_integration`).

## Запуск

```bash
# Быстрый pre-merge gate
scripts/golden_smoke_premerge.sh quick

# Полный smoke gate
scripts/golden_smoke_premerge.sh full

# Nightly core/heavy split lanes
scripts/golden_smoke_premerge.sh full-core
scripts/golden_smoke_premerge.sh full-heavy
```

Опционально можно увеличить таймауты:

```bash
PYTEST_TIMEOUT_SECONDS=2400 ALEMBIC_TIMEOUT_SECONDS=600 scripts/golden_smoke_premerge.sh full
```

## Критерии прохождения

Скрипт завершает работу с `exit 0`, если:

- `fail: 0` в итоговом summary;
- `Alembic bootstrap to head` = PASS;
- `Schema parity check` = PASS;
- `Requirements lock sync check` = PASS;
- все тестовые шаги профиля = PASS.

Любой `FAIL` в summary считается merge blocker.

## Разбор типовых падений

- `duplicate column/index` в Alembic:
  - миграция неидемпотентна, нужно добавить guard через инспектор схемы.
- `missing_tables` в parity:
  - ORM/миграции рассинхронизированы; чинить ревизию или модель.
- падение тестового шага:
  - сначала воспроизвести этот конкретный файл локально;
  - потом возвращаться к полному smoke.

## Текущий статус (на 2026-02-27)

- `quick`: PASS (`pass: 11`, `fail: 0`) после добавления `Requirements lock sync check`.
- `full`: PASS (`pass: 22`, `fail: 0`) после добавления `Requirements lock sync check`.
- `full-core`: PASS (`pass: 18`, `fail: 0`) на локальном прогоне после split.
- `full-heavy`: валидирован набор lane (`116 tests collected` в `--collect-only`), выполняется в nightly CI.

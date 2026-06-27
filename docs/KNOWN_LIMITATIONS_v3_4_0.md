# Known Limitations — v3.4.0

**Дата:** `2026-03-05`  
**Применимость:** runtime API, mesh-operator, release workflow

## 1) API schema vs runtime error envelope

- **Ограничение:** часть OpenAPI-схем (`ErrorResponse`) отражает legacy-формат, тогда как gateway runtime использует unified error envelope: `status/detail/code/trace_id`.
- **Влияние:** клиентам, строго полагающимся только на schema-level error models, нужна адаптация парсинга ошибок.
- **Workaround:** ориентироваться на фактический runtime контракт из `src/core/api_error_handlers.py`; использовать `code` + `trace_id` для диагностики.

## 2) MAAS light mode feature surface

- **Ограничение:** при `MAAS_LIGHT_MODE=true` часть роутеров не регистрируется (`nodes`, `telemetry`, `vpn`, `users`, `swarm`, `ledger`, `vision`).
- **Влияние:** endpoint parity между средами может отличаться.
- **Workaround:** для интеграционных проверок включать full mode (`MAAS_LIGHT_MODE=false`) и фиксировать режим в тестовых профилях.

## 3) Mesh-operator image provenance in isolated environments

- **Ограничение:** публичный pull `x0tta6bl4/mesh-operator:3.4.0` может быть недоступен в отдельных окружениях; pipeline использует fallback/local build стратегию.
- **Влияние:** локальные и CI прогоны зависят от доступности Docker daemon и возможности локальной сборки.
- **Workaround:** использовать `scripts/ops/ensure_mesh_operator_image.sh` и fallback manager build path.

## 4) Canary/rollback validation scope

- **Ограничение:** текущий canary gate (`mesh_operator_canary_rollback_e2e.sh`) валидирован на `kind` и Helm release scope, не на production traffic shaping.
- **Влияние:** rollback SLA в `kind` не равен автоматически production SLA.
- **Workaround:** использовать текущий gate как pre-prod quality bar и отдельно мерить rollback в целевом pre-prod/prod окружении.

## 5) Readiness business metrics still require production history

- **Ограничение:** метрики `Regression reopen rate`, `Critical incident MTTR`, `Release rollback time` в master plan требуют накопленной эксплуатационной статистики.
- **Влияние:** эти KPI нельзя закрыть только локальными тестами/CI.
- **Workaround:** собирать статистику через incident/release telemetry и пересчитывать KPI на регулярной cadence.

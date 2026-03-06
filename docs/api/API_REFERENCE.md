# API Reference

**Версия:** `3.4.0`  
**Дата:** `2026-03-05`  
**Базовый URL:** `http://localhost:8000`

## Источники

- `docs/api/openapi.json` (164 path operations)
- `src/core/app.py` (фактическая регистрация роутеров и middleware)
- `src/core/api_error_handlers.py` (единый error envelope)

## 1) Карта API поверхностей

- `GET /health`, `/health/live`, `/health/ready`, `/health/detailed`, `/metrics`
- `api/v1/maas/*` — MaaS runtime: auth, nodes, telemetry, marketplace, governance, billing, playbooks, supply-chain.
- `api/v1/users/*` — пользовательские endpoint’ы.
- `api/v1/billing/*` — billing integration API.
- `api/v3/swarm/*` — orchestration API.
- `/edge/*` — edge execution and node/task control.
- `/events/*` — event-sourcing commands/queries/projections.
- `/vpn/*`, `/mesh/*`, `/pqc/status` — network and VPN layer endpoints.

## 2) Глобальный контракт ответов

### Response headers

На всех ответах шлюз выставляет:

- `X-Trace-ID`
- `X-Request-ID`
- `X-Correlation-ID`

### Единый error envelope (v3.4.0)

При ошибках gateway возвращает унифицированный payload:

```json
{
  "status": "error",
  "detail": "...",
  "code": "VALIDATION_ERROR | HTTP_<status> | INTERNAL_ERROR | <domain_code>",
  "trace_id": "..."
}
```

Где:

- `code=VALIDATION_ERROR` для `422`.
- `code=HTTP_<status>` для стандартных `HTTPException`.
- `code=INTERNAL_ERROR` для необработанных `500`.
- Если endpoint передаёт `detail.code`, используется explicit domain code.

## 3) Обновлённые поля в ключевых ответах (v3.4.0)

### Marketplace

`ListingResponse` включает:

- `price_token_per_hour`
- `currency` (`USD`/`X0T`)
- `trust_score`

### Billing

`BillingWebhookResponse` включает:

- `plan_before`
- `plan_after`
- `requests_limit`
- `idempotent_replay`

`InvoiceResponse` включает:

- `stripe_session_id`
- `period_start`
- `period_end`

### Mesh lifecycle and telemetry

`MeshStatusResponse` включает:

- `peers`
- `health_score`
- `pqc_enabled`
- `traffic_profile`

`MeshMetricsResponse` агрегирует:

- `consciousness`
- `mape_k`
- `network`

### Playbooks / Supply-chain

`PlaybookCreateResponse` включает:

- `algorithm`
- `expires_at`

`SBOMResponse` включает:

- `attestation`
- `pqc_signature`
- `checksum_sha256`

## 4) Прикладные заметки совместимости

- В критичных MaaS/VPN путях поддержана `str/int` совместимость `user_id` (mixed-id clients).
- Для production security-профиля действует fail-closed политика для authz и секретов.

## 5) OpenAPI артефакты

- `docs/api/openapi.json`
- `docs/api/openapi.yaml`
- `docs/api/swagger.html`
- `docs/api/index.html`

Для полного перечня endpoint’ов и схем используйте `openapi.json` как canonical machine-readable spec.

# x0tta6bl4 Fix Report (Post-Gemini)

_Дата: 2026-03-01_

## 1) Что исправлено

### Security и API-контракты
- `src/api/maas_agent_mesh.py`
  - Добавлена обязательная аутентификация (`Depends(get_current_user_from_maas)`) для endpoint-ов mesh API.
- `src/api/maas_security.py`
  - Убрана обрезка PQC-подписи: теперь хранится/возвращается полный `ML-DSA` signature hex.
  - Усилена верификация подписи токена (нормализация signature + безопасный fallback).
- `src/api/maas_playbooks.py`
  - Убрана fail-open логика: неизвестные алгоритмы подписи теперь отклоняются.
  - Валидация подписи разделена по алгоритмам:
    - `HMAC*` -> HMAC verify path.
    - `ML-DSA*` -> strict PQC verify path (без fallback на HMAC).
  - Усилен ack-контракт: проверка существования playbook, expiry, target node и статуса ack.
- `src/api/maas_auth.py`
  - Исправлен OIDC client secret wiring: используется `OIDC_CLIENT_SECRET`, а не `audience`.
  - `require_permission`/`require_mesh_access` унифицированы под `str | MeshPermission`.
  - Добавлен compatibility слой для legacy scopes (policy/audit и др.) без ломки старых маршрутов.
- `src/core/rbac.py`
  - Добавлены VPN-permissions (`vpn:config`, `vpn:status`, `vpn:admin`) в enum и role defaults.
- `src/api/vpn.py`
  - Убран `sys.path` hack и хрупкие прямые импорты `from database import ...`.
  - Введён безопасный adapter к legacy `database.py` для ZKP-path.
- `src/api/maas_marketplace.py`
  - Закрыт TOCTOU в аренде: повторная проверка `owner/status` по DB перед переходом в escrow.
  - Усилен контроль release/refund: повторная проверка `renter_id` по DB (не доверяем cache-only).
  - Усилена валидация `Idempotency-Key` (длина, допустимые символы).
  - Запрещён cancel listing в активном rental state (`escrow`/`rented`).
  - Добавлен DB re-check в `cancel_listing` для защиты от stale/подменённого cache.
- `src/api/maas_nodes.py`
  - Усилена валидация enroll token:
    - проверка наличия `join_token`,
    - проверка expiry (`join_token_expires_at`),
    - compare через `hmac.compare_digest`.
  - Усилен approve-path: проверка существования mesh и валидности join token до перевода node в `approved` (без преждевременного commit).
  - Исправлена модель прав mesh owner (добавлены node/acl/telemetry management scopes).
  - Добавлено расширение alias-permissions (`view<->read`, `update<->write`) для корректной проверки RBAC.

### Кодовая стабильность
- `src/agents/kimi_healing_agent.py`
  - Невалидное действие playbook `isolate_node` заменено на `ban_peer`.
  - Добавлен allowlist/безопасный fallback для неизвестных действий.
- `src/core/parl_mapek_integration.py`
  - Исправлена генерация healing plan и fallback при ошибках агента.
- `src/network/obfuscation/http_steganography.py`
  - Переписан encode/decode путь: URL-safe base64, лимиты payload, безопасные decode-fail сценарии.

### Документы и позиционирование
- `STATUS_REALITY.md`
  - Переписан в evidence-based формате.
- `docs/GTM_LAUNCH_READY_REPORT_2026.md`
  - Смягчены/нормализованы неподтверждаемые технические утверждения.
- `docs/TRUST_AND_SECURITY_WHITEPAPER.md`
  - Синхронизированы claims с фактическим состоянием кода.

## 2) Добавленные/обновлённые тесты

- `tests/unit/api/test_maas_agent_mesh_unit.py`
  - Обновлены auth overrides, добавлен явный 401-path.
- `tests/unit/agents/test_kimi_healing_agent_unit.py`
  - Проверки action allowlist/fallback.
- `tests/unit/network/obfuscation/test_http_steganography_unit.py`
  - Проверки safe encode/decode и invalid input handling.
- `tests/api/test_maas_playbooks.py`
  - Добавлены регрессионные проверки на неизвестный/подменённый алгоритм подписи.
- `tests/api/test_maas_marketplace.py`
  - Добавлены проверки:
    - stale-cache rent protection,
    - DB renter re-check на release/refund,
    - stale-cache cancel protection,
    - validation `Idempotency-Key`.
- `tests/api/test_maas_nodes.py`
  - Добавлены проверки alias expansion и owner node-management permissions.
  - Добавлен safety-тест на `approve_node`: при истёкшем token статус node не коммитится в `approved`.

## 3) Проверка результатов

Ключевые прогоны, выполненные после правок:

1. `pytest --no-cov -q tests/unit/api/test_maas_security_unit.py tests/api/test_maas_playbooks.py tests/api/test_maas_auth.py tests/api/test_vpn_api.py`
   - Результат: `156 passed`

2. `pytest --no-cov -q tests/api/test_maas_auth.py tests/api/test_maas_playbooks.py tests/api/test_maas_policies.py tests/api/test_maas_billing.py tests/api/test_maas_marketplace.py tests/api/test_vpn_api.py`
   - Результат: `316 passed`

3. `pytest --no-cov -q tests/api/test_maas_marketplace.py tests/api/test_maas_nodes.py`
   - Результат: `160 passed`

4. `python3 -m py_compile` для всех затронутых модулей
   - Результат: без ошибок.

5. `pytest --no-cov -q tests/api/test_maas_auth.py tests/api/test_maas_playbooks.py tests/api/test_maas_policies.py tests/api/test_maas_billing.py tests/api/test_maas_marketplace.py tests/api/test_vpn_api.py tests/api/test_maas_nodes.py`
   - Результат: `420 passed`

## 4) Итог

После блока правок post-Gemini устранены критичные security-contract несоответствия в `maas_security`, `maas_playbooks`, `maas_auth`, `maas_marketplace`, `maas_nodes` и `vpn`, синхронизированы claims в документах и добавлены регрессионные тесты для предотвращения повторного появления этих классов ошибок.

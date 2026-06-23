# 📋 Исчерпывающий План Устранения Технического Долга x0tta6bl4

**Дата создания:** 2026-02-02  
**Версия проекта:** 3.2.0  
**Автор анализа:** Технический аудит  
**Методология:** Code Review + Dependency Analysis + Architecture Assessment + Security Audit

---

## 📊 Executive Summary

### Текущее состояние проекта

| Метрика | Значение | Статус |
|---------|----------|--------|
| **Покрытие тестами** | 1.24% (549/44,327 строк) | 🔴 КРИТИЧНО |
| **Уязвимости в зависимостях** | 15+ CVE | 🔴 КРИТИЧНО |
| **Устаревшие пакеты** | 48+ | 🟡 ТРЕБУЕТ ВНИМАНИЯ |
| **Архитектурные дефекты** | 7 (3 исправлены) | 🟡 В РАБОТЕ |
| **Дублирование кода** | Умеренное | 🟢 ПРИЕМЛЕМО |
| **Документация** | Обширная, но неактуальная | 🟡 ТРЕБУЕТ ОБНОВЛЕНИЯ |

### Общая оценка технического долга

**Объём технического долга:** ~400-500 человеко-часов  
**Критический долг (блокирующий):** ~80-100 человеко-часов  
**Рекомендуемый срок устранения:** 3-4 месяца (при 1 разработчике)

---

## 🔥 ПРИОРИТЕТНЫЙ БЛОК: УСТРАНЕНИЕ КРИТИЧЕСКИХ ЗАГЛУШЕК (P0)

### P0.1 Post-Quantum Cryptography (PQC/eBPF)
- **Проблема:** xdp_pqc_verify.c — заглушка, нет реальной ML-DSA-65/AES-GCM, только проверки на ненулевые байты/XOR.
- **Риск:** Критический для безопасности, подрывает доверие к заявленной PQC.
- **Шаги:** Интегрировать liboqs или аналог, реализовать ML-DSA-65/AES-GCM в eBPF, покрыть тестами.
- **Критерий приёмки:** eBPF-программа реально проверяет PQC-подписи и шифрует трафик, тесты проходят.

### P0.2 ConsciousnessEngine (AI/ML ядро)
- **Проблема:** Простые if/else, нет реального ML inference, нет explainability.
- **Риск:** Нет интеллектуального самовосстановления, подрывает уникальность self-healing.
- **Шаги:** Внедрить ML inference (causal analysis, anomaly detection), интегрировать explainability (SHAP, XAI).
- **Критерий приёмки:** В цикле MAPE-K реально работает ML inference, есть объяснения решений.

### P0.3 CRDT и Distributed Sync
- **Проблема:** Только scaffold и базовые типы, нет production-grade sync, нет тестов на конфликтные сценарии.
- **Риск:** Возможна потеря данных, split-brain, невозможность масштабирования.
- **Шаги:** Реализовать production CRDT (LWW, OR-Set, Map), покрыть тестами, интегрировать с mesh.
- **Критерий приёмки:** CRDT-синхронизация проходит тесты на конфликтные сценарии, интеграция с mesh.

### P0.4 Advanced ML/AI (Causal Analysis v2, LoRA, RAG)
- **Проблема:** Каркасы без production inference, нет реальных моделей, нет retraining pipeline.
- **Риск:** Нет реального AI-усиления, невозможность демонстрировать ML-преимущества.
- **Шаги:** Подключить реальные модели, автоматизировать retraining, интегрировать с MAPE-K.
- **Критерий приёмки:** Модули causal analysis, LoRA, RAG реально работают на production-данных.

### P0.5 DAO Governance Integration
- **Проблема:** Нет массового использования, неясна глубина интеграции с mesh/ML.
- **Риск:** Governance не влияет на реальные процессы, нет децентрализации.
- **Шаги:** Провести пилот DAO с реальными пользователями, интегрировать с mesh-операциями.
- **Критерий приёмки:** Решения DAO реально влияют на mesh/ML-операции, есть пользовательская активность.

---

## 🔴 ЧАСТЬ 1: КРИТИЧЕСКИЕ ПРОБЛЕМЫ (P0)

### 1.1 Уязвимости безопасности в зависимостях

**Срочность:** 🔴 НЕМЕДЛЕННО  
**Важность:** 🔴 КРИТИЧЕСКАЯ  
**Трудозатраты:** 4-8 часов  
**Риск при игнорировании:** Компрометация системы, утечка данных

#### Выявленные CVE:

| Пакет | Текущая версия | CVE | Исправленная версия | Критичность |
|-------|----------------|-----|---------------------|-------------|
| aiohttp | 3.13.1 | 8 CVE (DoS, request smuggling) | 3.13.3 | 🔴 HIGH |
| certifi | 2023.11.17 | CVE-2024-39689 | 2024.7.4 | 🔴 HIGH |
| Jinja2 | 3.1.2 | CVE-2024-34064 | 3.1.6 | 🟡 MEDIUM |
| pillow | 10.2.0 | CVE-2024-28219 | 10.3.0 | 🟡 MEDIUM |
| setuptools | 68.1.2 | CVE-2024-6345, CVE-2022-40897 | 78.1.1 | 🔴 HIGH |
| urllib3 | 2.6.0 | CVE-2024-37891 | 2.6.3 | 🟡 MEDIUM |
| python-multipart | 0.0.18 | CVE-2024-24762 | 0.0.22 | 🟡 MEDIUM |
| filelock | 3.20.1 | CVE-2024-53899 | 3.20.3 | 🟡 MEDIUM |
| configobj | 5.0.8 | CVE-2023-26112 | 5.0.9 | 🟡 MEDIUM |
| pip | 24.0 | CVE-2024-37891 | 25.3 | 🟡 MEDIUM |

**Без исправления (мониторинг):**
- paramiko - удалён из baseline-зависимостей, потому что runtime-код проекта его не импортирует, а для GHSA-r374-rxx8-8654 нет patched release
- orjson 3.11.3 - CVE (recursion DoS) - нет фикса
- protobuf 6.33.4 - CVE (recursion DoS) - нет фикса

#### Задачи:

```bash
# Немедленное обновление критических пакетов
pip install --upgrade "aiohttp>=3.13.3" "certifi>=2024.7.4" \
    "Jinja2>=3.1.6" "pillow>=10.3.0" "setuptools>=78.1.1" "urllib3>=2.7.0" \
    "python-multipart>=0.0.27" "filelock>=3.20.3" "configobj>=5.0.9" "pip>=25.3"
```

**Критерии приёмки:**
- [ ] `pip-audit` возвращает 0 критических уязвимостей
- [ ] Все тесты проходят после обновления
- [ ] Нет breaking changes в API

---

### 1.2 Критически низкое покрытие тестами

**Срочность:** 🔴 ВЫСОКАЯ  
**Важность:** 🔴 КРИТИЧЕСКАЯ  
**Трудозатраты:** 80-120 часов  
**Риск при игнорировании:** Регрессии, нестабильность в production

#### Текущее состояние:

```
Покрытие: 1.24% (549 строк из 44,327)
Тестовых файлов: 280
Тестовых функций: 1630+
```

**Проблема:** Тесты существуют, но не выполняются или не покрывают код.

#### Приоритетные модули для покрытия:

| Модуль | Строк кода | Текущее покрытие | Целевое покрытие | Приоритет |
|--------|------------|------------------|------------------|-----------|
| src/api/ | ~2,000 | 0% | 80% | 🔴 P0 |
| src/core/ | ~3,000 | 0.02% | 75% | 🔴 P0 |
| src/security/ | ~5,000 | 0% | 90% | 🔴 P0 |
| src/database/ | ~500 | 0% | 80% | 🔴 P0 |
| src/network/ | ~4,000 | 0% | 70% | 🟡 P1 |
| src/ml/ | ~3,000 | 0% | 60% | 🟡 P1 |
| src/self_healing/ | ~2,000 | 0% | 70% | 🟡 P1 |

#### Задачи:

1. **Исправить конфигурацию pytest** (2ч)
   - Проверить pytest.ini / pyproject.toml
   - Убедиться, что тесты находят исходный код
   - Настроить PYTHONPATH

2. **Покрыть критические API endpoints** (20ч)
   - src/api/users.py - аутентификация, CRUD
   - src/api/billing.py - платежи, webhooks
   - src/api/vpn.py - статус, конфигурация

3. **Покрыть security модули** (30ч)
   - src/security/pqc/ - криптография
   - src/security/spiffe/ - идентификация
   - src/security/vault_secrets.py - секреты

4. **Покрыть core модули** (20ч)
   - src/core/cache.py
   - src/core/circuit_breaker.py
   - src/database/__init__.py

**Критерии приёмки:**
- [ ] Общее покрытие ≥ 75%
- [ ] Критические модули (api, security) ≥ 80%
- [ ] Все тесты проходят в CI/CD

---

### 1.3 Hardcoded секреты и токены

**Срочность:** 🔴 ВЫСОКАЯ  
**Важность:** 🔴 КРИТИЧЕСКАЯ  
**Трудозатраты:** 8-16 часов  
**Риск при игнорировании:** Утечка credentials, компрометация

#### Выявленные проблемы:

| Файл | Проблема | Статус |
|------|----------|--------|
| mutants/src/self_healing/mape_k_spiffe_integration.py:84 | `token="dev-join-token"` | 🔴 HARDCODED |
| mutants/test_stripe_webhook.py:8 | `WEBHOOK_SECRET = "whsec_test_..."` | 🟡 TEST ONLY |
| src/sales/telegram_bot.py:55 | `BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"` | 🟡 PLACEHOLDER |
| monitoring/geo-leak-detector/config/settings.py:95 | `secret_key = "your-secret-key-change-in-production"` | 🔴 DEFAULT |
| src/network/transport/session_manager.py:26 | `GHOST_NODE_SECRET` used shared fallback entropy | ✅ FIXED 2026-05-31 |

#### Текущее уточнение baseline

На 2026-05-31 `scripts/check_env_security_defaults.py` проверяет
`src/self_healing` и `src/sales` вместе с основными security/runtime путями.
SPIFFE MAPE-K join token читается только из env в
`src/self_healing/mape_k_spiffe_integration.py`. Session persistence больше не
использует общий fallback entropy: production требует `GHOST_NODE_SECRET` или
`.tmp/pqc_identity.txt`, а non-production использует временный ephemeral key,
если оба источника отсутствуют.

#### Задачи:

1. **Удалить hardcoded токены** (4ч)
   ```python
   # БЫЛО:
   token="dev-join-token"
   
   # СТАЛО:
   token = os.getenv("X0TTA6BL4_SPIRE_JOIN_TOKEN")
   if not token:
       raise RuntimeError("X0TTA6BL4_SPIRE_JOIN_TOKEN required")
   ```

2. **Добавить валидацию секретов при старте** (4ч)
   - Проверка наличия всех required env vars
   - Fail-fast при отсутствии критических секретов

3. **Настроить pre-commit hook для detect-secrets** (2ч)
   ```yaml
   # .pre-commit-config.yaml
   - repo: https://github.com/Yelp/detect-secrets
     rev: v1.4.0
     hooks:
       - id: detect-secrets
         args: ['--baseline', '.secrets.baseline']
   ```

**Критерии приёмки:**
- [ ] `detect-secrets scan` не находит секретов
- [ ] Все секреты читаются из env vars или Vault
- [ ] Приложение не стартует без критических секретов

---

## 🟡 ЧАСТЬ 2: ВАЖНЫЕ ПРОБЛЕМЫ (P1)

### 2.1 Архитектурные дефекты

**Срочность:** 🟡 СРЕДНЯЯ  
**Важность:** 🔴 ВЫСОКАЯ  
**Трудозатраты:** 40-60 часов  
**Риск при игнорировании:** Проблемы масштабирования, технический долг

#### Статус исправлений:

| # | Дефект | Статус | Трудозатраты |
|---|--------|--------|--------------|
| 1 | Синхронный socket в vpn.py | ✅ ИСПРАВЛЕНО | - |
| 2 | SessionLocal внутри endpoints | ⚠️ ЧАСТИЧНО | 4-6ч |
| 3 | Отсутствие Repository Pattern | ❌ НЕ НАЧАТО | 16-24ч |
| 4 | Отсутствие кэширования | ✅ ИСПРАВЛЕНО | - |
| 5 | Circuit breaker для внешних API | ✅ РЕАЛИЗОВАНО | - |
| 6 | Глобальный rate limiting | ⚠️ ЧАСТИЧНО | 4-6ч |
| 7 | Монолитная структура API | ❌ НЕ НАЧАТО | 24-40ч |

#### Задачи:

1. **Унифицировать управление сессиями БД** (6ч)
   - Заменить все `db = SessionLocal()` на `Depends(get_db)`
   - Файлы: src/api/billing.py, src/api/vpn.py

2. **Внедрить Repository Pattern** (24ч)
   ```python
   # src/repositories/base.py
   class BaseRepository(ABC, Generic[T]):
       @abstractmethod
       async def get_by_id(self, id: str) -> Optional[T]: ...
       
   # src/repositories/user_repository.py
   class UserRepository(BaseRepository[User]):
       def __init__(self, db: Session):
           self.db = db
   ```

3. **Разделить API на модули** (40ч)
   ```
   src/api/
   ├── users/
   │   ├── routes.py
   │   ├── schemas.py
   │   └── service.py
   ├── billing/
   └── vpn/
   ```

**Критерии приёмки:**
- [ ] Нет прямых вызовов SessionLocal() в endpoints
- [ ] Repository Pattern для User, Payment, License
- [ ] API разделён на логические модули

---

### 2.2 Устаревшие зависимости

**Срочность:** 🟡 СРЕДНЯЯ  
**Важность:** 🟡 СРЕДНЯЯ  
**Трудозатраты:** 8-16 часов  
**Риск при игнорировании:** Несовместимость, отсутствие новых фич

#### Основные устаревшие пакеты:

| Пакет | Текущая | Последняя | Отставание |
|-------|---------|-----------|------------|
| torch | 2.9.0 | 2.9.1 | 1 minor |
| fastapi | 0.119.1 | 0.120.0 | 1 minor |
| pydantic | 2.11.5 | 2.12.0 | 1 minor |
| sqlalchemy | 2.0.41 | 2.0.42 | 1 patch |
| redis | 5.3.0 | 5.4.0 | 1 minor |
| httpx | 0.28.1 | 0.29.0 | 1 minor |

#### Несоответствия версий:

| Файл | Пакет | Версия | pyproject.toml |
|------|-------|--------|----------------|
| requirements-dev.txt | black | 24.4.2 | 25.9.0 |
| .pre-commit-config.yaml | black | 24.1.1 | 25.9.0 |
| .pre-commit-config.yaml | ruff | 0.2.1 | 0.11.12 |
| .pre-commit-config.yaml | mypy | 1.8.0 | 1.16.0 |

#### Задачи:

1. **Синхронизировать версии** (4ч)
   - Обновить requirements-dev.txt
   - Обновить .pre-commit-config.yaml
   - Запустить тесты

2. **Обновить некритические пакеты** (8ч)
   - Создать отдельную ветку
   - Обновить по одному пакету
   - Тестировать после каждого обновления

**Критерии приёмки:**
- [ ] Все версии синхронизированы между файлами
- [ ] Нет пакетов с отставанием > 2 major версий
- [ ] Все тесты проходят

---

### 2.3 Дублирование кода

**Срочность:** 🟢 НИЗКАЯ  
**Важность:** 🟡 СРЕДНЯЯ  
**Трудозатраты:** 16-24 часа  
**Риск при игнорировании:** Сложность поддержки, несогласованность

#### Выявленные дубликаты:

| Паттерн | Файлы | Решение |
|---------|-------|---------|
| `verify_admin_token()` | src/api/users.py (20+ копий) | Вынести в middleware |
| Telegram bot config | src/sales/telegram_bot.py, telegram_bot.py | Объединить |
| SPIFFE initialization | src/self_healing/mape_k_spiffe_integration.py | Вынести в factory |
| Password validation | src/security/web_security_hardening.py | Использовать везде |

#### Задачи:

1. **Рефакторинг verify_admin_token** (4ч)
   ```python
   # src/api/middleware/auth.py
   async def verify_admin_token(
       x_admin_token: str = Header(None)
   ) -> None:
       admin_token = os.getenv("ADMIN_TOKEN")
       if not admin_token:
           raise HTTPException(500, "ADMIN_TOKEN not configured")
       if x_admin_token != admin_token:
           raise HTTPException(401, "Invalid admin token")
   
   # Использование
   @router.get("/stats", dependencies=[Depends(verify_admin_token)])
   async def get_stats(): ...
   ```

2. **Объединить Telegram боты** (8ч)
   - Выбрать основную версию
   - Мигрировать функционал
   - Удалить дубликаты

**Критерии приёмки:**
- [ ] Нет дублирования verify_admin_token
- [ ] Один Telegram bot
- [ ] Общие утилиты в shared модуле

---

## 🟢 ЧАСТЬ 3: УЛУЧШЕНИЯ (P2)

### 3.1 Документация

**Срочность:** 🟢 НИЗКАЯ  
**Важность:** 🟡 СРЕДНЯЯ  
**Трудозатраты:** 16-24 часа

#### Проблемы:

1. **Неактуальная документация**
   - Многие .md файлы устарели
   - Нет единого README.md
   - API документация неполная

2. **Отсутствующая документация**
   - Нет CONTRIBUTING.md
   - Нет SECURITY.md
   - Нет архитектурных диаграмм

#### Задачи:

1. **Обновить README.md** (4ч)
2. **Создать CONTRIBUTING.md** (2ч)
3. **Создать SECURITY.md** (2ч)
4. **Сгенерировать API docs** (4ч)
5. **Создать архитектурные диаграммы** (8ч)

---

### 3.2 CI/CD улучшения

**Срочность:** 🟢 НИЗКАЯ  
**Важность:** 🟡 СРЕДНЯЯ  
**Трудозатраты:** 8-16 часов

#### Задачи:

1. **Добавить security scanning в CI** (4ч)
   ```yaml
   # .gitlab-ci.yml
   security-scan:
     stage: test
     script:
       - pip-audit
       - bandit -r src/
       - safety check
   ```

2. **Добавить coverage gate** (2ч)
   ```yaml
   test:
     script:
       - pytest --cov=src --cov-fail-under=75
   ```

3. **Добавить dependency update bot** (2ч)
   - Dependabot или Renovate

---

### 3.3 Мониторинг и observability

**Срочность:** 🟢 НИЗКАЯ  
**Важность:** 🟡 СРЕДНЯЯ  
**Трудозатраты:** 16-24 часа

#### Задачи:

1. **Настроить structured logging** (4ч)
2. **Добавить метрики для технического долга** (4ч)
3. **Создать dashboard для code quality** (8ч)

---

## 📈 ЧАСТЬ 4: МАТРИЦА ТЕХНИЧЕСКОГО ДОЛГА

### Матрица Срочность × Важность

```
                    ВАЖНОСТЬ
                    Низкая    Средняя    Высокая
              ┌─────────────────────────────────────┐
    Высокая   │           │ Устаревшие │ CVE в     │
              │           │ пакеты     │ зависим.  │
              │           │            │ Покрытие  │
              │           │            │ тестами   │
    СРОЧНОСТЬ ├───────────┼────────────┼───────────┤
    Средняя   │ Документ. │ Дублиров.  │ Архитект. │
              │           │ кода       │ дефекты   │
              │           │            │           │
              ├───────────┼────────────┼───────────┤
    Низкая    │ CI/CD     │ Монитор.   │           │
              │ улучшения │            │           │
              └─────────────────────────────────────┘
```

### Полная таблица технического долга

| ID | Элемент | Срочность | Важность | Трудозатраты | Риск | Зависимости |
|----|---------|-----------|----------|--------------|------|-------------|
| TD-001 | CVE в зависимостях | 🔴 Высокая | 🔴 Высокая | 4-8ч | Компрометация | - |
| TD-002 | Покрытие тестами 1.24% | 🔴 Высокая | 🔴 Высокая | 80-120ч | Регрессии | - |
| TD-003 | Hardcoded секреты | 🔴 Высокая | 🔴 Высокая | 8-16ч | Утечка данных | - |
| TD-004 | SessionLocal в endpoints | 🟡 Средняя | 🔴 Высокая | 4-6ч | Утечка соединений | - |
| TD-005 | Repository Pattern | 🟡 Средняя | 🔴 Высокая | 16-24ч | Сложность рефакторинга | TD-004 |
| TD-006 | Монолитная структура API | 🟢 Низкая | 🔴 Высокая | 24-40ч | Сложность масштабирования | TD-005 |
| TD-007 | Устаревшие пакеты | 🟡 Средняя | 🟡 СРЕДНЯЯ | 8-16ч | Несовместимость | TD-001 |
| TD-008 | Несинхронизированные версии | 🟡 Средняя | 🟡 СРЕДНЯЯ | 4ч | Конфликты | - |
| TD-009 | Дублирование verify_admin_token | 🟢 Низкая | 🟡 Средняя | 4ч | Несогласованность | - |
| TD-010 | Дублирование Telegram ботов | 🟢 Низкая | 🟡 Средняя | 8ч | Путаница | - |
| TD-011 | Неактуальная документация | 🟢 Низкая | 🟡 Средняя | 16-24ч | Сложность onboarding | - |
| TD-012 | Security scanning в CI | 🟢 Низкая | 🟡 Средняя | 4ч | Пропуск уязвимостей | TD-001 |
| TD-013 | Coverage gate в CI | 🟢 Низкая | 🟡 Средняя | 2ч | Снижение покрытия | TD-002 |
| TD-014 | Dependency update bot | 🟢 Низкая | 🟢 Низкая | 2ч | Устаревание | - |

---

## 🗓️ ЧАСТЬ 5: ДОРОЖНАЯ КАРТА

### Спринт 1: Критическая безопасность (Неделя 1-2)

**Цель:** Устранить критические уязвимости безопасности

| Задача | Трудозатраты | Ответственный | Критерий приёмки |
|--------|--------------|---------------|------------------|
| TD-001: Обновить уязвимые пакеты | 8ч | DevOps | pip-audit clean |
| TD-003: Удалить hardcoded секреты | 16ч | Security | detect-secrets clean |
| TD-012: Security scanning в CI | 4ч | DevOps | CI pipeline green |

**Ожидаемые результаты:**
- 0 критических CVE
- 0 hardcoded секретов
- Автоматическое сканирование в CI

**Метрики успешности:**
- `pip-audit` возвращает 0 уязвимостей
- `detect-secrets scan` возвращает 0 находок
- CI pipeline проходит security stage

---

### Спринт 2: Тестовое покрытие - Фаза 1 (Неделя 3-4)

**Цель:** Поднять покрытие критических модулей до 50%

| Задача | Трудозатраты | Ответственный | Критерий приёмки |
|--------|--------------|---------------|------------------|
| Исправить конфигурацию pytest | 4ч | QA | Тесты находят код |
| Покрыть src/api/ | 20ч | Dev | Coverage ≥ 50% |
| Покрыть src/core/ | 16ч | Dev | Coverage ≥ 50% |
| TD-013: Coverage gate в CI | 2ч | DevOps | CI fails < 50% |

**Ожидаемые результаты:**
- Покрытие API: 50%+
- Покрытие Core: 50%+
- Общее покрытие: 30%+

**Метрики успешности:**
- `pytest --cov` показывает ≥ 30% общего покрытия
- CI pipeline проходит coverage gate

---

### Спринт 3: Тестовое покрытие - Фаза 2 (Неделя 5-6)

**Цель:** Поднять покрытие до 60%

| Задача | Трудозатраты | Ответственный | Критерий приёмки |
|--------|--------------|---------------|------------------|
| Покрыть src/security/ | 30ч | Security | Coverage ≥ 70% |
| Покрыть src/database/ | 10ч | Dev | Coverage ≥ 80% |

**Ожидаемые результаты:**
- Покрытие Security: 70%+
- Покрытие Database: 80%+
- Общее покрытие: 60%+

---

### Спринт 4: Архитектурный рефакторинг (Неделя 7-8)

**Цель:** Устранить архитектурные дефекты

| Задача | Трудозатраты | Ответственный | Критерий приёмки |
|--------|--------------|---------------|------------------|
| TD-004: Унифицировать сессии БД | 6ч | Dev | Нет SessionLocal() |
| TD-009: Рефакторинг verify_admin_token | 4ч | Dev | Один middleware |
| TD-008: Синхронизировать версии | 4ч | DevOps | Версии совпадают |

**Ожидаемые результаты:**
- Единообразное управление сессиями
- Централизованная аутентификация
- Синхронизированные зависимости

---

### Спринт 5: Repository Pattern (Неделя 9-10)

**Цель:** Внедрить Repository Pattern

| Задача | Трудозатраты | Ответственный | Критерий приёмки |
|--------|--------------|---------------|------------------|
| TD-005: BaseRepository | 8ч | Architect | Абстракция готова |
| UserRepository | 8ч | Dev | Тесты проходят |
| PaymentRepository | 8ч | Dev | Тесты проходят |

**Ожидаемые результаты:**
- Абстракция от БД
- Легкая замена хранилища
- Улучшенная тестируемость

---

### Спринт 6: Документация и финализация (Неделя 11-12)

**Цель:** Обновить документацию, достичь 75% покрытия

| Задача | Трудозатраты | Ответственный | Критерий приёмки |
|--------|--------------|---------------|------------------|
| TD-011: Обновить README.md | 4ч | Tech Writer | README актуален |
| Создать CONTRIBUTING.md | 2ч | Tech Writer | Файл создан |
| Создать SECURITY.md | 2ч | Security | Файл создан |
| Финальное тестирование | 16ч | QA | Coverage ≥ 75% |

**Ожидаемые результаты:**
- Актуальная документация
- Покрытие тестами ≥ 75%
- Готовность к production

---

## 🔄 ЧАСТЬ 6: СТРАТЕГИЯ РЕФАКТОРИНГА

### Принципы параллельной разработки

1. **Feature Flags**
   ```python
   # src/core/feature_flags.py
   USE_REPOSITORY_PATTERN = os.getenv("USE_REPOSITORY_PATTERN", "false") == "true"
   
   # Использование
   if USE_REPOSITORY_PATTERN:
       user = await user_repository.get_by_id(user_id)
   else:
       user = db.query(User).filter(User.id == user_id).first()
   ```

2. **Strangler Fig Pattern**
   - Новый код использует новую архитектуру
   - Старый код постепенно мигрирует
   - Оба варианта работают параллельно

3. **Branch by Abstraction**
   - Создать абстракцию над старым кодом
   - Реализовать новую версию
   - Переключить на новую версию
   - Удалить старую

### Правила для новой функциональности

1. **Все новые endpoints** используют:
   - `Depends(get_db)` для сессий
   - Repository Pattern для доступа к данным
   - Централизованную аутентификацию

2. **Все новые модули** имеют:
   - Покрытие тестами ≥ 80%
   - Type hints
   - Docstrings

3. **Все новые зависимости**:
   - Проверяются на CVE перед добавлением
   - Добавляются в pyproject.toml с версией
   - Документируются в CHANGELOG.md

---

## 🤖 ЧАСТЬ 7: АВТОМАТИЗАЦИЯ ВЫЯВЛЕНИЯ ТЕХНИЧЕСКОГО ДОЛГА

### Pre-commit hooks

```yaml
# .pre-commit-config.yaml
repos:
  # Security
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.4.0
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']
  
  # Code quality
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.11.12
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  
  # Type checking
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.16.0
    hooks:
      - id: mypy
        additional_dependencies: [types-all]
  
  # Dependency audit
  - repo: local
    hooks:
      - id: pip-audit
        name: pip-audit
        entry: pip-audit
        language: system
        pass_filenames: false
```

### CI/CD Pipeline

```yaml
# .gitlab-ci.yml
stages:
  - lint
  - security
  - test
  - build

lint:
  stage: lint
  script:
    - ruff check src/
    - mypy src/

security:
  stage: security
  script:
    - pip-audit
    - bandit -r src/ -ll
    - safety check
    - detect-secrets scan --baseline .secrets.baseline

test:
  stage: test
  script:
    - pytest --cov=src --cov-fail-under=75 --cov-report=xml
  coverage: '/TOTAL.*\s+(\d+%)/'
  artifacts:
    reports:
      coverage_report:
        coverage_format: cobertura
        path: coverage.xml

dependency-update:
  stage: lint
  script:
    - pip list --outdated --format=json > outdated.json
    - python scripts/check_outdated.py outdated.json
  allow_failure: true
```

### Метрики технического долга

```python
# scripts/tech_debt_metrics.py
"""
Скрипт для сбора метрик технического долга.
Запускать еженедельно в CI.
"""

import subprocess
import json

def collect_metrics():
    metrics = {
        "coverage": get_coverage(),
        "vulnerabilities": get_vulnerabilities(),
        "outdated_packages": get_outdated_count(),
        "code_smells": get_code_smells(),
        "duplications": get_duplications(),
    }
    return metrics

def get_coverage():
    result = subprocess.run(
        ["pytest", "--cov=src", "--cov-report=json"],
        capture_output=True
    )
    with open("coverage.json") as f:
        data = json.load(f)
    return data["totals"]["percent_covered"]

def get_vulnerabilities():
    result = subprocess.run(
        ["pip-audit", "--format=json"],
        capture_output=True
    )
    vulns = json.loads(result.stdout)
    return len(vulns)

# ... остальные функции
```

### SonarQube интеграция

```yaml
# sonar-project.properties
sonar.projectKey=x0tta6bl4
sonar.projectName=x0tta6bl4
sonar.sources=src
sonar.tests=tests
sonar.python.coverage.reportPaths=coverage.xml
sonar.python.bandit.reportPaths=bandit-report.json

# Quality Gates
sonar.qualitygate.wait=true
```

---

## 📊 ЧАСТЬ 8: МЕТРИКИ И KPI

### Целевые метрики

| Метрика | Текущее | Цель (3 мес) | Цель (6 мес) |
|---------|---------|--------------|--------------|
| Покрытие тестами | 1.24% | 75% | 85% |
| Критические CVE | 15+ | 0 | 0 |
| Hardcoded секреты | 5+ | 0 | 0 |
| Устаревшие пакеты (>2 major) | 10+ | 0 | 0 |
| Code smells (SonarQube) | N/A | < 100 | < 50 |
| Technical debt ratio | N/A | < 5% | < 3% |

### Dashboard метрик

Рекомендуется создать Grafana dashboard с:
- Покрытие тестами (trend)
- Количество уязвимостей (trend)
- Количество устаревших пакетов
- Code quality score
- Build success rate

---

## ✅ ЧАСТЬ 9: ЧЕКЛИСТ ГОТОВНОСТИ

### Критерии завершения устранения технического долга

#### Безопасность
- [ ] 0 критических CVE в зависимостях
- [ ] 0 hardcoded секретов
- [ ] Security scanning в CI
- [ ] SECURITY.md создан

#### Качество кода
- [ ] Покрытие тестами ≥ 75%
- [ ] Coverage gate в CI
- [ ] Все версии синхронизированы
- [ ] Нет дублирования критического кода

#### Архитектура
- [ ] Единообразное управление сессиями БД
- [ ] Repository Pattern для основных сущностей
- [ ] Централизованная аутентификация

#### Документация
- [ ] README.md актуален
- [ ] CONTRIBUTING.md создан
- [ ] API документация сгенерирована
- [ ] Архитектурные диаграммы созданы

#### Автоматизация
- [ ] Pre-commit hooks настроены
- [ ] CI/CD pipeline полный
- [ ] Dependency update bot настроен
- [ ] Метрики технического долга собираются

---

## 📝 Заключение

Проект x0tta6bl4 имеет значительный технический долг, но он управляем. Основные проблемы:

1. **Критически низкое покрытие тестами** (1.24%) - главный риск
2. **Уязвимости в зависимостях** - требуют немедленного исправления
3. **Архитектурные дефекты** - частично исправлены, требуют завершения

При следовании данному плану, технический долг может быть устранён за 3-4 месяца при выделении 1 разработчика full-time или 6-8 месяцев при частичной занятости.

**Рекомендуемый приоритет:**
1. Безопасность (Спринт 1)
2. Тестовое покрытие (Спринты 2-3)
3. Архитектура (Спринты 4-5)
4. Документация (Спринт 6)

---

**Документ создан:** 2026-02-02  
**Следующий review:** 2026-03-02  
**Ответственный:** Technical Lead

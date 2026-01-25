# 📋 План действий по исправлению уязвимостей x0tta6bl4
## Дата: 10 января 2026
## Оценка времени: 5-6 недель до Production Ready

---

## 🎯 Стратегия

**Подход:** Fix by Priority → Test → Deploy → Validate
**Принцип:** Сначала критические уязвимости безопасности, затем инфраструктура, затем улучшения

---

## 📅 Неделя 1-2: P0 - Критические уязвимости безопасности (7-10 дней)

### День 1-2: Исправление модуля post_quantum.py
**Задача:** P0-1
**Файлы:** `src/security/__init__.py`

**Действия:**
1. Создать `src/security/post_quantum.py` с импортами из `post_quantum_liboqs.py`
2. Или удалить импорт из `__init__.py` и обновить все использующие модули
3. Запустить `pytest` и убедиться что 0 ошибок импорта

**Команды:**
```bash
# Вариант 1: Создать файл
cp src/security/post_quantum_liboqs.py src/security/post_quantum.py

# Вариант 2: Удалить импорт и обновить
# Отредактировать src/security/__init__.py

# Тестирование
pytest tests/unit/ -v
```

**Критерий успеха:** 0 ошибок импорта в pytest

---

### День 2-3: Замена pickle на json
**Задача:** P0-2
**Файлы:** `src/storage/vector_index.py`

**Действия:**
1. Заменить `pickle.dump` на `json.dump`
2. Заменить `pickle.load` на `json.load`
3. Обновить структуру данных для JSON-совместимости
4. Протестировать сохранение/загрузку

**Изменения:**
```python
# Было:
import pickle
with open(metadata_file, 'wb') as f:
    pickle.dump(data, f)

# Стало:
import json
with open(metadata_file, 'w') as f:
    json.dump(data, f)
```

**Критерий успеха:** Тесты vector_index проходят, данные сохраняются/загружаются корректно

---

### День 3-4: Замена SHA-256 на bcrypt для паролей
**Задача:** P0-3
**Файлы:** `src/api/users.py`

**Действия:**
1. Заменить `hash_password` функцию на bcrypt
2. Обновить `hash_password` в `login` endpoint
3. Протестировать регистрацию и логин
4. Мигрировать существующие пароли (если есть)

**Изменения:**
```python
# Было:
import hashlib
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

# Стало:
import bcrypt
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

# В login:
# Было:
if user["password_hash"] != hash_password(credentials.password):

# Стало:
if not bcrypt.checkpw(credentials.password.encode(), user["password_hash"].encode()):
```

**Критерий успеха:** Регистрация и логин работают, пароли хешируются bcrypt

---

### День 4: Убрать api_key из UserResponse
**Задача:** P0-4
**Файлы:** `src/api/users.py`

**Действия:**
1. Удалить `api_key` из `UserResponse` модели
2. Создать отдельный endpoint `/me/api-key` для получения ключа
3. Добавить аутентификацию на новый endpoint

**Изменения:**
```python
# Убрать из UserResponse:
class UserResponse(BaseModel):
    # ... другие поля
    # api_key: str  # УДАЛИТЬ

# Добавить новый endpoint:
@router.get("/me/api-key")
async def get_api_key():
    # Проверить аутентификацию
    # Вернуть api_key
```

**Критерий успеха:** API ключ не утекает в обычных ответах

---

### День 5: Добавить rate limiting
**Задача:** P0-5
**Файлы:** `src/core/app.py`

**Действия:**
1. Импортировать `slowapi` (уже в requirements.txt)
2. Настроить Limiter для FastAPI
3. Добавить rate limiting на критические endpoints

**Изменения:**
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@router.post("/login")
@limiter.limit("5/minute")  # 5 попыток в минуту
async def login(credentials: UserLogin):
    # ...
```

**Критерий успеха:** Rate limiting работает, DDoS атаки блокируются

---

### День 6: Добавить аутентификацию на /stats
**Задача:** P0-6
**Файлы:** `src/api/users.py`

**Действия:**
1. Создать middleware для проверки admin прав
2. Добавить зависимость для admin endpoints
3. Применить к `/stats` endpoint

**Изменения:**
```python
from fastapi import Depends, HTTPException, Header

async def verify_admin(x_admin_token: str = Header(...)):
    if x_admin_token != os.getenv("ADMIN_TOKEN"):
        raise HTTPException(status_code=403, detail="Admin only")

@router.get("/stats")
async def get_user_stats(admin=Depends(verify_admin)):
    # ...
```

**Критерий успеха:** /stats требует аутентификацию

---

### День 7: Использовать hmac.compare_digest
**Задача:** P0-7
**Файлы:** `src/api/users.py`

**Действия:**
1. Заменить `!=` на `hmac.compare_digest` для паролей
2. Протестировать логин

**Изменения:**
```python
import hmac

# Было:
if user["password_hash"] != hash_password(credentials.password):

# Стало:
if not hmac.compare_digest(
    user["password_hash"].encode(),
    hash_password(credentials.password).encode()
):
```

**Критерий успеха:** Timing attack уязвимость устранена

---

### День 8: Заменить urllib.request на httpx
**Задача:** P0-8
**Файлы:** `src/network/yggdrasil_client.py`

**Действия:**
1. Заменить `urllib.request` на `httpx`
2. Добавить валидацию URL
3. Добавить timeout

**Изменения:**
```python
import httpx
from urllib.parse import urlparse

async def fetch_yggdrasil_status(url: str):
    # Валидация URL
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        raise ValueError("Invalid URL scheme")
    
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(url)
        return response.json()
```

**Критерий успеха:** SSRF уязвимость устранена

---

## 📅 Неделя 3: P1 - Высокий приоритет (5-7 дней)

### День 1-2: Исправить CI/CD
**Задача:** P1-1
**Файлы:** `.gitlab-ci.yml`

**Действия:**
1. Убрать `|| true` из pytest команды
2. Убрать `|| true` из ruff и mypy команд
3. Сделать тесты обязательными для деплоя

**Изменения:**
```yaml
# Было:
pytest tests/unit/ --cov=src --cov-fail-under=85 || true

# Стало:
pytest tests/unit/ --cov=src --cov-fail-under=85

# Было:
ruff check . || true

# Стало:
ruff check .
```

**Критерий успеха:** Тесты блокируют деплой при провале

---

### День 3: Включить readOnlyRootFilesystem
**Задача:** P1-2
**Файлы:** `helm/x0tta6bl4/values-production.yaml`

**Действия:**
1. Изменить `readOnlyRootFilesystem` на `true`
2. Добавить volumes для `/tmp`, `/app/data`, `/app/logs`
3. Обновить deployment template

**Изменения:**
```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  fsGroup: 1000
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: true  # ИЗМЕНИТЬ

volumes:
  - name: tmp
    emptyDir: {}
  - name: data
    emptyDir: {}
  - name: logs
    emptyDir: {}

volumeMounts:
  - name: tmp
    mountPath: /tmp
  - name: data
    mountPath: /app/data
  - name: logs
    mountPath: /app/logs
```

**Критерий успеха:** Pods работают с read-only root filesystem

---

### День 4: Отключить публичный доступ к EKS
**Задача:** P1-3
**Файлы:** `terraform/aws/main.tf`

**Действия:**
1. Изменить `cluster_endpoint_public_access` на `false`
2. Добавить VPN или bastion host для доступа
3. Обновить документацию

**Изменения:**
```hcl
# Было:
cluster_endpoint_public_access = true

# Стало:
cluster_endpoint_public_access = false
```

**Критерий успеха:** EKS API endpoint недоступен публично

---

### День 5: Использовать commit hash в Dockerfile
**Задача:** P1-4
**Файлы:** `Dockerfile`

**Действия:**
1. Найти конкретный commit hash liboqs
2. Заменить `--branch main` на `--branch commit_hash`

**Изменения:**
```dockerfile
# Было:
RUN git clone --depth 1 --branch main https://github.com/open-quantum-safe/liboqs.git /tmp/liboqs

# Стало:
RUN git clone --depth 1 --branch v0.10.0 https://github.com/open-quantum-safe/liboqs.git /tmp/liboqs
# Или:
RUN git clone --depth 1 https://github.com/open-quantum-safe/liboqs.git /tmp/liboqs && \
    cd /tmp/liboqs && \
    git checkout abc123def456
```

**Критерий успеха:** Dockerfile использует конкретную версию liboqs

---

### День 6: Унифицировать версии зависимостей
**Задача:** P1-5
**Файлы:** `requirements.txt`, `pyproject.toml`, `Dockerfile`

**Действия:**
1. Выбрать единую версию для каждого пакета
2. Обновить все файлы
3. Создать скрипт для синхронизации

**Команды:**
```bash
# Создать скрипт sync_versions.py
# Запустить для синхронизации
python scripts/sync_versions.py
```

**Критерий успеха:** Версии согласованы во всех файлах

---

### День 7: Обновить уязвимые зависимости
**Задача:** P1-6
**Файлы:** `requirements.txt`

**Действия:**
1. Запустить `pip-audit`
2. Обновить уязвимые пакеты
3. Протестировать совместимость

**Команды:**
```bash
pip-audit
pip install --upgrade urllib3 cryptography
pip freeze > requirements.txt
```

**Критерий успеха:** `pip-audit` не находит уязвимостей

---

### День 8: Зашифровать Terraform state
**Задача:** P1-7
**Файлы:** `terraform/eks/main.tf`

**Действия:**
1. Раскомментировать backend блок
2. Убедиться что `encrypt = true`
3. Создать S3 bucket и DynamoDB table

**Изменения:**
```hcl
terraform {
  backend "s3" {
    bucket         = "x0tta6bl4-terraform-state"
    key            = "eks/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true  # ВАЖНО
    dynamodb_table = "x0tta6bl4-terraform-locks"
  }
}
```

**Критерий успеха:** Terraform state зашифрован в S3

---

### День 9: Установить SECRET_KEY для Flask
**Задача:** P1-8
**Файлы:** `src/web/aggregator_dashboard.py`

**Действия:**
1. Добавить `app.secret_key` из environment variable
2. Добавить в `.env.example`

**Изменения:**
```python
import os
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY') or os.urandom(32)
```

**Критерий успеха:** Flask использует secret_key

---

### День 10: Валидировать subprocess вызовы
**Задача:** P1-9
**Файлы:** `src/network/ebpf/loader.py`, `src/mesh/real_network_adapter.py`

**Действия:**
1. Создать whitelist разрешённых команд
2. Валидировать все аргументы
3. Добавить санитизацию

**Изменения:**
```python
ALLOWED_COMMANDS = {'bpftool', 'batctl', 'yggdrasilctl', 'ip', 'tc'}

def validate_command(cmd: list) -> bool:
    if not cmd or cmd[0] not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {cmd[0]}")
    # Дополнительная валидация аргументов
    return True

# Перед вызовом:
validate_command(cmd)
subprocess.run(cmd, ...)
```

**Критерий успеха:** Все subprocess вызовы валидированы

---

## 📅 Неделя 4: P2 - Средний приоритет (3-5 дней)

### День 1: Добавить ResourceQuota
**Задача:** P2-1
**Файлы:** `k8s/resource-quota.yaml`

**Действия:**
1. Создать ResourceQuota manifest
2. Применить к namespace

**Создать файл:**
```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: x0tta6bl4-quota
  namespace: x0tta6bl4-production
spec:
  hard:
    requests.cpu: "10"
    requests.memory: "20Gi"
    limits.cpu: "20"
    limits.memory: "40Gi"
    persistentvolumeclaims: "5"
```

**Критерий успеха:** ResourceQuota применён к namespace

---

### День 2: Настроить External Secrets
**Задача:** P2-2
**Файлы:** `helm/x0tta6bl4/values-production.yaml`

**Действия:**
1. Установить External Secrets Operator
2. Создать SecretStore
3. Обновить Helm values

**Критерий успеха:** Секреты получаются из Vault/AWS Secrets Manager

---

### День 3: Усилить Network Policies
**Задача:** P2-3
**Файлы:** `k8s/network-policies/x0tta6bl4-network-policy.yaml`

**Действия:**
1. Добавить egress whitelist
2. Ограничить внешние подключения

**Критерий успеха:** Egress трафик ограничен

---

### День 4: Добавить CSRF protection
**Задача:** P2-4
**Файлы:** `src/core/app.py`

**Действия:**
1. Установить `starlette-csrf`
2. Добавить middleware
3. Обновить frontend

**Критерий успеха:** CSRF protection включён

---

### День 5: Добавить security headers
**Задача:** P2-5
**Файлы:** `src/core/app.py`

**Действия:**
1. Создать middleware для security headers
2. Добавить CSP, HSTS, X-Frame-Options

**Изменения:**
```python
from starlette.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

app.add_middleware(SecurityHeadersMiddleware)
```

**Критерий успеха:** Security headers присутствуют в ответах

---

### День 6: Перенести users_db в PostgreSQL
**Задача:** P2-6
**Файлы:** `src/api/users.py`, `database.py`

**Действия:**
1. Создать схему PostgreSQL
2. Заменить in-memory storage на PostgreSQL
3. Мигрировать существующие данные

**Критерий успеха:** Пользователи хранятся в PostgreSQL

---

### День 7: Добавить request size limits
**Задача:** P2-7
**Файлы:** `src/core/app.py`

**Действия:**
1. Настроить max request size в FastAPI

**Изменения:**
```python
app = FastAPI(max_request_size=10 * 1024 * 1024)  # 10MB
```

**Критерий успеха:** Большие запросы отклоняются

---

## 📅 Неделя 5-6: P3 - Низкий приоритет (1-2 недели)

### Задача P3-1: Увеличить покрытие кода до 75%
**Действия:**
1. Написать тесты для непокрытых модулей
2. Запустить `pytest --cov=src --cov-report=html`
3. Целевой охват: 75%

**Команды:**
```bash
pytest --cov=src --cov-report=html --cov-fail-under=75
open htmlcov/index.html
```

---

### Задача P3-2: Реально валидировать метрики
**Действия:**
1. Запустить бенчмарки в staging
2. Измерить реальные метрики
3. Обновить `validation_results_20260103.json`

---

### Задача P3-3: Добавить type hints
**Действия:**
1. Запустить `mypy --strict`
2. Исправить все type errors
3. Добавить type hints во все функции

---

### Задача P3-4: Настроить pre-commit hooks
**Действия:**
1. Обновить `.pre-commit-config.yaml`
2. Сделать hooks обязательными

**Изменения:**
```yaml
repos:
  - repo: https://github.com/psf/black
    hooks:
      - id: black
  - repo: https://github.com/pycqa/flake8
    hooks:
      - id: flake8
  - repo: https://github.com/pre-commit/mirrors-mypy
    hooks:
      - id: mypy
```

---

### Задача P3-5: Добавить integration tests
**Действия:**
1. Создать тесты для critical paths
2. Тестировать end-to-end сценарии

---

### Задача P3-6: Добавить HEALTHCHECK в Dockerfile
**Действия:**
1. Добавить HEALTHCHECK инструкцию

**Изменения:**
```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8080/api/v1/health || exit 1
```

---

### Задача P3-7: Унифицировать лицензию
**Действия:**
1. Обновить `pyproject.toml` на Apache 2.0
2. Убедиться что LICENSE файл соответствует

---

### Задача P3-8: Исправить CONTINUITY.md
**Действия:**
1. Обновить Test Coverage на 4.86%
2. Обновить количество тестов на 64
3. Удалить "VALIDATED" из метрик
4. Обновить Production Readiness на 3.5/10

---

## 📊 Трекинг прогресса

### Чек-лист прогресса

| Неделя | P0 | P1 | P2 | P3 | Всего |
|--------|----|----|----|----|-------|
| Неделя 1-2 | 8/8 | 0/10 | 0/7 | 0/8 | 8/33 (24%) |
| Неделя 3 | 8/8 | 10/10 | 0/7 | 0/8 | 18/33 (55%) |
| Неделя 4 | 8/8 | 10/10 | 7/7 | 0/8 | 25/33 (76%) |
| Неделя 5-6 | 8/8 | 10/10 | 7/7 | 8/8 | 33/33 (100%) |

---

## 🎯 Критерии успеха

### Критические (P0):
- [ ] 0 ошибок импорта в pytest
- [ ] Unsafe pickle заменён на json
- [ ] Пароли хешируются bcrypt
- [ ] API ключи не утекают в ответах
- [ ] Rate limiting включён
- [ ] Admin endpoints защищены
- [ ] Timing attack устранён
- [ ] SSRF уязвимость устранена

### Высокие (P1):
- [ ] CI/CD блокирует бракованный код
- [ ] readOnlyRootFilesystem включён
- [ ] EKS публичный доступ отключён
- [ ] Git clone использует commit hash
- [ ] Версии зависимостей унифицированы
- [ ] Уязвимые зависимости обновлены
- [ ] Terraform state зашифрован
- [ ] Flask SECRET_KEY установлен
- [ ] Subprocess вызовы валидированы

### Средние (P2):
- [ ] ResourceQuota добавлен
- [ ] External Secrets настроен
- [ ] Network Policies усилены
- [ ] CSRF protection включён
- [ ] Security headers добавлены
- [ ] PostgreSQL используется для users
- [ ] Request size limits добавлены

### Низкие (P3):
- [ ] Покрытие кода ≥ 75%
- [ ] Метрики реально валидированы
- [ ] Type hints добавлены
- [ ] Pre-commit hooks обязательны
- [ ] Integration tests добавлены
- [ ] HEALTHCHECK в Dockerfile
- [ ] Лицензия унифицирована
- [ ] CONTINUITY.md исправлен

---

## 📞 Поддержка

Если возникают проблемы:
1. Проверить логи: `kubectl logs -f deployment/x0tta6bl4`
2. Проверить события: `kubectl get events --sort-by='.lastTimestamp'`
3. Проверить pod status: `kubectl describe pod <pod-name>`
4. Запустить локально: `python -m uvicorn src.core.app:app --reload`

---

**Создано:** 10 января 2026
**Автор:** Cascade AI Assistant
**Версия:** 1.0

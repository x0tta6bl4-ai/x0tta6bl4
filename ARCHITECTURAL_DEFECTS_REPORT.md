# Архитектурные дефекты, блокирующие масштабирование

## Дата анализа: 2026-01-29
## Файлы: src/api/users.py, src/api/billing.py, src/api/vpn.py

---

## 1. Жёсткие зависимости и отсутствие абстракций

### Проблема
Прямой импорт и использование `SessionLocal` внутри endpoint'ов создаёт жёсткую связанность с SQLAlchemy.

**Примеры:**
- `src/api/billing.py:165` - `db = SessionLocal()` внутри webhook
- `src/api/vpn.py:187, 218` - `db = SessionLocal()` внутри endpoint'ов

### Решение
Внедрить Repository Pattern:

```python
# src/repositories/base.py
from abc import ABC, abstractmethod
from typing import TypeVar, Generic, List, Optional

T = TypeVar('T')

class BaseRepository(ABC, Generic[T]):
    @abstractmethod
    async def get_by_id(self, id: str) -> Optional[T]: ...
    
    @abstractmethod
    async def list(self, **filters) -> List[T]: ...
    
    @abstractmethod
    async def create(self, entity: T) -> T: ...

# src/repositories/user_repository.py
class UserRepository(BaseRepository[User]):
    def __init__(self, db: Session):
        self.db = db
    
    async def get_by_email(self, email: str) -> Optional[User]:
        return self.db.query(User).filter(User.email == email).first()
```

**Приоритет:** Высокий  
**Трудозатраты:** 2-3 дня  
**Влияние на масштабирование:** Позволяет легко заменить БД на распределённое хранилище

---

## 2. Синхронные блокирующие вызовы ввода-вывода

### Проблема
Использование синхронного `socket.socket` в async endpoint:

**src/api/vpn.py:147-155**
```python
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(2)
try:
    sock.connect((server, port))  # Блокирующий вызов!
```

### Решение
Заменить на asyncio-совместимую версию:

```python
import asyncio

async def check_vpn_status(server: str, port: int) -> bool:
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(server, port),
            timeout=2.0
        )
        writer.close()
        await writer.wait_closed()
        return True
    except (asyncio.TimeoutError, ConnectionRefusedError):
        return False
```

**Приоритет:** Высокий  
**Трудозатраты:** 2-4 часа  
**Влияние на масштабирование:** Устраняет блокировку event loop

---

## 3. Отсутствие кэширования

### Проблема
Каждый запрос к `/vpn/status` и `/vpn/users` делает запросы в БД без кэширования.

### Решение
Внедрить Redis-кэширование:

```python
# src/core/cache.py
import redis.asyncio as redis
from functools import wraps

redis_client = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost"))

def cached(ttl: int = 60):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{hash(str(args) + str(kwargs))}"
            cached = await redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
            
            result = await func(*args, **kwargs)
            await redis_client.setex(cache_key, ttl, json.dumps(result))
            return result
        return wrapper
    return decorator

# Использование
@router.get("/status")
@cached(ttl=30)
async def get_vpn_status():
    ...
```

**Приоритет:** Средний  
**Трудозатраты:** 1 день  
**Влияние на масштабирование:** Снижает нагрузку на БД в 10-100 раз

---

## 4. Проблемы с управлением соединениями

### Проблема
Создание новой сессии БД внутри endpoint'ов без использования Dependency Injection:

**src/api/vpn.py:187**
```python
from src.database import SessionLocal, User
db = SessionLocal()  # Новое соединение на каждый запрос!
```

### Решение
Использовать FastAPI Depends для управления сессиями:

```python
# Уже частично реализовано в users.py!
from src.database import get_db

@router.get("/users")
async def get_vpn_users(db: Session = Depends(get_db)):
    # Сессия автоматически закроется после запроса
    ...
```

**Приоритет:** Высокий  
**Трудозатраты:** 4-6 часов  
**Влияние на масштабирование:** Пул соединений SQLAlchemy работает эффективнее

---

## 5. Монолитная структура API

### Проблема
Все endpoint'ы в одном файле, сложно масштабировать горизонтально:
- `users.py` - 209 строк
- `billing.py` - 196 строк  
- `vpn.py` - 226 строк

### Решение
Разделить на микросервисы или хотя бы модули:

```
src/api/
├── users/
│   ├── __init__.py
│   ├── routes.py
│   ├── schemas.py
│   └── service.py
├── billing/
│   ├── __init__.py
│   ├── routes.py
│   ├── schemas.py
│   └── service.py
└── vpn/
    ├── __init__.py
    ├── routes.py
    ├── schemas.py
    └── service.py
```

**Приоритет:** Низкий (долгосрочный)  
**Трудозатраты:** 3-5 дней  
**Влияние на масштабирование:** Позволяет деплоить сервисы независимо

---

## 6. Rate Limiting только на уровне endpoint

### Проблема
Rate limiting через `@limiter.limit()` не защищает от DDoS на уровне приложения.

### Решение
Добавить глобальный rate limiting и circuit breaker:

```python
# src/core/circuit_breaker.py
from pybreaker import CircuitBreaker

db_breaker = CircuitBreaker(fail_max=5, reset_timeout=60)

@db_breaker
async def get_user_from_db(user_id: str):
    ...
```

**Приоритет:** Средний  
**Трудозатраты:** 4-6 часов  
**Влияние на масштабирование:** Защита от каскадных отказов

---

## 7. Синхронные вызовы внешних API

### Проблема
В `billing.py` используется `httpx.AsyncClient`, но нет retry логики и circuit breaker.

### Решение
```python
from httpx import AsyncClient, Timeout
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def call_stripe_api(data: dict):
    async with AsyncClient(timeout=Timeout(20.0)) as client:
        resp = await client.post(...)
        resp.raise_for_status()
        return resp.json()
```

**Приоритет:** Средний  
**Трудозатраты:** 2-3 часа  
**Влияние на масштабирование:** Устойчивость к временным сбоям Stripe

---

## Итоговая приоритизация

| # | Дефект | Приоритет | Трудозатраты | ROI |
|---|--------|-----------|--------------|-----|
| 1 | Синхронный socket в vpn.py | 🔴 Высокий | 2-4ч | Высокий |
| 2 | SessionLocal внутри endpoint'ов | 🔴 Высокий | 4-6ч | Высокий |
| 3 | Отсутствие Repository Pattern | 🟡 Средний | 2-3дн | Средний |
| 4 | Отсутствие кэширования | 🟡 Средний | 1 день | Высокий |
| 5 | Circuit breaker для внешних API | 🟡 Средний | 2-3ч | Средний |
| 6 | Глобальный rate limiting | 🟡 Средний | 4-6ч | Средний |
| 7 | Монолитная структура | 🟢 Низкий | 3-5дн | Низкий |

---

## Рекомендуемый план внедрения

### Неделя 1 (Критические)
1. Исправить синхронный socket в vpn.py
2. Унифицировать управление сессиями БД через Depends

### Неделя 2 (Важные)
3. Внедрить Redis-кэширование для частых запросов
4. Добавить retry и circuit breaker для Stripe API

### Месяц 2 (Архитектурные)
5. Рефакторинг в Repository Pattern
6. Разделение на модули/микросервисы

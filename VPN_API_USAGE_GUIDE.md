# Руководство по использованию VPN API для x0tta6bl4

## Обзор
В этом руководстве описано, как использовать только что реализованные VPN API эндпоинты с протоколом VLESS+Reality для проверки работы и настройки подключений.

## Основные эндпоинты VPN API

### 1. Проверка статуса VPN-сервера
Получить информацию о статусе VPN-сервера

```bash
curl -X GET "http://127.0.0.1:8081/vpn/status" -H "accept: application/json"
```

**Пример ответа:**
```json
{
  "status": "online",
  "server": "89.125.1.107",
  "port": 39829,
  "protocol": "VLESS+Reality",
  "active_users": 5,
  "uptime": 86400.0
}
```

### 2. Генерация VPN-конфигурации
Сгенерировать VPN-конфигурацию для пользователя

```bash
curl -X GET "http://127.0.0.1:8081/vpn/config?user_id=12345&username=testuser" -H "accept: application/json"
```

**Пример ответа:**
```json
{
  "user_id": 12345,
  "username": "testuser",
  "vless_link": "vless://31312e22-150b-4ae5-a27a-7c38148a9f20@89.125.1.107:39829?type=tcp&encryption=none&security=reality&pbk=xMwVfOuehQZwVHPodTvo3TJEGUYUbxmGTeAxMUBWpww&fp=chrome&sni=google.com&sid=6b&spx=%2Fwatch%3Fv%3DdQw4w9WgXcQ&flow=xtls-rprx-vision#x0tta6bl4_VPN",
  "config_text": "Детальная конфигурация с инструкциями"
}
```

### 3. Создание конфигурации через POST-запрос
Создать VPN-конфигурацию используя POST-запрос с данными в теле запроса

```bash
curl -X POST "http://127.0.0.1:8081/vpn/config" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 12345,
    "username": "testuser",
    "server": "89.125.1.107",
    "port": 39829
  }'
```

### 4. Получение списка активных пользователей
Получить список всех активных VPN-пользователей

```bash
curl -X GET "http://127.0.0.1:8081/vpn/users" -H "accept: application/json"
```

### 5. Удаление VPN-пользователя
Удалить VPN-пользователя по ID

```bash
curl -X DELETE "http://127.0.0.1:8081/vpn/user/12345" -H "accept: application/json"
```

## Как подключиться к VPN

### Шаги для подключения:

1. **Сгенерируйте конфигурацию:**
   ```bash
   curl -X GET "http://127.0.0.1:8081/vpn/config?user_id=ВАШ_USER_ID&username=ВАШ_ИМЯ"
   ```

2. **Скопируйте VLESS-ссылку** из ответа

3. **Установите клиент VPN:**
   - Windows: [v2rayN](https://github.com/2dust/v2rayN)
   - Android: [v2rayNG](https://play.google.com/store/apps/details?id=com.v2ray.ang)
   - iOS: Shadowrocket (App Store)
   - Mac: v2rayA или ClashX

4. **Импортируйте конфигурацию:**
   - В v2rayN: Выберите "Сервер" → "Импорт из буфера обмена"
   - В v2rayNG: Нажмите "+" → "Импорт из буфера обмена"

5. **Подключитесь** к созданному серверу

6. **Проверьте работу:**
   Откройте сайт, который был заблокирован, например, [Reddit](https://reddit.com) или [Twitter](https://twitter.com)

## Подробные параметры конфигурации

Если нужно настроить VPN вручную (без импорта ссылки), используйте эти параметры:

| Параметр | Значение |
|----------|----------|
| Protocol | VLESS |
| Address | 89.125.1.107 |
| Port | 39829 |
| UUID | (уникальный для каждого пользователя) |
| Flow | xtls-rprx-vision |
| Encryption | none |
| Network | TCP |
| Security | reality |
| Reality Public Key | xMwVfOuehQZwVHPodTvo3TJEGUYUbxmGTeAxMUBWpww |
| Fingerprint | chrome |
| SNI | google.com |
| Short ID | 6b |
| SpiderX | /watch?v=dQw4w9WgXcQ |

## Проверка работы API с помощью Python

Создайте файл `test_vpn_api.py`:

```python
import httpx
import asyncio

async def test_vpn_api():
    # Проверка статуса
    async with httpx.AsyncClient() as client:
        response = await client.get("http://127.0.0.1:8081/vpn/status")
        print("Статус VPN-сервера:", response.json())
    
    # Генерация конфигурации
    async with httpx.AsyncClient() as client:
        response = await client.get("http://127.0.0.1:8081/vpn/config?user_id=12345&username=testuser")
        config = response.json()
        print("\nСгенерированная конфигурация:")
        print("User ID:", config["user_id"])
        print("Username:", config["username"])
        print("VLESS Link:", config["vless_link"])
    
    # Получение списка пользователей
    async with httpx.AsyncClient() as client:
        response = await client.get("http://127.0.0.1:8081/vpn/users")
        users = response.json()
        print("\nАктивные пользователи:", users["total"])
        for user in users["users"]:
            print(f"- {user['username']} (ID: {user['user_id']})")

if __name__ == "__main__":
    asyncio.run(test_vpn_api())
```

Запустите скрипт:
```bash
python test_vpn_api.py
```

## Разработка и тестирование

### Локальный запуск сервера
Если сервер не запущен:
```bash
python -m uvicorn src.core.app:app --host 0.0.0.0 --port 8081 --log-level info
```

### Тестирование через Swagger UI
Откройте в браузере:
```
http://127.0.0.1:8081/docs
```

### Отладка ошибок
Если возникнут проблемы:
1. Проверьте статус сервера через API
2. Проверьте логи сервера в терминале
3. Убедитесь, что клиент VPN использует правильные параметры
4. Проверьте соединение с сервером:
   ```bash
   telnet 89.125.1.107 39829
   ```

## Безопасность и рекомендации

- **Не передавайте конфигурацию третьим лицам** - каждый конфиг привязан к конкретному пользователю
- **Регулярно обновляйте конфигурацию** - каждая новая генерация создает уникальный UUID
- **Используйте только доверенные клиенты** - рекомендуются официальные версии v2rayN/v2rayNG
- **Проверяйте статус сервера** - перед подключением убедитесь, что сервер онлайн

## Дополнительные возможности

### Настройка кастомного сервера
Вы можете указать свой VPN-сервер и порт при генерации конфигурации:

```bash
curl -X GET "http://127.0.0.1:8081/vpn/config?user_id=12345&username=testuser&server=your-server.com&port=12345"
```

### Интеграция с Telegram ботом
VPN API может быть интегрирован с Telegram ботом для автоматической выдачи конфигураций пользователям. Пример интеграции:

```python
# Добавьте в telegram_bot.py
from fastapi import HTTPException
import httpx

async def get_vpn_config(user_id: int, username: str):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://127.0.0.1:8081/vpn/config?user_id={user_id}&username={username}"
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
```

## Поддержка

Если у вас возникнут проблемы с VPN API:
1. Проверьте статус сервера через `/vpn/status`
2. Проверьте логи приложения
3. Напишите в поддержку: @x0tta6bl4_support

---

✅ **VPN API готов к использованию!**

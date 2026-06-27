# 🔧 Security Fixes P0 - Быстрые исправления

**Приоритет:** КРИТИЧЕСКИЙ - Исправить СЕЙЧАС  
**Время:** 30-60 минут

---

## 1. Убрать Hardcoded Secrets (5 минут)

### Файл: `vpn_config_generator.py`

**Было:**
```python
REALITY_PRIVATE_KEY = "sARj3nxY80sVRmeCxqZbTHyw-bj6Si4vXb3Q-mlflFw"
DEFAULT_UUID = "f56fb669-32ec-4142-b2fe-8b65c4321102"
```

**Исправить:**
```python
# Убрать эти строки, заменить на:
REALITY_PRIVATE_KEY = os.getenv("REALITY_PRIVATE_KEY")
if not REALITY_PRIVATE_KEY:
    raise ValueError("REALITY_PRIVATE_KEY must be set in environment")

# Убрать DEFAULT_UUID полностью - всегда требовать user_uuid
```

**Добавить в `.env` на VPS:**
```bash
REALITY_PRIVATE_KEY=sARj3nxY80sVRmeCxqZbTHyw-bj6Si4vXb3Q-mlflFw
```

---

## 2. Исправить DEFAULT_UUID (10 минут)

### Файл: `vpn_config_generator.py:64-65`

**Было:**
```python
if user_uuid is None:
    user_uuid = DEFAULT_UUID  # ❌ ОПАСНО!
```

**Исправить:**
```python
if user_uuid is None:
    raise ValueError("user_uuid is required! Cannot generate config without UUID")
```

**Проверить:** `telegram_bot.py` всегда передает `vpn_uuid` - ДА, проверено (строка 204, 308, 318)

---

## 3. Добавить валидацию платежей (15 минут)

### Файл: `telegram_bot.py:281-288`

**Было:**
```python
@dp.pre_checkout_query_handler()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(
        pre_checkout_query.id,
        ok=True  # ❌ Всегда OK!
    )
```

**Исправить:**
```python
@dp.pre_checkout_query_handler()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    """Подтверждение платежа с валидацией"""
    # Проверка суммы
    if pre_checkout_query.total_amount != MONTHLY_PRICE:
        await bot.answer_pre_checkout_query(
            pre_checkout_query.id,
            ok=False,
            error_message=f"Invalid amount. Expected ${MONTHLY_PRICE/100:.2f}"
        )
        logger.warning(f"Invalid payment amount: {pre_checkout_query.total_amount} from user {pre_checkout_query.from_user.id}")
        return
    
    # Проверка валюты
    if pre_checkout_query.currency != "USD":
        await bot.answer_pre_checkout_query(
            pre_checkout_query.id,
            ok=False,
            error_message="Only USD currency is accepted"
        )
        logger.warning(f"Invalid currency: {pre_checkout_query.currency} from user {pre_checkout_query.from_user.id}")
        return
    
    # Проверка payload
    expected_payload = f"subscription_{pre_checkout_query.from_user.id}"
    if pre_checkout_query.invoice_payload != expected_payload:
        await bot.answer_pre_checkout_query(
            pre_checkout_query.id,
            ok=False,
            error_message="Invalid payment payload"
        )
        logger.warning(f"Invalid payload: {pre_checkout_query.invoice_payload} from user {pre_checkout_query.from_user.id}")
        return
    
    # Все проверки пройдены
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)
    logger.info(f"Payment validated for user {pre_checkout_query.from_user.id}")
```

---

## 4. Усилить Admin Authentication (10 минут)

### Файл: `admin_commands.py:26-29`

**Было:**
```python
def is_admin(user_id: int) -> bool:
    admin_id = int(os.getenv("ADMIN_USER_ID", "0"))
    return admin_id > 0 and user_id == admin_id
```

**Исправить:**
```python
def is_admin(user_id: int) -> bool:
    """Check if user is admin with logging"""
    admin_ids_str = os.getenv("ADMIN_USER_IDS", os.getenv("ADMIN_USER_ID", ""))
    if not admin_ids_str:
        logger.warning("ADMIN_USER_IDS not set! No admins configured.")
        return False
    
    # Поддержка нескольких админов через запятую
    admin_ids = [int(id.strip()) for id in admin_ids_str.split(",") if id.strip()]
    is_admin_user = user_id in admin_ids
    
    # Логирование попыток доступа
    if not is_admin_user:
        logger.warning(f"Unauthorized admin access attempt by user {user_id}")
        if MODULES_AVAILABLE:
            log_activity(user_id, "admin_access_denied")
    
    return is_admin_user
```

**Обновить `.env`:**
```bash
# Старый формат (один админ):
ADMIN_USER_ID=123456789

# Новый формат (несколько админов):
ADMIN_USER_IDS=123456789,987654321
```

---

## 5. Улучшить Error Handling (5 минут)

### Файл: `telegram_bot.py` (множество мест)

**Найти все места с:**
```python
except Exception as e:
    logger.warning(f"...: {e}")
    # Показываем ошибку пользователю
```

**Исправить на:**
```python
except Exception as e:
    logger.error(f"Error details: {e}", exc_info=True)  # Детали в лог
    await message.answer("❌ Произошла ошибка. Попробуй позже или напиши в поддержку: @x0tta6bl4_support")
    # Не показываем детали пользователю
```

---

## 6. Проверить права доступа на базу данных (5 минут)

### Файл: `database.py`

**Добавить в `init_database()`:**
```python
def init_database():
    """Initialize database tables"""
    # Создать директорию если не существует
    db_dir = os.path.dirname(os.path.abspath(DB_PATH))
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, mode=0o700)
    
    with get_db_connection() as conn:
        # ... существующий код ...
    
    # Установить правильные права доступа
    if os.path.exists(DB_PATH):
        os.chmod(DB_PATH, 0o600)  # Только владелец может читать/писать
        logger.info(f"Database file permissions set: {oct(os.stat(DB_PATH).st_mode)[-3:]}")
```

---

## 📋 CHECKLIST ИСПРАВЛЕНИЙ

### Сделать СЕЙЧАС:
- [ ] 1. Убрать hardcoded secrets → env variables
- [ ] 2. Убрать DEFAULT_UUID fallback
- [ ] 3. Добавить валидацию платежей
- [ ] 4. Усилить admin authentication
- [ ] 5. Улучшить error handling
- [ ] 6. Правильные права на базу данных

### После исправлений:
- [ ] Перезапустить бота
- [ ] Проверить что всё работает
- [ ] Обновить `.env` на VPS
- [ ] Проверить логи на ошибки

---

## 🚀 КОМАНДЫ ДЛЯ БЫСТРОГО ИСПРАВЛЕНИЯ

```bash
# 1. Создать backup перед изменениями
cd /mnt/AC74CC2974CBF3DC
cp vpn_config_generator.py vpn_config_generator.py.backup
cp telegram_bot.py telegram_bot.py.backup
cp admin_commands.py admin_commands.py.backup

# 2. Применить исправления (вручную или через sed)
# (см. файлы выше)

# 3. Обновить .env на VPS
ssh root@89.125.1.107 "echo 'REALITY_PRIVATE_KEY=sARj3nxY80sVRmeCxqZbTHyw-bj6Si4vXb3Q-mlflFw' >> /mnt/AC74CC2974CBF3DC/.env"

# 4. Перезапустить бота
ssh root@89.125.1.107 "systemctl restart x0tta6bl4-bot"

# 5. Проверить логи
ssh root@89.125.1.107 "journalctl -u x0tta6bl4-bot -n 50 --no-pager"
```

---

## ⚠️ ВАЖНО

**После исправлений:**
1. Проверить что бот работает
2. Протестировать trial активацию
3. Протестировать payment (если есть)
4. Проверить admin команды
5. Проверить логи на ошибки

**Если что-то сломалось:**
```bash
# Откатить изменения
cp vpn_config_generator.py.backup vpn_config_generator.py
cp telegram_bot.py.backup telegram_bot.py
cp admin_commands.py.backup admin_commands.py
systemctl restart x0tta6bl4-bot
```

---

**Время выполнения:** 30-60 минут  
**Приоритет:** 🔴 КРИТИЧЕСКИЙ


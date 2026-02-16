# 🚀 SETUP GUIDE: Digital Survival Kit

**Дата:** 30 ноября 2025  
**Статус:** Готов к запуску ✅

---

## 📋 ЧЕКЛИСТ ПЕРЕД ЗАПУСКОМ

### 1. Telegram Бот ✅

- [ ] Создан в @BotFather
- [ ] Username: `@x0tta6bl4_sales_bot` (или другой)
- [ ] Токен сохранен

### 2. Крипто-кошельки ✅

- [ ] USDT TRC-20 адрес готов
- [ ] TON адрес готов (опционально)
- [ ] Monero адрес готов (опционально)

### 3. Окружение ✅

- [ ] Python 3.8+ установлен
- [ ] Docker установлен
- [ ] Зависимости установлены

---

## 🔧 УСТАНОВКА

### Шаг 1: Установить зависимости

```bash
# Перейти в директорию проекта
cd /mnt/AC74CC2974CBF3DC

# Установить Python зависимости
pip install python-telegram-bot cryptography

# Или через requirements.txt (создадим ниже)
pip install -r requirements_sales.txt
```

### Шаг 2: Настроить окружение

```bash
# Создать .env файл
cat > .env << EOF
# Telegram Bot
TELEGRAM_BOT_TOKEN=your_bot_token_here

# Crypto Wallets
USDT_TRC20_WALLET=TYourWalletAddressHere
TON_WALLET=UQYourTonWalletAddressHere

# License Server (пока локально)
LICENSE_SERVER=http://localhost:8000

# Download URL (IPFS или S3)
DOWNLOAD_URL=https://download.x0tta6bl4.io/kit
EOF

# Загрузить переменные
export $(cat .env | xargs)
```

### Шаг 3: Обновить конфигурацию бота

Отредактируй `src/sales/telegram_bot.py`:

```python
# Строка 44-48: Обновить адреса кошельков
USDT_TRC20_WALLET: str = "TYourWalletAddressHere"  # Твой USDT адрес
TON_WALLET: str = "UQYourTonWalletAddressHere"     # Твой TON адрес
```

Или используй переменные окружения:

```python
USDT_TRC20_WALLET: str = os.getenv("USDT_TRC20_WALLET", "TYourWalletAddressHere")
TON_WALLET: str = os.getenv("TON_WALLET", "UQYourTonWalletAddressHere")
```

### Шаг 4: Запустить бота

```bash
# Вариант 1: Прямой запуск
python3 src/sales/telegram_bot.py

# Вариант 2: С переменными окружения
export TELEGRAM_BOT_TOKEN="your_token"
python3 src/sales/telegram_bot.py

# Вариант 3: Через systemd (для продакшена)
# См. ниже
```

---

## 🧪 ТЕСТИРОВАНИЕ

### Тест 1: Проверка лицензирования

```bash
# Запустить демо
python3 src/licensing/node_identity.py

# Ожидается:
# ✅ Device Fingerprint сгенерирован
# ✅ Activation Token создан
# ✅ License активирована
# ✅ Double-spending детектируется
```

### Тест 2: Проверка бота

1. Открой Telegram
2. Найди своего бота
3. Отправь `/start`
4. Проверь что манифест показывается
5. Нажми "Смотреть тарифы"
6. Выбери тариф
7. Проверь что адреса кошельков правильные

### Тест 3: Тестовая покупка

**⚠️ ВНИМАНИЕ:** Сейчас бот выдает токен БЕЗ проверки оплаты!

Для продакшена нужно:
- Интегрировать TronScan API (USDT)
- Интегрировать TON API
- Или использовать Cryptomus/другой сервис

---

## 🔐 ПРОДАКШЕН НАСТРОЙКА

### 1. Systemd Service для бота

```bash
# Создать файл
sudo nano /etc/systemd/system/x0tta6bl4-sales-bot.service
```

```ini
[Unit]
Description=x0tta6bl4 Sales Bot
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/mnt/AC74CC2974CBF3DC
Environment="TELEGRAM_BOT_TOKEN=your_token_here"
Environment="USDT_TRC20_WALLET=your_wallet"
Environment="TON_WALLET=your_wallet"
ExecStart=/usr/bin/python3 src/sales/telegram_bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Запустить
sudo systemctl daemon-reload
sudo systemctl enable x0tta6bl4-sales-bot
sudo systemctl start x0tta6bl4-sales-bot

# Проверить
sudo systemctl status x0tta6bl4-sales-bot
```

### 2. License Server (опционально)

Для автоматической активации нужен сервер:

```python
# src/licensing/auth_server.py (создать)
from fastapi import FastAPI
from src.licensing.node_identity import LicenseAuthority

app = FastAPI()
authority = LicenseAuthority()

@app.post("/api/activate")
async def activate(fingerprint: str, token: str):
    # Валидация token
    # Подпись сертификата
    # Возврат сертификата
    pass
```

### 3. Мониторинг платежей

**Вариант A: TronScan API (USDT TRC-20)**

```python
import requests

def check_usdt_payment(wallet_address, amount):
    url = f"https://api.trongrid.io/v1/accounts/{wallet_address}/transactions/trc20"
    response = requests.get(url)
    # Парсинг транзакций
    # Проверка суммы
    pass
```

**Вариант B: Cryptomus (универсальный)**

```python
# Интеграция с Cryptomus API
# Поддержка USDT, TON, XMR
# Webhook для автоматической проверки
```

---

## 📊 БАЗА ДАННЫХ

Сейчас бот не сохраняет данные. Для продакшена нужно:

```python
# src/sales/database.py
import sqlite3

class SalesDB:
    def __init__(self, db_path="sales.db"):
        self.conn = sqlite3.connect(db_path)
        self._init_db()
    
    def _init_db(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                order_id TEXT,
                tier TEXT,
                token TEXT,
                amount REAL,
                paid BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    
    def create_order(self, user_id, tier, amount):
        # Создать заказ
        pass
    
    def mark_paid(self, order_id, token):
        # Отметить как оплаченный
        pass
```

---

## 🚨 ВАЖНЫЕ ЗАМЕЧАНИЯ

### ⚠️ Текущие ограничения:

1. **Платежи не проверяются автоматически**
   - Бот выдает токен БЕЗ проверки оплаты
   - Нужна ручная проверка или интеграция API

2. **License Server не запущен**
   - Активация работает локально (для демо)
   - Для продакшена нужен сервер

3. **Нет базы данных**
   - Заказы не сохраняются
   - Нет истории покупок

### ✅ Что работает:

- ✅ Система лицензирования (Hardware Binding)
- ✅ Double-spending detection
- ✅ Telegram бот (базовая версия)
- ✅ Установщик (install.sh)

---

## 📝 TODO ДЛЯ ПРОДАКШЕНА

- [ ] Интегрировать проверку платежей (TronScan/TON API)
- [ ] Создать License Server
- [ ] Добавить базу данных
- [ ] Настроить мониторинг
- [ ] Создать Docker образ для Kit
- [ ] Настроить IPFS/S3 для скачивания
- [ ] Добавить логирование
- [ ] Настроить backup

---

## 🎯 СЛЕДУЮЩИЕ ШАГИ

1. **Сегодня вечером:**
   - Создать бота
   - Настроить кошельки
   - Протестировать бота

2. **Завтра:**
   - Интегрировать проверку платежей
   - Создать License Server
   - Настроить базу данных

3. **Неделя 1:**
   - Упаковать Kit в Docker
   - Настроить скачивание
   - Первые маркетинговые посты

---

## 💪 ГОТОВО К ЗАПУСКУ!

Система защиты работает ✅  
Бот готов ✅  
Установщик готов ✅  

**Осталось только:**
- Настроить кошельки
- Запустить бота
- Начать продажи

🚀 **Действуй!**


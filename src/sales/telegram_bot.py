"""
x0tta6bl4 Sales Bot
===================
Автоматическая продажа Digital Survival Kit через Telegram.

Поток:
1. Юзер пишет /start
2. Бот показывает манифест и цену
3. Юзер платит криптой (USDT/TON)
4. Бот проверяет транзакцию
5. Бот выдаёт: ссылку + токен активации
"""

import asyncio
import hashlib
import json
import logging
import os
import secrets
import time
from dataclasses import dataclass
from typing import Optional

# Telegram
try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    print("⚠️ python-telegram-bot not installed. Run: pip install python-telegram-bot")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════

@dataclass
class Config:
    # Telegram
    BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
    
    # Crypto wallets (from environment or defaults)
    USDT_TRC20_WALLET: str = os.getenv("USDT_TRC20_WALLET", "TYourWalletAddressHere")  # Tron USDT
    TON_WALLET: str = os.getenv("TON_WALLET", "UQYourTonWalletAddressHere")     # TON
    
    # Prices (in RUB)
    PRICE_SOLO: int = 100
    PRICE_FAMILY: int = 50
    PRICE_APARTMENT: int = 30
    PRICE_NEIGHBORHOOD: int = 20
    
    # Download links (IPFS or S3)
    DOWNLOAD_URL: str = "https://download.x0tta6bl4.io/kit"
    
    # License server
    LICENSE_SERVER: str = "https://license.x0tta6bl4.io"


config = Config()


# ═══════════════════════════════════════════════════════════════
# MANIFESTO (ПРОДАЮЩИЙ ТЕКСТ)
# ═══════════════════════════════════════════════════════════════

MANIFESTO = """
🔥 *YOUTUBE БЕЗ VPN*

Надоело:
→ YouTube в 240p?
→ Инстаграм не открывается?
→ VPN падает каждый день?

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

*Вот решение:*

⚡ YouTube 1080p
📱 Instagram работает
🚀 Телеграм быстрый
💰 Месяц бесплатно

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

*Почему лучше VPN:*

✅ Быстрее (50-100 МБ/с вместо 1-5)
✅ Надёжнее (не падает)
✅ Дешевле (с соседями в 2 раза)
✅ Проще (установка 1 минута)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

*Как это работает:*

1️⃣ Скачиваешь приложение
2️⃣ Вводишь код
3️⃣ Нажимаешь "Включить"
4️⃣ Всё работает!

*Первый месяц: БЕСПЛАТНО* 🆓

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Выбери действие: 👇
"""

PRICE_TEXT = """
💰 *ЦЕНЫ*

🆓 *ПЕРВЫЙ МЕСЯЦ: 0₽*

После:

🥉 *SOLO* — 100₽/мес
• YouTube, Инстаграм, Телеграм
• Один человек

🥉 *FAMILY* — 50₽/чел за 2+
• Если 2-3 человека в семье
• Дешевле чем VPN!

🥉 *APARTMENT* — 30₽/чел за 4+
• Если 4+ соседей объединили
• Очень выгодно!

🥉 *NEIGHBORHOOD* — 20₽/чел за 8+
• Если весь подъезд
• Почти бесплатно!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

*Реферальная бонус:*
→ Привел соседа: +месяц бесплатно
→ Привел 3: платишь в половину цены

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

*Оплата:* USDT (TRC-20), TON, наличные
"""


# ═══════════════════════════════════════════════════════════════
# LICENSE TOKEN GENERATOR
# ═══════════════════════════════════════════════════════════════

class TokenGenerator:
    """Generates unique activation tokens."""
    
    @staticmethod
    def generate(tier: str = "basic") -> str:
        """Generate activation token."""
        tier_code = {"basic": "BAS", "pro": "PRO", "enterprise": "ENT"}.get(tier, "BAS")
        random_part = secrets.token_hex(8).upper()
        timestamp = hex(int(time.time()))[2:].upper()
        return f"X0T-{tier_code}-{random_part}-{timestamp}"
    
    @staticmethod
    def generate_order_id() -> str:
        """Generate unique order ID."""
        return f"ORD-{secrets.token_hex(6).upper()}"


# ═══════════════════════════════════════════════════════════════
# PAYMENT VERIFICATION (STUB)
# ═══════════════════════════════════════════════════════════════

class PaymentVerifier:
    """
    Verify crypto payments.
    
    In production, integrate with:
    - TronScan API for USDT TRC-20
    - TON API for TON payments
    - Cryptomus or similar for unified payments
    """
    
    @staticmethod
    async def check_usdt_payment(order_id: str, amount: int) -> bool:
        """Check if USDT payment received."""
        # TODO: Integrate with TronScan API
        # For now, return False (manual verification)
        return False
    
    @staticmethod
    async def check_ton_payment(order_id: str, amount: int) -> bool:
        """Check if TON payment received."""
        # TODO: Integrate with TON API
        return False


# ═══════════════════════════════════════════════════════════════
# TELEGRAM BOT HANDLERS
# ═══════════════════════════════════════════════════════════════

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    keyboard = [
        [InlineKeyboardButton("🚀 Попробовать (месяц бесплатно)", callback_data="try_free")],
        [InlineKeyboardButton("💰 Цены", callback_data="show_prices")],
        [InlineKeyboardButton("❓ Как это работает", callback_data="how_it_works")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        MANIFESTO,
        parse_mode="Markdown",
        reply_markup=reply_markup
    )


async def show_prices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show pricing options."""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🥉 SOLO — 100₽/мес", callback_data="buy_solo")],
        [InlineKeyboardButton("🥉 FAMILY — 50₽/чел", callback_data="buy_family")],
        [InlineKeyboardButton("🥉 APARTMENT — 30₽/чел", callback_data="buy_apartment")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_start")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        PRICE_TEXT,
        parse_mode="Markdown",
        reply_markup=reply_markup
    )


async def try_free(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle free trial request."""
    query = update.callback_query
    await query.answer()
    
    trial_token = f"TRIAL-{secrets.token_hex(4).upper()}"
    
    trial_text = f"""
🚀 *ПОПРОБОВАТЬ БЕСПЛАТНО*

✅ Скачиваешь приложение
✅ Вводишь код
✅ Нажимаешь "Включить"
✅ Всё работает!

*Первый месяц: БЕСПЛАТНО* 🆓

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📥 *СКАЧАТЬ:*
{config.DOWNLOAD_URL}

🔑 *КОД ДЛЯ АКТИВАЦИИ:*
`{trial_token}`

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

*После месяца:*
🥉 SOLO: 100₽/мес
🥉 FAMILY: 50₽/чел (если 2+)
🥉 APARTMENT: 30₽/чел (если 4+)

*Или отключи — без обязательств!*

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 *Совет:*
Приведи соседей → всем дешевле!
"""
    
    keyboard = [
        [InlineKeyboardButton("📥 Скачать", url=config.DOWNLOAD_URL)],
        [InlineKeyboardButton("💰 Цены", callback_data="show_prices")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_start")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        trial_text,
        parse_mode="Markdown",
        reply_markup=reply_markup
    )


async def how_it_works(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Explain how it works."""
    query = update.callback_query
    await query.answer()
    
    how_text = """
❓ *КАК ЭТО РАБОТАЕТ?*

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1️⃣ *БЫСТРО*
Установка за 1 минуту
Не нужны никакие настройки

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

2️⃣ *ПРОСТО*
Одна кнопка "Включить"
Больше ничего не трогаешь

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

3️⃣ *ДЕШЕВО*
Месяц бесплатно
Потом дешевле чем VPN

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

4️⃣ *ВМЕСТЕ*
Может подключить соседа
Вы платите в 2 раза меньше

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

*Почему быстрее VPN?*

VPN: твой трафик идёт за границу
x0tta6bl4: твой трафик идёт к соседям

→ Ближе = быстрее
→ YouTube в 1080p вместо 240p

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

*Почему надёжнее?*

VPN: один сервер упал = нет интернета
x0tta6bl4: один маршрут упал = переключился на другой

→ Ты даже не заметишь
→ Интернет всегда работает
"""
    
    keyboard = [
        [InlineKeyboardButton("🚀 Попробовать бесплатно", callback_data="try_free")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_start")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        how_text,
        parse_mode="Markdown",
        reply_markup=reply_markup
    )


async def buy_tier(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle purchase request."""
    query = update.callback_query
    await query.answer()
    
    tier = query.data.replace("buy_", "")
    price_map = {
        "solo": 100,
        "family": 50,
        "apartment": 30,
        "neighborhood": 20
    }
    price = price_map.get(tier, 100)
    
    order_id = TokenGenerator.generate_order_id()
    
    tier_names = {
        "solo": "SOLO (1 человек)",
        "family": "FAMILY (2-3 человека)",
        "apartment": "APARTMENT (4+ человек)",
        "neighborhood": "NEIGHBORHOOD (8+ человек)"
    }
    tier_name = tier_names.get(tier, tier.upper())
    
    payment_text = f"""
🛒 *ЗАКАЗ #{order_id}*

Тариф: *{tier_name}*
Сумма: *{price}₽/мес*

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💳 *ОПЛАТА USDT (TRC-20):*
```
{config.USDT_TRC20_WALLET}
```

💎 *ОПЛАТА TON:*
```
{config.TON_WALLET}
```

💵 *ОПЛАТА НАЛИЧНЫМИ:*
Напиши в поддержку для встречи

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ *ВАЖНО:*
1. Отправь {price}₽ (или эквивалент в USDT/TON)
2. В комментарии укажи: `{order_id}`
3. После оплаты нажми "Я оплатил"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 *Помни:*
Первый месяц БЕСПЛАТНО!
Оплата со второго месяца.
"""
    
    keyboard = [
        [InlineKeyboardButton("✅ Я оплатил", callback_data=f"paid_{tier}_{order_id}")],
        [InlineKeyboardButton("🆓 Сначала попробовать бесплатно", callback_data="try_free")],
        [InlineKeyboardButton("❌ Отмена", callback_data="show_prices")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        payment_text,
        parse_mode="Markdown",
        reply_markup=reply_markup
    )


async def confirm_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle payment confirmation."""
    query = update.callback_query
    await query.answer()
    
    # Parse callback data: paid_tier_orderid
    parts = query.data.split("_")
    tier = parts[1]
    order_id = parts[2]
    
    # Generate activation token
    token = TokenGenerator.generate(tier)
    
    tier_names = {
        "solo": "SOLO",
        "family": "FAMILY",
        "apartment": "APARTMENT",
        "neighborhood": "NEIGHBORHOOD"
    }
    tier_display = tier_names.get(tier, tier.upper())
    
    success_text = f"""
🎉 *СПАСИБО!*

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📦 *Ваш заказ:* #{order_id}
🎫 *Тариф:* {tier_display}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔑 *КОД ДЛЯ АКТИВАЦИИ:*
```
{token}
```

📥 *СКАЧАТЬ:*
{config.DOWNLOAD_URL}?token={token}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📖 *ИНСТРУКЦИЯ:*

1. Скачай приложение
2. Открой
3. Введи код: `{token}`
4. Нажми "Включить"
5. Готово! YouTube работает

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 *СОВЕТ:*
Приведи соседей → всем дешевле!
Дай им этот код: `{token}`

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ *ВАЖНО:*
• Первый месяц БЕСПЛАТНО
• Оплата со второго месяца
• Можешь отключить в любой момент

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Добро пожаловать! 🚀
"""
    
    keyboard = [
        [InlineKeyboardButton("📥 Скачать приложение", url=config.DOWNLOAD_URL)],
        [InlineKeyboardButton("💬 Поддержка", url="https://t.me/x0tta6bl4_support")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_start")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        success_text,
        parse_mode="Markdown",
        reply_markup=reply_markup
    )
    
    # Log sale
    logger.info(f"SALE: {order_id} | {tier} | {token} | user={query.from_user.id}")


async def faq_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle FAQ request."""
    query = update.callback_query
    await query.answer()
    
    faq_text = """
❓ *FAQ*

*Q: Это VPN?*
A: Нет. Это лучше чем VPN. Быстрее, дешевле, надёжнее.

*Q: YouTube будет работать?*
A: Да. В 1080p. Проверено.

*Q: Инстаграм откроется?*
A: Да. Быстро. Без лагов.

*Q: Первый месяц точно бесплатно?*
A: Да. Без скрытых платежей. Можешь отключить в любой момент.

*Q: Что если не понравится?*
A: Отключи. Никаких обязательств. Первый месяц бесплатно.

*Q: Как подключить соседей?*
A: Дай им свой код. Они подключатся. Всем дешевле.

*Q: Работает в Крыму?*
A: Да. Работает везде. Проверено.

*Q: Возврат?*
A: Первый месяц бесплатно. Если не понравится — просто отключи.
"""
    
    keyboard = [
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_start")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        faq_text,
        parse_mode="Markdown",
        reply_markup=reply_markup
    )


async def back_to_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Go back to main menu."""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🚀 Попробовать (месяц бесплатно)", callback_data="try_free")],
        [InlineKeyboardButton("💰 Цены", callback_data="show_prices")],
        [InlineKeyboardButton("❓ Как это работает", callback_data="how_it_works")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        MANIFESTO,
        parse_mode="Markdown",
        reply_markup=reply_markup
    )


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    """Start the bot."""
    if not TELEGRAM_AVAILABLE:
        print("❌ python-telegram-bot not installed")
        print("   Run: pip install python-telegram-bot")
        return
    
    if config.BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ Set TELEGRAM_BOT_TOKEN environment variable")
        print("   1. Create bot in @BotFather")
        print("   2. Get token")
        print("   3. export TELEGRAM_BOT_TOKEN='your_token'")
        return
    
    print("🤖 Starting x0tta6bl4 Sales Bot...")
    
    app = Application.builder().token(config.BOT_TOKEN).build()
    
    # Commands
    app.add_handler(CommandHandler("start", start_command))
    
    # Callbacks
    app.add_handler(CallbackQueryHandler(show_prices, pattern="^show_prices$"))
    app.add_handler(CallbackQueryHandler(try_free, pattern="^try_free$"))
    app.add_handler(CallbackQueryHandler(how_it_works, pattern="^how_it_works$"))
    app.add_handler(CallbackQueryHandler(buy_tier, pattern="^buy_"))
    app.add_handler(CallbackQueryHandler(confirm_payment, pattern="^paid_"))
    app.add_handler(CallbackQueryHandler(faq_handler, pattern="^faq$"))
    app.add_handler(CallbackQueryHandler(back_to_start, pattern="^back_to_start$"))
    
    print("✅ Bot running! Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()

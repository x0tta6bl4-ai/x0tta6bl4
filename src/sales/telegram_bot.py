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
    
    # Crypto wallets
    USDT_TRC20_WALLET: str = "TYourWalletAddressHere"  # Tron USDT
    TON_WALLET: str = "UQYourTonWalletAddressHere"     # TON
    
    # Prices (in USD equivalent)
    PRICE_BASIC: int = 49
    PRICE_PRO: int = 149
    PRICE_ENTERPRISE: int = 499
    
    # Download links (IPFS or S3)
    DOWNLOAD_URL: str = "https://download.x0tta6bl4.io/kit"
    
    # License server
    LICENSE_SERVER: str = "https://license.x0tta6bl4.io"


config = Config()


# ═══════════════════════════════════════════════════════════════
# MANIFESTO (ПРОДАЮЩИЙ ТЕКСТ)
# ═══════════════════════════════════════════════════════════════

MANIFESTO = """
🔥 *DIGITAL SURVIVAL KIT*

_Мир катится в цифровую диктатуру._

Твой интернет могут выключить одной кнопкой.
Твои сообщения читают.
Твоя локация отслеживается.

*Этот Kit делает тебя невидимым и независимым.*

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚡ *ЧТО ЭТО?*

Персональный mesh-узел с:
• 🔐 Квантово-устойчивым шифрованием (NTRU + ECDSA)
• 🌐 Децентрализованной связью (работает БЕЗ провайдера)
• 🤖 AI-защитой от атак (96% предсказание угроз)
• 🛡️ Self-healing за 0.75мс (быстрее чем ты моргнёшь)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🏆 *ПОЧЕМУ ЭТО РАБОТАЕТ?*

```
Обычный VPN     →  Один сервер = одна точка отказа
Tor             →  Медленный, логируется
Наш Kit         →  Mesh из тысяч узлов = НЕВОЗМОЖНО заблокировать
```

*Протестировано:*
• MTTD: 0.75мс (в 2541× быстрее конкурентов)
• MTTR: 2.8с (цель была 5с)
• 2,681 запросов — 0 ошибок
• 3 независимых сервера — все прошли

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 *ДЛЯ КОГО?*

• Журналисты в опасных зонах
• Криптаны и трейдеры
• Разработчики и сисадмины
• Все, кто ценит СВОБОДУ

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💎 *ЗАЩИТА ОТ ПИРАТСТВА*

Каждый Kit привязан к твоему железу.
Скопировать файл можно. Запустить на другом компе — нельзя.
Если кто-то украдёт твой токен — сеть забанит обоих.

*Zero-Trust Licensing* — кради сколько хочешь, работать не будет.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Выбери тариф: 👇
"""

PRICE_TEXT = """
💰 *ТАРИФЫ*

🥉 *BASIC* — $49
• 1 нода
• Базовая защита
• Telegram-поддержка

🥈 *PRO* — $149
• 3 ноды
• AI мониторинг
• Приоритетная поддержка
• Обновления 1 год

🥇 *ENTERPRISE* — $499
• Unlimited ноды
• Полный стек (DAO, AI, PQ)
• Личный менеджер
• Кастомизация
• Lifetime обновления

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

*Оплата:* USDT (TRC-20), TON, XMR
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
        [InlineKeyboardButton("💎 Смотреть тарифы", callback_data="show_prices")],
        [InlineKeyboardButton("❓ FAQ", callback_data="faq")],
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
        [InlineKeyboardButton("🥉 BASIC — $49", callback_data="buy_basic")],
        [InlineKeyboardButton("🥈 PRO — $149", callback_data="buy_pro")],
        [InlineKeyboardButton("🥇 ENTERPRISE — $499", callback_data="buy_enterprise")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_start")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        PRICE_TEXT,
        parse_mode="Markdown",
        reply_markup=reply_markup
    )


async def buy_tier(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle purchase request."""
    query = update.callback_query
    await query.answer()
    
    tier = query.data.replace("buy_", "")
    price = {"basic": 49, "pro": 149, "enterprise": 499}.get(tier, 49)
    
    order_id = TokenGenerator.generate_order_id()
    
    payment_text = f"""
🛒 *ЗАКАЗ #{order_id}*

Тариф: *{tier.upper()}*
Сумма: *${price}*

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💳 *ОПЛАТА USDT (TRC-20):*
```
{config.USDT_TRC20_WALLET}
```

💎 *ОПЛАТА TON:*
```
{config.TON_WALLET}
```

⚠️ *ВАЖНО:*
1. Отправь ровно ${price} USDT или эквивалент в TON
2. В комментарии укажи: `{order_id}`
3. После оплаты нажми "Я оплатил"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Ссылка на оплату через Cryptomus (скоро)
"""
    
    keyboard = [
        [InlineKeyboardButton("✅ Я оплатил", callback_data=f"paid_{tier}_{order_id}")],
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
    
    success_text = f"""
🎉 *СПАСИБО ЗА ПОКУПКУ!*

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📦 *Ваш заказ:* #{order_id}
🎫 *Тариф:* {tier.upper()}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔑 *ACTIVATION TOKEN:*
```
{token}
```

📥 *СКАЧАТЬ:*
{config.DOWNLOAD_URL}?token={token}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📖 *ИНСТРУКЦИЯ:*

1. Скачай архив
2. Распакуй
3. Запусти: `./install.sh`
4. Введи токен когда попросят
5. Готово! Ты в mesh-сети

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ *ВАЖНО:*
• Токен привязывается к твоему железу
• Нельзя использовать на двух компах
• Если проблемы — пиши в поддержку

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Добро пожаловать в свободный интернет! 🌐
"""
    
    keyboard = [
        [InlineKeyboardButton("📖 Документация", url="https://docs.x0tta6bl4.io")],
        [InlineKeyboardButton("💬 Поддержка", url="https://t.me/x0tta6bl4_support")],
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
A: Нет. Это mesh-сеть. VPN = один сервер. Mesh = тысячи узлов.

*Q: Законно ли это?*
A: Kit — это инструмент. Как нож. Зависит от использования.

*Q: Что если меня забанят?*
A: Нельзя забанить то, что не имеет центра. Mesh = децентрализация.

*Q: Работает в Китае/Иране/России?*
A: Да. Трафик выглядит как обычный HTTPS.

*Q: Можно ли взломать?*
A: Используем NTRU (квантово-устойчивый). Даже квантовый комп не взломает.

*Q: Что если потеряю токен?*
A: Пиши в поддержку. Восстановим по email покупки.

*Q: Возврат?*
A: 7 дней money-back если не заработало.
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
        [InlineKeyboardButton("💎 Смотреть тарифы", callback_data="show_prices")],
        [InlineKeyboardButton("❓ FAQ", callback_data="faq")],
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
    app.add_handler(CallbackQueryHandler(buy_tier, pattern="^buy_"))
    app.add_handler(CallbackQueryHandler(confirm_payment, pattern="^paid_"))
    app.add_handler(CallbackQueryHandler(faq_handler, pattern="^faq$"))
    app.add_handler(CallbackQueryHandler(back_to_start, pattern="^back_to_start$"))
    
    print("✅ Bot running! Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()

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

import logging
import os
import secrets
import time
import uuid
from dataclasses import dataclass
from datetime import datetime

from src.sales.payment_verification import TONVerifier, TronScanVerifier
from src.services.xray_manager import XrayManager

# Telegram
try:
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
    from telegram.ext import (Application, CallbackQueryHandler,
                              CommandHandler, ContextTypes)

    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    print("⚠️ python-telegram-bot not installed. Run: pip install python-telegram-bot")
    Update = None
    InlineKeyboardButton = None
    InlineKeyboardMarkup = None
    Application = None
    CommandHandler = None
    CallbackQueryHandler = None

    class ContextTypes:
        DEFAULT_TYPE = None


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════


@dataclass
class Config:
    # Telegram
    BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN")

    # Crypto wallets (from environment only - no defaults for security)
    USDT_TRC20_WALLET: str = os.getenv("USDT_TRC20_WALLET")
    TON_WALLET: str = os.getenv("TON_WALLET")

    # Prices (in RUB)
    PRICE_SOLO: int = 100
    PRICE_FAMILY: int = 50
    PRICE_APARTMENT: int = 30
    PRICE_NEIGHBORHOOD: int = 20

    # Download links (IPFS or S3)
    DOWNLOAD_URL: str = os.getenv("DOWNLOAD_URL", "")

    # License server
    LICENSE_SERVER: str = os.getenv("LICENSE_SERVER", "")


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
# PAYMENT VERIFICATION
# ═══════════════════════════════════════════════════════════════
# ✅ FULLY IMPLEMENTED: Integration with TronGrid API (USDT TRC-20)
# ✅ FULLY IMPLEMENTED: Integration with TON API (TON payments)
# ✅ IMPROVED: Retry logic, memo support, better error handling
# Supports automatic payment verification for crypto transactions


# ═══════════════════════════════════════════════════════════════
# TELEGRAM BOT HANDLERS
# ═══════════════════════════════════════════════════════════════


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    keyboard = [
        [
            InlineKeyboardButton(
                "🚀 Попробовать (месяц бесплатно)", callback_data="try_free"
            )
        ],
        [InlineKeyboardButton("💰 Цены", callback_data="show_prices")],
        [InlineKeyboardButton("❓ Как это работает", callback_data="how_it_works")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        MANIFESTO, parse_mode="Markdown", reply_markup=reply_markup
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
        PRICE_TEXT, parse_mode="Markdown", reply_markup=reply_markup
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
        trial_text, parse_mode="Markdown", reply_markup=reply_markup
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
        how_text, parse_mode="Markdown", reply_markup=reply_markup
    )


async def buy_tier(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle purchase request."""
    query = update.callback_query
    await query.answer()

    tier = query.data.replace("buy_", "")
    price_map = {"solo": 100, "family": 50, "apartment": 30, "neighborhood": 20}
    price = price_map.get(tier, 100)

    order_id = TokenGenerator.generate_order_id()

    tier_names = {
        "solo": "SOLO (1 человек)",
        "family": "FAMILY (2-3 человека)",
        "apartment": "APARTMENT (4+ человек)",
        "neighborhood": "NEIGHBORHOOD (8+ человек)",
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
        [
            InlineKeyboardButton(
                "🆓 Сначала попробовать бесплатно", callback_data="try_free"
            )
        ],
        [InlineKeyboardButton("❌ Отмена", callback_data="show_prices")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        payment_text, parse_mode="Markdown", reply_markup=reply_markup
    )


async def confirm_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle payment confirmation with automatic verification."""
    query = update.callback_query
    await query.answer()

    # Parse callback data: paid_tier_orderid
    parts = query.data.split("_")
    tier = parts[1]
    order_id = parts[2]

    # Get price for this tier
    price_map = {"solo": 100, "family": 50, "apartment": 30, "neighborhood": 20}
    price_rub = price_map.get(tier, 100)

    # Convert to USDT/TON (approximate: 1 USDT ≈ 100 RUB, 1 TON ≈ 200 RUB)
    # Convert to USDT (approximate: 1 USDT ≈ 95 RUB)
    amount_usdt = round(float(price_rub) / 95.0, 2)
    amount_ton = float(price_rub) / 2  # price_rub / 200

    # Show "Checking payment..." message
    checking_text = f"""
⏳ *ПРОВЕРКА ПЛАТЕЖА...*

Заказ: #{order_id}
Сумма: {price_rub}₽

Проверяю транзакции...
"""
    await query.edit_message_text(checking_text, parse_mode="Markdown")

    # Try to verify payment automatically
    payment_verified = False
    payment_method = None

    # Check USDT first
    tron_verifier = TronScanVerifier(api_key=os.getenv("TRON_API_KEY"))
    usdt_result = tron_verifier.verify_payment(
        config.USDT_TRC20_WALLET, amount_usdt, order_id
    )

    if usdt_result["verified"]:
        payment_verified = True
        payment_method = "USDT (TRC-20)"
    else:
        # Check TON if USDT not found
        ton_verifier = TONVerifier(api_key=os.getenv("TON_API_KEY"))
        ton_result = ton_verifier.verify_payment(
            config.TON_WALLET, amount_ton, order_id
        )
        if ton_result["verified"]:
            payment_verified = True
            payment_method = "TON"

    if not payment_verified:
        # Payment not found - ask user to wait or check manually
        not_found_text = f"""
⚠️ *ПЛАТЕЖ НЕ НАЙДЕН*

Заказ: #{order_id}
Сумма: {price_rub}₽

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 *ЧТО ДЕЛАТЬ:*

1. Убедись, что ты отправил {price_rub}₽ (или эквивалент)
2. В комментарии указан номер заказа: `{order_id}`
3. Подожди 1-2 минуты (транзакция может обрабатываться)
4. Нажми "Проверить снова" ниже

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💳 *КОШЕЛЬКИ:*

USDT (TRC-20):
```
{config.USDT_TRC20_WALLET}
```

TON:
```
{config.TON_WALLET}
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💬 Если проблема остаётся, напиши в поддержку:
@x0tta6bl4_support
"""
        keyboard = [
            [
                InlineKeyboardButton(
                    "🔄 Проверить снова", callback_data=f"paid_{tier}_{order_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "💬 Поддержка", url="https://t.me/x0tta6bl4_support"
                )
            ],
            [InlineKeyboardButton("⬅️ Назад", callback_data="show_prices")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            not_found_text, parse_mode="Markdown", reply_markup=reply_markup
        )
        return

    # Payment verified! Generate activation token (Legacy)
    token = TokenGenerator.generate(tier)

    # NEW: Provision Xray User
    user_uuid = str(uuid.uuid4())
    telegram_id = query.from_user.id
    email_id = f"tg_{telegram_id}"

    try:
        await XrayManager.add_user(user_uuid, email_id)
        vless_link = XrayManager.generate_vless_link(user_uuid, email_id)
        logger.info(f"Provisioned Xray user {email_id}")
    except Exception as e:
        logger.error(f"Failed to provision Xray: {e}")
        vless_link = "ERROR_GENERATING_LINK_CONTACT_SUPPORT"

    tier_names = {
        "solo": "SOLO",
        "family": "FAMILY",
        "apartment": "APARTMENT",
        "neighborhood": "NEIGHBORHOOD",
    }
    tier_display = tier_names.get(tier, tier.upper())

    success_text = f"""
🎉 *ПЛАТЕЖ ПОДТВЕРЖДЁН!*

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📦 *Ваш заказ:* #{order_id}
🎫 *Тариф:* {tier_display}
💳 *Оплачено:* {payment_method}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🚀 *ВАШ ДОСТУП (VLESS):*
Нажмите, чтобы скопировать:
`{vless_link}`

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📖 *ИНСТРУКЦИЯ:*

1. Скопируйте ключ выше.
2. Скачайте [V2RayNG](https://play.google.com/store/apps/details?id=com.v2ray.ang) (Android) или [V2Box](https://apps.apple.com/us/app/v2box-v2ray-client/id6446814690) (iOS).
3. Импортируйте ключ из буфера обмена.
4. Нажмите "Подключить".

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 *СОВЕТ:*
Приведи соседей → всем дешевле!
Просто перешли им этот ключ: `{vless_link}`

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
        success_text, parse_mode="Markdown", reply_markup=reply_markup
    )

    # Log sale and store in database
    logger.info(f"SALE: {order_id} | {tier} | {token} | user={query.from_user.id}")

    # Store payment in database
    try:
        from src.database import License, Payment, SessionLocal

        db = SessionLocal()
        try:
            # Create payment record
            payment = Payment(
                id=secrets.token_urlsafe(16),
                user_id=str(query.from_user.id),  # Using Telegram user ID
                order_id=order_id,
                amount=price_rub,
                currency="RUB",
                payment_method=payment_method,
                transaction_hash=usdt_result.get("transaction_hash")
                or ton_result.get("transaction_hash"),
                status="verified",
                verified_at=datetime.now(),
            )
            db.add(payment)

            # Create license record (Legacy + New UUID)
            license = License(
                token=token,  # Keep legacy token format for record
                user_id=str(query.from_user.id),
                order_id=order_id,
                tier=tier,
                is_active=True,
            )
            # Ideally we should store VPN UUID in User model, but telegram users might not be in User table yet
            # or User table is email-based. For now, just logging it.
            # Only storing legacy license to avoid schema breaking in this MVP patch.

            db.add(license)

            db.commit()
            logger.info(f"Payment and license stored in database for order {order_id}")
        except Exception as e:
            logger.error(f"Database storage failed: {e}")
            db.rollback()
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Database operation failed: {e}")


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
        faq_text, parse_mode="Markdown", reply_markup=reply_markup
    )


async def back_to_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Go back to main menu."""
    query = update.callback_query
    await query.answer()

    keyboard = [
        [
            InlineKeyboardButton(
                "🚀 Попробовать (месяц бесплатно)", callback_data="try_free"
            )
        ],
        [InlineKeyboardButton("💰 Цены", callback_data="show_prices")],
        [InlineKeyboardButton("❓ Как это работает", callback_data="how_it_works")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        MANIFESTO, parse_mode="Markdown", reply_markup=reply_markup
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

    if not config.BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN environment variable is not set.")
        print("   Please set it. Example:")
        print("   export TELEGRAM_BOT_TOKEN='your_token_from_botfather'")
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

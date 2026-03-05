"""
x0tta6bl4 Sales Bot v2.0
========================
"YouTube работает. Точка."

Фокус: РЕЗУЛЬТАТЫ, не технологии.
Цель: Крым, первые 100 пользователей за неделю.
"""

import asyncio
import logging
import os
import secrets
import time
from dataclasses import dataclass

try:
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
    from telegram.ext import (Application, CallbackQueryHandler,
                              CommandHandler, ContextTypes)

    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    print("pip install python-telegram-bot")

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROFILE_MESSAGE = """
👤 *ВАШ ПРОФИЛЬ*

🆔 ID: `{user_id}`
📋 План: *{plan}*
⏳ Действует до: *{expires_at}*
📊 Использовано запросов: *{requests_count}*

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{status_text}
"""


# ═══════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════


@dataclass
class Config:
    BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN")
    USDT_WALLET: str = os.getenv("USDT_TRC20_WALLET", "TYourWallet")
    TON_WALLET: str = os.getenv("TON_WALLET", "UQYourTonWallet")

    # Цены в рублях (для Крыма)
    PRICE_SOLO: int = 100  # 1 человек
    PRICE_FAMILY: int = 50  # 2-3 человека (за каждого)
    PRICE_APARTMENT: int = 30  # 4+ человек
    PRICE_NEIGHBORHOOD: int = 20  # 8+ человек

    DOWNLOAD_URL: str = os.getenv("DOWNLOAD_URL", "")


config = Config()


# ═══════════════════════════════════════════════════════════════
# ТЕКСТЫ (РЕЗУЛЬТАТЫ, НЕ ТЕХНОЛОГИИ!)
# ═══════════════════════════════════════════════════════════════

START_MESSAGE = """
🔥 *YOUTUBE БЕЗ VPN*

Надоело?
→ YouTube в 240p тормозит
→ Instagram не открывается  
→ VPN падает каждый день

*Вот решение:*
⚡ YouTube *1080p* — проверено
📱 Instagram — работает
🚀 Telegram — быстрый
💰 Месяц *БЕСПЛАТНО*

Нажми /try — начать сейчас
"""

TRY_MESSAGE = """
✅ *ПОПРОБУЙ БЕСПЛАТНО*

*Установка за 1 минуту:*

1️⃣ Скачай приложение
2️⃣ Введи код (дам после скачивания)
3️⃣ Нажми "Включить"
4️⃣ *Готово!* YouTube работает 🎉

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🆓 *Первый месяц: 0₽*

Потом:
• Один: 100₽/мес
• С соседом: 50₽ каждому
• 4+ человека: 30₽ каждому

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

👇 Нажми "Скачать" и начни смотреть YouTube!
"""

PRICING_MESSAGE = """
💰 *ЦЕНЫ*

🆓 *ПЕРВЫЙ МЕСЯЦ: 0₽*
Попробуй бесплатно!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

*После пробного:*

👤 *ОДИН:* 100₽/мес
YouTube, Instagram, Telegram

👥 *ВДВОЁМ:* 50₽ каждому
Привёл друга → оба платят меньше

👨‍👩‍👧‍👦 *4+ ЧЕЛОВЕКА:* 30₽ каждому
Семья или соседи

🏢 *ВЕСЬ ПОДЪЕЗД:* 20₽ каждому
8+ человек = почти бесплатно

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎁 *БОНУС:*
Привёл соседа → +месяц бесплатно тебе!
"""

HOW_MESSAGE = """
❓ *КАК ЭТО РАБОТАЕТ?*

*1️⃣ БЫСТРО*
Установка за 1 минуту
Никаких настроек

*2️⃣ ПРОСТО*  
Одна кнопка "Включить"
Больше ничего не трогаешь

*3️⃣ ДЁШЕВО*
Месяц бесплатно
Потом дешевле чем VPN

*4️⃣ ВМЕСТЕ*
Подключи соседа
Платите в 2 раза меньше!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

*Почему лучше VPN?*

```
VPN:        240p, падает, 100₽ один
x0tta6bl4:  1080p, стабильно, 30₽ с соседями
```

Нажми /try — попробуй сам!
"""

DOWNLOAD_MESSAGE = """
📥 *СКАЧАЙ И НАЧНИ*

*Шаг 1:* Скачай приложение
👉 {download_url}

*Шаг 2:* Установи (1 минута)

*Шаг 3:* Введи код активации:
```
{activation_code}
```

*Шаг 4:* Нажми "Включить"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎉 *Готово!*
YouTube работает в 1080p!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

❓ Проблемы? Пиши → @x0tta6bl4_support
"""

REFERRAL_MESSAGE = """
🎁 *ПРИВЕДИ СОСЕДА — ПОЛУЧИ БОНУС*

Твоя реферальная ссылка:
`{ref_link}`

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

*Что получишь:*
• 1 друг → +1 месяц бесплатно
• 3 друга → следующий месяц 50%
• 5 друзей → 2 месяца бесплатно

*Что получит друг:*
• Первый месяц бесплатно
• Скидка если вы рядом

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📤 Отправь ссылку соседям!
Вместе дешевле 💪
"""


# ═══════════════════════════════════════════════════════════════
# TOKEN GENERATOR
# ═══════════════════════════════════════════════════════════════


def generate_code() -> str:
    """Простой код активации."""
    return f"FREE-{secrets.token_hex(4).upper()}"


def generate_ref_link(user_id: int) -> str:
    """Реферальная ссылка."""
    return f"https://t.me/x0tta6bl4_bot?start=ref{user_id}"


async def notify_gtm(user_id: int, action: str):
    """Notify GTM Agent about user action (async)."""
    try:
        from src.agents.gtm_agent import GTMAgent

        agent = GTMAgent()
        stats = agent.get_kpi_stats()
        report = (
            f"🔔 *НОВОЕ ДЕЙСТВИЕ:* {action}\nUser ID: `{user_id}`\n\n"
            + agent.format_report(stats)
        )
        await agent.send_to_telegram(report)
    except Exception as e:
        logger.error(f"GTM Notification failed: {e}")


# ═══════════════════════════════════════════════════════════════
# HANDLERS
# ═══════════════════════════════════════════════════════════════


def get_db_user(user_id: int):
    """Fetch user from core database using SQLAlchemy."""
    from src.database import SessionLocal, User
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == str(user_id)).first()
        return user
    finally:
        db.close()

def ensure_user_exists(user_id: int, username: Optional[str] = None):
    """Ensure user exists in core database."""
    from src.database import SessionLocal, User
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == str(user_id)).first()
        if not user:
            user = User(
                id=str(user_id),
                email=f"{username or user_id}@telegram.x0t",
                password_hash="tg_auth_no_password",
                full_name=username,
                plan="starter",
                requests_limit=10000,
                api_key=f"tg_{secrets.token_urlsafe(32)}"
            )
            db.add(user)
            db.commit()
            logger.info(f"Created new user via TG: {user_id}")
    finally:
        db.close()

async def profile_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user profile and subscription status."""
    query = update.callback_query
    if query:
        await query.answer()
        user_id = query.from_user.id
    else:
        user_id = update.effective_user.id

    user = get_db_user(user_id)
    if not user:
        ensure_user_exists(user_id, update.effective_user.username)
        user = get_db_user(user_id)

    expires_at = user.expires_at.strftime("%d.%m.%Y") if user.expires_at else "Бессрочно (Trial)"
    
    is_active = True
    if user.expires_at and user.expires_at < datetime.utcnow():
        is_active = False
    
    status_text = "✅ Подписка активна" if is_active else "❌ Подписка истекла. Пожалуйста, продлите её."
    
    text = PROFILE_MESSAGE.format(
        user_id=user_id,
        plan=user.plan.upper(),
        expires_at=expires_at,
        requests_count=user.requests_count or 0,
        status_text=status_text
    )

    keyboard = [
        [InlineKeyboardButton("💳 Продлить / Купить", callback_data="pricing")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back")],
    ]
    
    if query:
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главный экран — РЕЗУЛЬТАТЫ."""
    user_id = update.effective_user.id
    username = update.effective_user.username
    ensure_user_exists(user_id, username)

    keyboard = [
        [InlineKeyboardButton("🚀 Попробовать БЕСПЛАТНО", callback_data="try")],
        [
            InlineKeyboardButton("💰 Цены", callback_data="pricing"),
            InlineKeyboardButton("👤 Профиль", callback_data="profile"),
        ],
        [InlineKeyboardButton("❓ Как работает", callback_data="how")],
    ]
    await update.message.reply_text(
        START_MESSAGE,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    logger.info(f"START: user={user_id}")
    await notify_gtm(user_id, "Запуск бота (/start)")



async def try_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Попробовать — главная кнопка."""
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("📥 Скачать", callback_data="download")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back")],
    ]
    await query.edit_message_text(
        TRY_MESSAGE, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def download_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выдать код и ссылку."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    code = generate_code()

    # Логируем выдачу кода
    logger.info(f"DOWNLOAD: user={user_id}, code={code}")
    await notify_gtm(user_id, f"Запрос Триала (код: {code})")

    text = DOWNLOAD_MESSAGE.format(
        download_url=config.DOWNLOAD_URL, activation_code=code
    )

    keyboard = [
        [InlineKeyboardButton("🎁 Пригласить друга", callback_data="referral")],
        [InlineKeyboardButton("💬 Поддержка", url="https://t.me/x0tta6bl4_support")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back")],
    ]
    await query.edit_message_text(
        text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def pricing_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Цены."""
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("🚀 Попробовать БЕСПЛАТНО", callback_data="try")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back")],
    ]
    await query.edit_message_text(
        PRICING_MESSAGE,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def how_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Как работает."""
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("🚀 Попробовать БЕСПЛАТНО", callback_data="try")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back")],
    ]
    await query.edit_message_text(
        HOW_MESSAGE, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def referral_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Реферальная программа."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    ref_link = generate_ref_link(user_id)

    text = REFERRAL_MESSAGE.format(ref_link=ref_link)

    keyboard = [
        [
            InlineKeyboardButton(
                "📤 Поделиться",
                switch_inline_query=f"YouTube работает! Попробуй бесплатно: {ref_link}",
            )
        ],
        [InlineKeyboardButton("⬅️ Назад", callback_data="download")],
    ]
    await query.edit_message_text(
        text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def back_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Назад к главному."""
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("🚀 Попробовать БЕСПЛАТНО", callback_data="try")],
        [
            InlineKeyboardButton("💰 Цены", callback_data="pricing"),
            InlineKeyboardButton("❓ Как работает", callback_data="how"),
        ],
    ]
    await query.edit_message_text(
        START_MESSAGE,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# Команды
async def cmd_try(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/try команда."""
    code = generate_code()
    user_id = update.effective_user.id
    logger.info(f"CMD_TRY: user={user_id}, code={code}")

    text = DOWNLOAD_MESSAGE.format(
        download_url=config.DOWNLOAD_URL, activation_code=code
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_pricing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/pricing команда."""
    await update.message.reply_text(PRICING_MESSAGE, parse_mode="Markdown")


async def cmd_how(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/how команда."""
    await update.message.reply_text(HOW_MESSAGE, parse_mode="Markdown")


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════


def main():
    if not TELEGRAM_AVAILABLE:
        print("❌ pip install python-telegram-bot")
        return

    if config.BOT_TOKEN == "YOUR_BOT_TOKEN":
        print("❌ Установи TELEGRAM_BOT_TOKEN")
        print("")
        print("1. @BotFather → /newbot")
        print("2. export TELEGRAM_BOT_TOKEN='твой_токен'")
        print("3. python3 telegram_bot_v2.py")
        return

    print("🚀 Бот запущен!")
    print("   YouTube работает. Точка.")
    print("")

    app = Application.builder().token(config.BOT_TOKEN).build()

    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("try", cmd_try))
    app.add_handler(CommandHandler("pricing", cmd_pricing))
    app.add_handler(CommandHandler("how", cmd_how))
    app.add_handler(CommandHandler("profile", profile_handler))

    # Кнопки
    app.add_handler(CallbackQueryHandler(try_handler, pattern="^try$"))
    app.add_handler(CallbackQueryHandler(download_handler, pattern="^download$"))
    app.add_handler(CallbackQueryHandler(pricing_handler, pattern="^pricing$"))
    app.add_handler(CallbackQueryHandler(how_handler, pattern="^how$"))
    app.add_handler(CallbackQueryHandler(referral_handler, pattern="^referral$"))
    app.add_handler(CallbackQueryHandler(profile_handler, pattern="^profile$"))
    app.add_handler(CallbackQueryHandler(back_handler, pattern="^back$"))


    app.run_polling()


if __name__ == "__main__":
    main()

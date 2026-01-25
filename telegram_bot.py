#!/usr/bin/env python3
"""
x0tta6bl4 Telegram Bot для signup и payment
Простой MVP для получения первых пользователей
"""

import os
import logging
import asyncio
from typing import Dict, Optional
from datetime import datetime, timedelta

try:
    from aiogram import Bot, Dispatcher, types
    from aiogram.contrib.fsm_storage.memory import MemoryStorage
    from aiogram.dispatcher import FSMContext
    from aiogram.dispatcher.filters.state import State, StatesGroup
    from aiogram.types import LabeledPrice, PreCheckoutQuery, ContentType, CallbackQuery
    from aiogram.utils import executor
    from aiogram.dispatcher.filters import Text
    AIOGRAM_AVAILABLE = True
except ImportError:
    AIOGRAM_AVAILABLE = False
    logging.warning("aiogram not installed. Install: pip install aiogram")

# Import keyboards
try:
    from keyboards import (
        get_main_menu_keyboard, get_trial_keyboard, get_subscribe_keyboard,
        get_config_keyboard, get_admin_keyboard, get_back_keyboard
    )
    KEYBOARDS_AVAILABLE = True
except ImportError:
    KEYBOARDS_AVAILABLE = False
    logging.warning("Keyboards module not available")

# Import rate limiter
try:
    from rate_limiter import check_rate_limit
    RATE_LIMITER_AVAILABLE = True
except ImportError:
    RATE_LIMITER_AVAILABLE = False
    def check_rate_limit(user_id, action):
        return True, None

# Import our modules
try:
    from vpn_config_generator import generate_config_text, generate_vless_link, generate_uuid
    from database import (
        init_database, get_user, create_user, update_user,
        is_user_active, log_activity, record_payment, get_user_stats
    )
    try:
        from qr_code_generator import generate_qr_code_for_vless
        QR_AVAILABLE = True
    except ImportError:
        QR_AVAILABLE = False
        generate_qr_code_for_vless = None
    MODULES_AVAILABLE = True
except ImportError as e:
    MODULES_AVAILABLE = False
    QR_AVAILABLE = False
    generate_qr_code_for_vless = None
    logging.warning(f"Local modules not available: {e}")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Config
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
PROVIDER_TOKEN = os.getenv("TELEGRAM_PAYMENT_TOKEN", "")  # От @BotFather
TRIAL_DAYS = 7
MONTHLY_PRICE = 1000  # $10 в центах (или 700₽ через YooMoney)

if not BOT_TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN not set!")
    logger.info("Get token from @BotFather on Telegram")

# Initialize database
if MODULES_AVAILABLE:
    try:
        init_database()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")

# Initialize bot
if AIOGRAM_AVAILABLE:
    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(bot, storage=storage)
else:
    bot = None
    dp = None


class SignupStates(StatesGroup):
    waiting_for_email = State()
    waiting_for_payment = State()


def generate_vpn_config(user_id: int) -> str:
    """Generate VPN config для пользователя"""
    if not MODULES_AVAILABLE:
        return f"# Config generation not available\n# User ID: {user_id}"
    
    # Get user from database
    user = get_user(user_id)
    if not user:
        logger.warning(f"User {user_id} not found in database")
        return "# User not found"
    
    # Generate config
    vpn_uuid = user.get('vpn_uuid')
    
    # ✅ SECURITY FIX: Ensure user has UUID (should always be set, but check for safety)
    if not vpn_uuid:
        logger.error(f"🚨 CRITICAL: User {user_id} has no vpn_uuid! Generating new one...")
        # Generate new UUID for user (should not happen, but handle gracefully)
        vpn_uuid = generate_uuid()
        update_user(user_id, vpn_uuid=vpn_uuid)
        logger.warning(f"Generated new UUID for user {user_id}: {vpn_uuid}")
    
    try:
        config_text = generate_config_text(user_id, vpn_uuid)
    except ValueError as e:
        logger.error(f"🚨 CRITICAL: Failed to generate config for user {user_id}: {e}")
        return f"# Error generating config. Please contact support: @x0tta6bl4_support"
    
    # Update user's config in database
    update_user(user_id, vpn_config=config_text)
    
    return config_text


@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    """Приветствие и главное меню"""
    user_id = message.from_user.id
    username = message.from_user.username or "User"
    
    # Log activity
    if MODULES_AVAILABLE:
        log_activity(user_id, "start_command")
    
    # Проверяем есть ли уже подписка
    if MODULES_AVAILABLE:
        if is_user_active(user_id):
            user = get_user(user_id)
            expires_at = datetime.fromisoformat(user['expires_at'])
            days_left = (expires_at - datetime.now()).days
            await message.answer(
                f"✅ У тебя уже есть активная подписка!\n"
                f"Осталось дней: {days_left}\n"
                f"Сервер: 89.125.1.107:39829\n\n"
                f"Используй /config чтобы получить конфиг"
            )
            return
    
    # Приветствие для новых пользователей
    welcome_text = (
        f"👋 Привет, {username}!\n\n"
        f"**x0tta6bl4** — это VPN который:\n"
        f"✅ Не падает (self-healing mesh)\n"
        f"✅ Быстрый (ping <80ms из Крыма)\n"
        f"✅ Безопасный (Zero-Trust, твои данные шифруются локально)\n\n"
        f"**Попробуй 7 дней бесплатно!**"
    )
    
    if KEYBOARDS_AVAILABLE:
        await message.answer(
            welcome_text,
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard()
        )
    else:
        await message.answer(
            welcome_text + "\n\n"
            f"Команды:\n"
            f"/trial — Бесплатный 7-дневный trial\n"
            f"/subscribe — Подписка $10/мес\n"
            f"/help — Помощь",
            parse_mode="Markdown"
        )


@dp.message_handler(commands=['trial'])
async def cmd_trial(message: types.Message):
    """Бесплатный 7-дневный trial"""
    user_id = message.from_user.id
    
    # Rate limiting
    if RATE_LIMITER_AVAILABLE:
        allowed, error_msg = check_rate_limit(user_id, 'trial')
        if not allowed:
            await message.answer(f"❌ {error_msg}")
            return
    
    if MODULES_AVAILABLE:
        log_activity(user_id, "trial_requested")
    
    # Проверяем не использовал ли уже trial
    if MODULES_AVAILABLE:
        user = get_user(user_id)
        if user and user.get('trial_used'):
            await message.answer(
                "❌ Ты уже использовал бесплатный trial.\n"
                "Используй /subscribe для подписки."
            )
            return
    
    # Создаем trial аккаунт
    expires_at = datetime.now() + timedelta(days=TRIAL_DAYS)
    
    if MODULES_AVAILABLE:
        # Generate UUID for user
        vpn_uuid = generate_uuid()
        create_user(
            user_id=user_id,
            username=message.from_user.username,
            plan='trial',
            expires_at=expires_at,
            vpn_uuid=vpn_uuid
        )
        log_activity(user_id, "trial_activated")
    else:
        # Fallback to in-memory storage
        if not hasattr(cmd_trial, 'users_db'):
            cmd_trial.users_db = {}
        cmd_trial.users_db[user_id] = {
            'user_id': user_id,
            'username': message.from_user.username,
            'trial_used': True,
            'expires_at': expires_at,
            'plan': 'trial'
        }
    
    # Send welcome message
    try:
        from notifications import send_welcome_message
        await send_welcome_message(bot, user_id, 'trial')
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"Failed to send welcome message: {e}")
    
    await message.answer(
        f"🎉 **Trial активирован!**\n\n"
        f"Доступен до: {expires_at.strftime('%d.%m.%Y')}\n"
        f"Сервер: `89.125.1.107:39829`\n\n"
        f"Используй /config чтобы получить конфиг для подключения.",
        parse_mode="Markdown"
    )
    
    logger.info(f"Trial activated for user {user_id}")


@dp.message_handler(commands=['subscribe'])
async def cmd_subscribe(message: types.Message):
    """Подписка через Telegram Payments"""
    if not PROVIDER_TOKEN:
        await message.answer(
            "❌ Платежи временно недоступны.\n"
            "Используй /trial для бесплатного доступа."
        )
        return
    
    # Создаем invoice
    prices = [LabeledPrice(label="x0tta6bl4 Pro (1 месяц)", amount=MONTHLY_PRICE)]
    
    await bot.send_invoice(
        chat_id=message.chat.id,
        title="x0tta6bl4 Pro",
        description="VPN который не падает + Encrypted Storage\n"
                    "Self-healing mesh network\n"
                    "Zero-Trust security\n"
                    "Безлимитный трафик",
        payload=f"subscription_{message.from_user.id}",
        provider_token=PROVIDER_TOKEN,
        currency="USD",
        prices=prices,
        start_parameter="x0tta6bl4-pro",
        photo_url="https://89.125.1.107:8080/landing.html",  # TODO: реальная картинка
        need_name=False,
        need_phone_number=False,
        need_email=False,
        need_shipping_address=False,
        send_phone_number_to_provider=False,
        send_email_to_provider=False,
        is_flexible=False
    )


@dp.pre_checkout_query_handler()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    """Подтверждение платежа с валидацией (SECURITY FIX)"""
    user_id = pre_checkout_query.from_user.id
    
    # ✅ SECURITY FIX: Validate payment amount
    if pre_checkout_query.total_amount != MONTHLY_PRICE:
        await bot.answer_pre_checkout_query(
            pre_checkout_query.id,
            ok=False,
            error_message=f"Invalid payment amount. Expected ${MONTHLY_PRICE/100:.2f}"
        )
        logger.warning(f"🚨 Invalid payment amount: {pre_checkout_query.total_amount} from user {user_id} (expected {MONTHLY_PRICE})")
        if MODULES_AVAILABLE:
            log_activity(user_id, "payment_validation_failed_amount")
        return
    
    # ✅ SECURITY FIX: Validate currency
    if pre_checkout_query.currency != "USD":
        await bot.answer_pre_checkout_query(
            pre_checkout_query.id,
            ok=False,
            error_message="Only USD currency is accepted"
        )
        logger.warning(f"🚨 Invalid currency: {pre_checkout_query.currency} from user {user_id}")
        if MODULES_AVAILABLE:
            log_activity(user_id, "payment_validation_failed_currency")
        return
    
    # ✅ SECURITY FIX: Validate payload
    expected_payload = f"subscription_{user_id}"
    if pre_checkout_query.invoice_payload != expected_payload:
        await bot.answer_pre_checkout_query(
            pre_checkout_query.id,
            ok=False,
            error_message="Invalid payment payload"
        )
        logger.warning(f"🚨 Invalid payload: {pre_checkout_query.invoice_payload} from user {user_id} (expected {expected_payload})")
        if MODULES_AVAILABLE:
            log_activity(user_id, "payment_validation_failed_payload")
        return
    
    # ✅ All validations passed
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)
    logger.info(f"✅ Payment validated for user {user_id}")


@dp.message_handler(content_types=ContentType.SUCCESSFUL_PAYMENT)
async def process_successful_payment(message: types.Message):
    """Обработка успешного платежа"""
    user_id = message.from_user.id
    payment = message.successful_payment
    
    if MODULES_AVAILABLE:
        log_activity(user_id, "payment_received")
    
    # Создаем/обновляем подписку
    expires_at = datetime.now() + timedelta(days=30)
    payment_amount = payment.total_amount / 100  # Convert cents to dollars
    
    if MODULES_AVAILABLE:
        # Get or create user
        user = get_user(user_id)
        if not user:
            vpn_uuid = generate_uuid()
            create_user(
                user_id=user_id,
                username=message.from_user.username,
                plan='pro',
                expires_at=expires_at,
                vpn_uuid=vpn_uuid
            )
        else:
            # Update existing user
            vpn_uuid = user.get('vpn_uuid') or generate_uuid()
            update_user(
                user_id=user_id,
                plan='pro',
                expires_at=expires_at,
                vpn_uuid=vpn_uuid
            )
        
        # Record payment
        record_payment(
            user_id=user_id,
            amount=payment_amount,
            currency=payment.currency,
            provider='telegram',
            status='completed'
        )
        log_activity(user_id, "subscription_activated")
    else:
        # Fallback to in-memory storage
        if not hasattr(process_successful_payment, 'users_db'):
            process_successful_payment.users_db = {}
        process_successful_payment.users_db[user_id] = {
            'user_id': user_id,
            'username': message.from_user.username,
            'expires_at': expires_at,
            'plan': 'pro',
            'payment_amount': payment_amount,
            'payment_currency': payment.currency
        }
    
    # Send welcome message
    try:
        from notifications import send_welcome_message
        await send_welcome_message(bot, user_id, 'pro')
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"Failed to send welcome message: {e}")
    
    await message.answer(
        f"✅ **Платеж успешен!**\n\n"
        f"Подписка активна до: {expires_at.strftime('%d.%m.%Y')}\n"
        f"Сервер: `89.125.1.107:39829`\n\n"
        f"Используй /config чтобы получить конфиг.",
        parse_mode="Markdown"
    )
    
    logger.info(f"Subscription activated for user {user_id}, expires {expires_at}")


@dp.message_handler(commands=['config'])
async def cmd_config(message: types.Message):
    """Получить VPN конфиг"""
    user_id = message.from_user.id
    
    # Rate limiting
    if RATE_LIMITER_AVAILABLE:
        allowed, error_msg = check_rate_limit(user_id, 'config')
        if not allowed:
            await message.answer(f"❌ {error_msg}")
            return
    
    if MODULES_AVAILABLE:
        log_activity(user_id, "config_requested")
    
    # Check if user exists and is active
    if MODULES_AVAILABLE:
        if not is_user_active(user_id):
            await message.answer(
                "❌ У тебя нет активной подписки.\n"
                "Используй /trial для бесплатного доступа."
            )
            return
        
        user = get_user(user_id)
    else:
        # Fallback check
        if not hasattr(cmd_config, 'users_db') or user_id not in cmd_config.users_db:
            await message.answer(
                "❌ У тебя нет активной подписки.\n"
                "Используй /trial для бесплатного доступа."
            )
            return
        
        user = cmd_config.users_db[user_id]
        if user.get('expires_at') and datetime.now() >= user['expires_at']:
            await message.answer(
                "❌ Твоя подписка истекла.\n"
                "Используй /subscribe для продления."
            )
            return
    
    # Генерируем конфиг
    config = generate_vpn_config(user_id)
    
    # Generate VLESS link for quick copy
    if MODULES_AVAILABLE and user.get('vpn_uuid'):
        vless_link = generate_vless_link(user['vpn_uuid'])
        
        # Send QR code if available
        if QR_AVAILABLE and generate_qr_code_for_vless:
            try:
                qr_image = generate_qr_code_for_vless(vless_link)
                if qr_image:
                    await message.answer_photo(
                        photo=types.InputFile(qr_image, filename="vpn_qr.png"),
                        caption="📱 **QR код для быстрого подключения**\n\n"
                                "Отсканируй QR код в клиенте (v2rayNG, Shadowrocket)"
                    )
            except Exception as e:
                logger.warning(f"Failed to generate QR code: {e}")
        
        # Send VLESS link
        await message.answer(
            f"🔗 **VLESS ссылка (скопируй):**\n\n"
            f"`{vless_link}`\n\n"
            f"Или скачай полный конфиг ниже ⬇️",
            parse_mode="Markdown"
        )
    
    # Отправляем как файл
    await message.answer_document(
        document=types.InputFile.from_string(
            config,
            filename=f"x0tta6bl4_{user_id}.conf"
        ),
        caption="📁 Твой VPN конфиг\n\n"
                "Инструкция по подключению:\n"
                "1. Скачай v2rayN (Windows) или v2rayNG (Android)\n"
                "2. Импортируй этот конфиг или VLESS ссылку\n"
                "3. Подключись!"
    )


@dp.message_handler(commands=['status'])
async def cmd_status(message: types.Message):
    """Статус подписки"""
    user_id = message.from_user.id
    
    if MODULES_AVAILABLE:
        log_activity(user_id, "status_requested")
        user = get_user(user_id)
        
        if not user:
            await message.answer("❌ У тебя нет активной подписки.")
            return
        
        if user.get('expires_at'):
            expires_at = datetime.fromisoformat(user['expires_at'])
            days_left = (expires_at - datetime.now()).days
            if days_left > 0:
                await message.answer(
                    f"✅ **Активная подписка**\n\n"
                    f"План: {user.get('plan', 'unknown')}\n"
                    f"Осталось дней: {days_left}\n"
                    f"Истекает: {expires_at.strftime('%d.%m.%Y')}",
                    parse_mode="Markdown"
                )
            else:
                await message.answer("❌ Подписка истекла. Используй /subscribe")
        else:
            await message.answer("❌ Подписка неактивна")
    else:
        # Fallback
        if not hasattr(cmd_status, 'users_db') or user_id not in cmd_status.users_db:
            await message.answer("❌ У тебя нет активной подписки.")
            return
        
        user = cmd_status.users_db[user_id]
        if user.get('expires_at'):
            expires_at = user['expires_at']
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at)
            days_left = (expires_at - datetime.now()).days
            if days_left > 0:
                await message.answer(
                    f"✅ **Активная подписка**\n\n"
                    f"План: {user.get('plan', 'unknown')}\n"
                    f"Осталось дней: {days_left}\n"
                    f"Истекает: {expires_at.strftime('%d.%m.%Y')}",
                    parse_mode="Markdown"
                )
            else:
                await message.answer("❌ Подписка истекла. Используй /subscribe")
        else:
            await message.answer("❌ Подписка неактивна")


@dp.message_handler(commands=['help'])
async def cmd_help(message: types.Message):
    """Помощь"""
    user_id = message.from_user.id
    if MODULES_AVAILABLE:
        log_activity(user_id, "help_requested")
    
    help_text = (
        "**x0tta6bl4 Bot — Команды:**\n\n"
        "/start — Главное меню\n"
        "/trial — 7 дней бесплатно\n"
        "/subscribe — Подписка $10/мес\n"
        "/config — Получить VPN конфиг\n"
        "/status — Статус подписки\n"
        "/help — Эта справка\n\n"
        "**Поддержка:** @x0tta6bl4_support"
    )
    
    # Add stats for admin (if user_id matches admin)
    admin_id = int(os.getenv("ADMIN_USER_ID", "0"))
    if admin_id and user_id == admin_id and MODULES_AVAILABLE:
        try:
            from admin_commands import get_admin_stats
            help_text += f"\n\n{get_admin_stats()}"
            help_text += f"\n\n**Admin Commands:**\n"
            help_text += f"/admin_stats — Детальная статистика\n"
            help_text += f"/admin_users — Список пользователей\n"
            help_text += f"/admin_user <id> — Инфо о пользователе\n"
        except ImportError:
            stats = get_user_stats()
            help_text += f"\n\n**📊 Статистика (Admin):**\n"
            help_text += f"Всего пользователей: {stats['total_users']}\n"
            help_text += f"Активных: {stats['active_users']}\n"
            help_text += f"Trial: {stats['trial_users']}\n"
            help_text += f"Pro: {stats['pro_users']}\n"
            help_text += f"Revenue: ${stats['total_revenue']:.2f}"
    
    await message.answer(help_text, parse_mode="Markdown")


@dp.message_handler(commands=['admin_stats'])
async def cmd_admin_stats(message: types.Message):
    """Admin: Детальная статистика"""
    user_id = message.from_user.id
    
    try:
        from admin_commands import is_admin, get_admin_stats
        if not is_admin(user_id):
            await message.answer("❌ Доступ запрещён")
            return
        
        stats_text = get_admin_stats()
        await message.answer(stats_text, parse_mode="Markdown")
    except ImportError:
        await message.answer("❌ Admin commands not available")


@dp.message_handler(commands=['admin_users'])
async def cmd_admin_users(message: types.Message):
    """Admin: Список пользователей"""
    user_id = message.from_user.id
    
    try:
        from admin_commands import is_admin, get_user_list, format_user_info
        if not is_admin(user_id):
            await message.answer("❌ Доступ запрещён")
            return
        
        users = get_user_list(limit=10)
        if not users:
            await message.answer("📭 Нет активных пользователей")
            return
        
        text = f"**👥 Активные пользователи (показано {len(users)}):**\n\n"
        for user in users:
            text += f"• User {user['user_id']} (@{user.get('username', 'N/A')}) - {user.get('plan', 'N/A')}\n"
        
        await message.answer(text, parse_mode="Markdown")
    except ImportError:
        await message.answer("❌ Admin commands not available")


@dp.message_handler(commands=['admin_user'])
async def cmd_admin_user(message: types.Message):
    """Admin: Информация о пользователе"""
    user_id = message.from_user.id
    
    try:
        from admin_commands import is_admin, format_user_info
        from database import get_user
        
        if not is_admin(user_id):
            await message.answer("❌ Доступ запрещён")
            return
        
        # Parse user ID from command
        parts = message.text.split()
        if len(parts) < 2:
            await message.answer("Использование: /admin_user <user_id>")
            return
        
        try:
            target_user_id = int(parts[1])
        except ValueError:
            await message.answer("❌ Неверный user_id")
            return
        
        user = get_user(target_user_id)
        if not user:
            await message.answer(f"❌ Пользователь {target_user_id} не найден")
            return
        
        user_info = format_user_info(user)
        await message.answer(user_info, parse_mode="Markdown")
    except ImportError:
        await message.answer("❌ Admin commands not available")


# Callback handlers для inline keyboards
@dp.callback_query_handler(lambda c: c.data == "main_menu")
async def callback_main_menu(callback_query: CallbackQuery):
    """Обработка кнопки "Главное меню" """
    await callback_query.answer()
    user_id = callback_query.from_user.id
    username = callback_query.from_user.username or "User"
    
    welcome_text = (
        f"👋 Главное меню\n\n"
        f"**x0tta6bl4** — VPN который не падает!\n\n"
        f"Выбери действие:"
    )
    
    if KEYBOARDS_AVAILABLE:
        await callback_query.message.edit_text(
            welcome_text,
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard()
        )
    else:
        await callback_query.message.edit_text(welcome_text, parse_mode="Markdown")


@dp.callback_query_handler(lambda c: c.data == "trial")
async def callback_trial(callback_query: CallbackQuery):
    """Обработка кнопки "Trial" """
    await callback_query.answer()
    
    text = (
        "🆓 **7 дней бесплатно**\n\n"
        "Попробуй x0tta6bl4 без оплаты:\n"
        "✅ Полный доступ к VPN\n"
        "✅ Безлимитный трафик\n"
        "✅ Все функции\n\n"
        "Нажми кнопку ниже чтобы активировать!"
    )
    
    if KEYBOARDS_AVAILABLE:
        await callback_query.message.edit_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_trial_keyboard()
        )
    else:
        await callback_query.message.edit_text(text, parse_mode="Markdown")


@dp.callback_query_handler(lambda c: c.data == "activate_trial")
async def callback_activate_trial(callback_query: CallbackQuery):
    """Активация trial через кнопку"""
    user_id = callback_query.from_user.id
    
    # Rate limiting
    if RATE_LIMITER_AVAILABLE:
        allowed, error_msg = check_rate_limit(user_id, 'trial')
        if not allowed:
            await callback_query.answer(f"❌ {error_msg}", show_alert=True)
            return
    
    if MODULES_AVAILABLE:
        log_activity(user_id, "trial_requested")
        user = get_user(user_id)
        if user and user.get('trial_used'):
            await callback_query.answer("❌ Ты уже использовал trial", show_alert=True)
            return
    
    # Используем существующую логику из cmd_trial
    expires_at = datetime.now() + timedelta(days=TRIAL_DAYS)
    
    if MODULES_AVAILABLE:
        vpn_uuid = generate_uuid()
        create_user(
            user_id=user_id,
            username=callback_query.from_user.username,
            plan='trial',
            expires_at=expires_at,
            vpn_uuid=vpn_uuid
        )
        log_activity(user_id, "trial_activated")
    
    await callback_query.answer("✅ Trial активирован!", show_alert=True)
    
    text = (
        f"🎉 **Trial активирован!**\n\n"
        f"Доступен до: {expires_at.strftime('%d.%m.%Y')}\n"
        f"Сервер: `89.125.1.107:39829`\n\n"
        f"Используй кнопку ниже чтобы получить конфиг!"
    )
    
    if KEYBOARDS_AVAILABLE:
        await callback_query.message.edit_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_config_keyboard()
        )
    else:
        await callback_query.message.edit_text(text, parse_mode="Markdown")


@dp.callback_query_handler(lambda c: c.data == "subscribe")
async def callback_subscribe(callback_query: CallbackQuery):
    """Обработка кнопки "Подписка" """
    await callback_query.answer()
    
    text = (
        "💳 **Подписка $10/мес**\n\n"
        "Что включено:\n"
        "✅ Безлимитный трафик\n"
        "✅ Self-healing mesh\n"
        "✅ Encrypted storage\n"
        "✅ Zero-Trust security\n"
        "✅ Поддержка 24/7\n\n"
        "Нажми кнопку ниже чтобы оплатить!"
    )
    
    if KEYBOARDS_AVAILABLE:
        await callback_query.message.edit_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_subscribe_keyboard()
        )
    else:
        await callback_query.message.edit_text(text, parse_mode="Markdown")


@dp.callback_query_handler(lambda c: c.data == "pay_subscribe")
async def callback_pay_subscribe(callback_query: CallbackQuery):
    """Обработка кнопки "Оплатить" """
    if not PROVIDER_TOKEN:
        await callback_query.answer("❌ Платежи временно недоступны", show_alert=True)
        return
    
    await callback_query.answer()
    
    # Используем существующую логику из cmd_subscribe
    prices = [LabeledPrice(label="x0tta6bl4 Pro (1 месяц)", amount=MONTHLY_PRICE)]
    
    await bot.send_invoice(
        chat_id=callback_query.message.chat.id,
        title="x0tta6bl4 Pro",
        description="VPN который не падает + Encrypted Storage\n"
                    "Self-healing mesh network\n"
                    "Zero-Trust security\n"
                    "Безлимитный трафик",
        payload=f"subscription_{callback_query.from_user.id}",
        provider_token=PROVIDER_TOKEN,
        currency="USD",
        prices=prices,
        start_parameter="x0tta6bl4-pro"
    )


@dp.callback_query_handler(lambda c: c.data == "get_config")
async def callback_get_config(callback_query: CallbackQuery):
    """Обработка кнопки "Получить конфиг" """
    user_id = callback_query.from_user.id
    
    if MODULES_AVAILABLE:
        if not is_user_active(user_id):
            await callback_query.answer("❌ У тебя нет активной подписки", show_alert=True)
            return
    
    await callback_query.answer()
    
    text = "📋 **Выбери формат конфига:**\n\n"
    text += "• QR код — для быстрого сканирования на мобильном\n"
    text += "• VLESS ссылка — для копирования\n"
    text += "• Полный конфиг — файл с инструкциями"
    
    if KEYBOARDS_AVAILABLE:
        await callback_query.message.edit_text(
            text,
            parse_mode="Markdown",
            reply_markup=get_config_keyboard()
        )
    else:
        await callback_query.message.edit_text(text, parse_mode="Markdown")


@dp.callback_query_handler(lambda c: c.data == "get_qr")
async def callback_get_qr(callback_query: CallbackQuery):
    """Отправка QR кода"""
    user_id = callback_query.from_user.id
    
    if MODULES_AVAILABLE:
        user = get_user(user_id)
        if not user or not user.get('vpn_uuid'):
            await callback_query.answer("❌ Конфиг не найден", show_alert=True)
            return
        
        vless_link = generate_vless_link(user['vpn_uuid'])
        
        if QR_AVAILABLE and generate_qr_code_for_vless:
            try:
                qr_image = generate_qr_code_for_vless(vless_link)
                if qr_image:
                    await callback_query.answer()
                    await callback_query.message.answer_photo(
                        photo=types.InputFile(qr_image, filename="vpn_qr.png"),
                        caption="📱 **QR код для быстрого подключения**\n\n"
                                "Отсканируй QR код в клиенте (v2rayNG, Shadowrocket)",
                        reply_markup=get_back_keyboard()
                    )
                    return
            except Exception as e:
                logger.warning(f"Failed to generate QR code: {e}")
    
    await callback_query.answer("❌ QR код недоступен", show_alert=True)


@dp.callback_query_handler(lambda c: c.data == "get_vless")
async def callback_get_vless(callback_query: CallbackQuery):
    """Отправка VLESS ссылки"""
    user_id = callback_query.from_user.id
    
    if MODULES_AVAILABLE:
        user = get_user(user_id)
        if not user or not user.get('vpn_uuid'):
            await callback_query.answer("❌ Конфиг не найден", show_alert=True)
            return
        
        vless_link = generate_vless_link(user['vpn_uuid'])
        await callback_query.answer()
        await callback_query.message.answer(
            f"🔗 **VLESS ссылка:**\n\n"
            f"`{vless_link}`\n\n"
            f"Скопируй и импортируй в клиент",
            parse_mode="Markdown",
            reply_markup=get_back_keyboard()
        )
    else:
        await callback_query.answer("❌ Функция недоступна", show_alert=True)


@dp.callback_query_handler(lambda c: c.data == "get_full_config")
async def callback_get_full_config(callback_query: CallbackQuery):
    """Отправка полного конфига"""
    user_id = callback_query.from_user.id
    
    if MODULES_AVAILABLE:
        if not is_user_active(user_id):
            await callback_query.answer("❌ У тебя нет активной подписки", show_alert=True)
            return
        
        config = generate_vpn_config(user_id)
        await callback_query.answer()
        await callback_query.message.answer_document(
            document=types.InputFile.from_string(
                config,
                filename=f"x0tta6bl4_{user_id}.conf"
            ),
            caption="📁 **Твой VPN конфиг**\n\n"
                    "Инструкция по подключению:\n"
                    "1. Скачай v2rayN (Windows) или v2rayNG (Android)\n"
                    "2. Импортируй этот конфиг\n"
                    "3. Подключись!",
            reply_markup=get_back_keyboard()
        )
    else:
        await callback_query.answer("❌ Функция недоступна", show_alert=True)


@dp.callback_query_handler(lambda c: c.data == "status")
async def callback_status(callback_query: CallbackQuery):
    """Обработка кнопки "Статус" """
    user_id = callback_query.from_user.id
    
    if MODULES_AVAILABLE:
        log_activity(user_id, "status_requested")
        user = get_user(user_id)
        
        if not user:
            await callback_query.answer("❌ У тебя нет активной подписки", show_alert=True)
            return
        
        if user.get('expires_at'):
            expires_at = datetime.fromisoformat(user['expires_at'])
            days_left = (expires_at - datetime.now()).days
            if days_left > 0:
                text = (
                    f"✅ **Активная подписка**\n\n"
                    f"План: {user.get('plan', 'unknown')}\n"
                    f"Осталось дней: {days_left}\n"
                    f"Истекает: {expires_at.strftime('%d.%m.%Y')}"
                )
            else:
                text = "❌ Подписка истекла. Используй /subscribe"
        else:
            text = "❌ Подписка неактивна"
        
        await callback_query.answer()
        if KEYBOARDS_AVAILABLE:
            await callback_query.message.edit_text(
                text,
                parse_mode="Markdown",
                reply_markup=get_back_keyboard()
            )
        else:
            await callback_query.message.edit_text(text, parse_mode="Markdown")
    else:
        await callback_query.answer("❌ Функция недоступна", show_alert=True)


@dp.callback_query_handler(lambda c: c.data == "help")
async def callback_help(callback_query: CallbackQuery):
    """Обработка кнопки "Помощь" """
    await callback_query.answer()
    
    help_text = (
        "**x0tta6bl4 Bot — Команды:**\n\n"
        "/start — Главное меню\n"
        "/trial — 7 дней бесплатно\n"
        "/subscribe — Подписка $10/мес\n"
        "/config — Получить VPN конфиг\n"
        "/status — Статус подписки\n"
        "/help — Эта справка\n\n"
        "**Поддержка:** @x0tta6bl4_support"
    )
    
    if KEYBOARDS_AVAILABLE:
        await callback_query.message.edit_text(
            help_text,
            parse_mode="Markdown",
            reply_markup=get_back_keyboard()
        )
    else:
        await callback_query.message.edit_text(help_text, parse_mode="Markdown")


@dp.message_handler()
async def echo(message: types.Message):
    """Обработка неизвестных сообщений"""
    if KEYBOARDS_AVAILABLE:
        await message.answer(
            "Не понимаю 🤔\n"
            "Используй кнопки ниже или /help для списка команд",
            reply_markup=get_main_menu_keyboard()
        )
    else:
        await message.answer(
            "Не понимаю 🤔\n"
            "Используй /help для списка команд"
        )


async def main():
    """Запуск бота"""
    if not AIOGRAM_AVAILABLE:
        logger.error("aiogram not installed!")
        logger.info("Install: pip install aiogram")
        return
    
    if not BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set!")
        logger.info("Get token from @BotFather")
        return
    
    logger.info("Starting x0tta6bl4 Telegram bot...")
    await dp.start_polling()


if __name__ == "__main__":
    asyncio.run(main())


#!/usr/bin/env python3
"""
Notifications для x0tta6bl4 Telegram Bot
Уведомления пользователям о важных событиях
"""

import logging
import os
from typing import Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

try:
    from aiogram import Bot
    from database import get_active_users, get_user
    MODULES_AVAILABLE = True
except ImportError:
    MODULES_AVAILABLE = False
    logger.warning("Notifications modules not available")


async def send_expiration_reminder(bot: Bot, user_id: int, days_left: int):
    """Отправить напоминание об истечении подписки"""
    if not MODULES_AVAILABLE or not bot:
        return
    
    try:
        if days_left == 7:
            text = (
                "⏰ **Напоминание о подписке**\n\n"
                f"Твоя подписка истекает через {days_left} дней.\n"
                "Используй /subscribe чтобы продлить!"
            )
        elif days_left == 3:
            text = (
                "⚠️ **Подписка скоро истечёт**\n\n"
                f"Осталось {days_left} дня!\n"
                "Продли сейчас: /subscribe"
            )
        elif days_left == 1:
            text = (
                "🔴 **Последний день подписки!**\n\n"
                "Твоя подписка истекает завтра.\n"
                "Продли сейчас: /subscribe"
            )
        else:
            return
        
        await bot.send_message(user_id, text, parse_mode="Markdown")
        logger.info(f"Expiration reminder sent to user {user_id} ({days_left} days left)")
    except Exception as e:
        logger.error(f"Failed to send expiration reminder to user {user_id}: {e}")


async def send_trial_ending_reminder(bot: Bot, user_id: int, days_left: int):
    """Отправить напоминание об окончании trial"""
    if not MODULES_AVAILABLE or not bot:
        return
    
    try:
        if days_left == 2:
            text = (
                "⏰ **Trial заканчивается**\n\n"
                f"Осталось {days_left} дня бесплатного доступа.\n"
                "Используй /subscribe чтобы продолжить!"
            )
        elif days_left == 1:
            text = (
                "⚠️ **Последний день trial!**\n\n"
                "Завтра trial закончится.\n"
                "Подпишись сейчас: /subscribe"
            )
        else:
            return
        
        await bot.send_message(user_id, text, parse_mode="Markdown")
        logger.info(f"Trial ending reminder sent to user {user_id} ({days_left} days left)")
    except Exception as e:
        logger.error(f"Failed to send trial reminder to user {user_id}: {e}")


async def send_welcome_message(bot: Bot, user_id: int, plan: str):
    """Отправить приветственное сообщение"""
    if not bot:
        return
    
    try:
        if plan == 'trial':
            text = (
                "🎉 **Добро пожаловать в x0tta6bl4!**\n\n"
                "Твой 7-дневный trial активирован.\n"
                "Используй /config чтобы получить VPN конфиг.\n\n"
                "Если понравится — подпишись: /subscribe"
            )
        else:
            text = (
                "🎉 **Спасибо за подписку!**\n\n"
                "Твоя подписка активна на 30 дней.\n"
                "Используй /config чтобы получить VPN конфиг.\n\n"
                "Приятного использования! 🚀"
            )
        
        await bot.send_message(user_id, text, parse_mode="Markdown")
        logger.info(f"Welcome message sent to user {user_id} (plan: {plan})")
    except Exception as e:
        logger.error(f"Failed to send welcome message to user {user_id}: {e}")


async def check_and_send_reminders(bot: Bot):
    """Проверить и отправить напоминания всем пользователям"""
    if not MODULES_AVAILABLE or not bot:
        return
    
    try:
        active_users = get_active_users()
        now = datetime.now()
        
        for user in active_users:
            if not user.get('expires_at'):
                continue
            
            expires_at = datetime.fromisoformat(user['expires_at'])
            days_left = (expires_at - now).days
            
            if user.get('plan') == 'trial' and days_left in [2, 1]:
                await send_trial_ending_reminder(bot, user['user_id'], days_left)
            elif days_left in [7, 3, 1]:
                await send_expiration_reminder(bot, user['user_id'], days_left)
    
    except Exception as e:
        logger.error(f"Failed to check and send reminders: {e}")


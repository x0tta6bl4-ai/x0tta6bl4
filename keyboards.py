#!/usr/bin/env python3
"""
Inline keyboards для x0tta6bl4 Telegram Bot
Улучшенный UX с кнопками
"""

from typing import Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Главное меню с кнопками"""
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🆓 7 дней бесплатно", callback_data="trial"),
        InlineKeyboardButton("💳 Подписка $10/мес", callback_data="subscribe")
    )
    keyboard.add(
        InlineKeyboardButton("📋 Получить конфиг", callback_data="get_config"),
        InlineKeyboardButton("📊 Статус", callback_data="status")
    )
    keyboard.add(InlineKeyboardButton("ℹ️ Помощь", callback_data="help"))
    return keyboard


def get_trial_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для trial"""
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton("✅ Активировать trial", callback_data="activate_trial"))
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="main_menu"))
    return keyboard


def get_subscribe_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для подписки"""
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton("💳 Оплатить $10/мес", callback_data="pay_subscribe"))
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="main_menu"))
    return keyboard


def get_config_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для получения конфига"""
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📱 QR код", callback_data="get_qr"),
        InlineKeyboardButton("🔗 VLESS ссылка", callback_data="get_vless")
    )
    keyboard.add(
        InlineKeyboardButton("📄 Полный конфиг", callback_data="get_full_config"),
        InlineKeyboardButton("📊 Статус", callback_data="status")
    )
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="main_menu"))
    return keyboard


def get_admin_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для админа"""
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
        InlineKeyboardButton("👥 Пользователи", callback_data="admin_users")
    )
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="main_menu"))
    return keyboard


def get_back_keyboard() -> InlineKeyboardMarkup:
    """Простая кнопка "Назад" """
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="main_menu"))
    return keyboard


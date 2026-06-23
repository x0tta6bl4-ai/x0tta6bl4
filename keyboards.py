#!/usr/bin/env python3
"""
Inline keyboards для x0tta6bl4 Telegram Bot
Улучшенный UX с кнопками
"""

from typing import Optional
import os
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types.web_app_info import WebAppInfo

TWA_URL = os.getenv("TWA_URL", "https://app.x0tta6bl4.tech/tma_mockup.html")

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
        InlineKeyboardButton("💻 x0tta6bl4_sys [TERMINAL]", web_app=WebAppInfo(url=TWA_URL))
    )
    keyboard.add(
        InlineKeyboardButton("🌍 Выбрать локацию", callback_data="select_location"),
        InlineKeyboardButton("📊 Статус", callback_data="status")
    )
    keyboard.add(
        InlineKeyboardButton("📱 QR код", callback_data="get_qr"),
        InlineKeyboardButton("🔗 VLESS ссылка", callback_data="get_vless")
    )
    keyboard.add(InlineKeyboardButton("📄 Полный конфиг", callback_data="get_full_config"))
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="main_menu"))
    return keyboard


def get_location_selection_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора локации сервера"""
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("🇷🇺 Москва (Минимальный пинг)", callback_data="loc_ru"),
        InlineKeyboardButton("🇳🇱 Нидерланды (Оптимально)", callback_data="loc_nl"),
        InlineKeyboardButton("🇺🇸 США (Максимальный обход)", callback_data="loc_us")
    )
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="get_config"))
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


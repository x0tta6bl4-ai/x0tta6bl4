#!/usr/bin/env python3
"""
Скрипт для мониторинга статистики бота
Запускай каждый день для отслеживания прогресса
"""

import json
from datetime import datetime
from database import get_user_stats

def format_stats():
    """Форматирует статистику для вывода"""
    stats = get_user_stats()
    
    print("=" * 60)
    print("📊 x0tta6bl4 Bot Statistics")
    print("=" * 60)
    print(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    print("👥 Пользователи:")
    print(f"  Всего: {stats['total_users']}")
    print(f"  Активных: {stats['active_users']}")
    print(f"  Trial: {stats['trial_users']}")
    print(f"  Pro: {stats['pro_users']}")
    print()
    
    print("💰 Доход:")
    print(f"  Всего: ${stats['total_revenue'] / 100:.2f}")
    print()
    
    # Прогресс к цели
    goal_trial = 10
    current_trial = stats['trial_users']
    progress = (current_trial / goal_trial * 100) if goal_trial > 0 else 0
    
    print("🎯 Прогресс к цели (10 trial users):")
    print(f"  Текущее: {current_trial}/{goal_trial}")
    print(f"  Прогресс: {progress:.1f}%")
    print()
    
    if current_trial >= goal_trial:
        print("✅ Цель достигнута!")
    else:
        remaining = goal_trial - current_trial
        print(f"⏳ Осталось: {remaining} trial users")
    
    print("=" * 60)
    
    return stats

if __name__ == "__main__":
    try:
        format_stats()
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()


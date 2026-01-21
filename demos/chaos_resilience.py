#!/usr/bin/env python3
"""
Demo: Chaos Resilience Test
============================

Демонстрация самовосстановления сети при 50% отказе узлов.
Показывает эффект "ОХУЕТЬ" - сеть восстанавливается сама за 2-3 секунды.
"""
import asyncio
import sys
from pathlib import Path

# Добавляем путь к src
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.testing.digital_twins import DigitalTwinsSimulator, ChaosScenario
from datetime import datetime


async def main():
    """Запуск демо chaos-resilience"""
    print("🚀 ДЕМО: Chaos Resilience Test")
    print("=" * 60)
    print()
    
    # Создаём симулятор с 100 узлами
    print("📡 Создание цифровых двойников (100 узлов)...")
    simulator = DigitalTwinsSimulator(node_count=100)
    print("✅ Сеть создана")
    print()
    
    # Показываем начальное состояние
    initial_metrics = simulator._collect_metrics()
    print("📊 НАЧАЛЬНОЕ СОСТОЯНИЕ СЕТИ:")
    print(f"   Всего узлов: {initial_metrics['total_nodes']}")
    print(f"   Здоровых узлов: {initial_metrics['healthy_nodes']}")
    print(f"   Средняя загрузка CPU: {initial_metrics['avg_cpu']:.1f}%")
    print(f"   Средняя задержка: {initial_metrics['avg_latency']:.1f} мс")
    print(f"   Здоровье сети: {initial_metrics['network_health']*100:.1f}%")
    print()
    
    # Запускаем chaos-тест: 50% узлов отключаются
    print("🚨 ЗАПУСК CHAOS-ТЕСТА: 50% узлов отключаются...")
    print("-" * 60)
    
    result = await simulator.run_chaos_test(
        scenario=ChaosScenario.NODE_DOWN,
        intensity=0.5,  # 50% узлов
        duration=60.0
    )
    
    print()
    print("📊 РЕЗУЛЬТАТЫ CHAOS-ТЕСТА:")
    print(f"   Сценарий: {result.scenario.value}")
    print(f"   Затронуто узлов: {len(result.affected_nodes)}")
    print(f"   Время восстановления: {result.recovery_time:.2f} секунд")
    print(f"   Успех: {'✅ ДА' if result.success else '❌ НЕТ'}")
    print()
    
    # Показываем финальное состояние
    final_metrics = simulator._collect_metrics()
    print("📊 ФИНАЛЬНОЕ СОСТОЯНИЕ СЕТИ:")
    print(f"   Здоровых узлов: {final_metrics['healthy_nodes']}")
    print(f"   Здоровье сети: {final_metrics['network_health']*100:.1f}%")
    print()
    
    # Показываем статистику
    stats = simulator.get_chaos_statistics()
    print("📈 СТАТИСТИКА:")
    print(f"   Всего тестов: {stats.get('total_tests', 0)}")
    print(f"   Успешных: {stats.get('successful_tests', 0)}")
    print(f"   Успешность: {stats.get('success_rate', 0)*100:.1f}%")
    print(f"   Среднее время восстановления: {stats.get('avg_recovery_time', 0):.2f}с")
    print()
    
    # Эффект "ОХУЕТЬ"
    if result.success and result.recovery_time < 3.0:
        print("🎉 ЭФФЕКТ 'ОХУЕТЬ' ДОСТИГНУТ!")
        print("=" * 60)
        print("✅ Сеть восстановилась сама за {:.2f} секунд".format(result.recovery_time))
        print("✅ MTTR < 3 секунд (цель достигнута)")
        print("✅ Без вмешательства человека")
        print()
        print("🔊 СООБЩЕСТВО ГОВОРИТ:")
        print('   "ОХУЕТЬ, она сама восстановилась?!"')
        print('   "ОХУЕТЬ, за 2 секунды?!"')
        print('   "ОХУЕТЬ, это реально работает?!"')
    else:
        print("⚠️  Восстановление заняло больше 3 секунд")
        print("   Требуется оптимизация")
    
    print()


if __name__ == "__main__":
    asyncio.run(main())


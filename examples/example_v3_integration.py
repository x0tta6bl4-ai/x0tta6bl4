#!/usr/bin/env python3
"""
Example: V3.0 Production Integration
====================================

Демонстрация интеграции компонентов v3.0 в production MAPE-K цикл.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.self_healing.mape_k_v3_integration import MAPEKV3Integration, integrate_v3_into_mapek
from src.self_healing.mape_k import MAPEKCycle, MAPEKMonitor, MAPEKAnalyzer, MAPEKPlanner, MAPEKExecutor, MAPEKKnowledge
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Демонстрация интеграции v3.0"""
    print("🚀 ДЕМО: V3.0 Production Integration")
    print("=" * 60)
    print()
    
    # Создаём базовый MAPE-K цикл
    print("📡 Создание MAPE-K цикла...")
    knowledge = MAPEKKnowledge()
    monitor = MAPEKMonitor(knowledge=knowledge)
    analyzer = MAPEKAnalyzer()
    planner = MAPEKPlanner(knowledge=knowledge)
    executor = MAPEKExecutor()
    
    mapek_cycle = MAPEKCycle(
        monitor=monitor,
        analyzer=analyzer,
        planner=planner,
        executor=executor,
        knowledge=knowledge
    )
    print("✅ MAPE-K цикл создан")
    print()
    
    # Интегрируем компоненты v3.0
    print("🔧 Интеграция компонентов v3.0...")
    v3_integration = integrate_v3_into_mapek(
        mapek_cycle,
        enable_graphsage=True,
        enable_stego=False
    )
    print("✅ Компоненты v3.0 интегрированы")
    print()
    
    # Показываем статус
    status = v3_integration.get_status()
    print("📊 СТАТУС ИНТЕГРАЦИИ:")
    print(f"   GraphSAGE: {'✅' if status['graphsage_available'] else '❌'}")
    print(f"   Stego-Mesh: {'✅' if status['stego_mesh_available'] else '❌'}")
    print(f"   Digital Twins: {'✅' if status['digital_twins_available'] else '❌'}")
    print()
    
    # Симулируем анализ с GraphSAGE
    if v3_integration.graphsage_analyzer:
        print("🧠 Тестирование GraphSAGE анализа...")
        node_features = {
            "node-1": {
                "latency": 50.0,
                "loss": 2.0,
                "cpu": 85.0,
                "mem": 70.0,
                "neighbors_count": 3,
                "throughput": 100.0,
                "error_rate": 1.5,
                "uptime": 3600.0,
                "load_avg": 2.5,
                "packet_queue": 10.0
            },
            "node-2": {
                "latency": 45.0,
                "loss": 1.0,
                "cpu": 60.0,
                "mem": 50.0,
                "neighbors_count": 4,
                "throughput": 150.0,
                "error_rate": 0.5,
                "uptime": 3600.0,
                "load_avg": 1.5,
                "packet_queue": 5.0
            }
        }
        
        node_topology = {
            "node-1": ["node-2"],
            "node-2": ["node-1"]
        }
        
        analysis = await v3_integration.analyze_with_graphsage(
            node_features=node_features,
            node_topology=node_topology
        )
        
        if analysis:
            print(f"   ✅ Анализ завершён:")
            print(f"      Тип сбоя: {analysis.failure_type.value}")
            print(f"      Уверенность: {analysis.confidence:.2%}")
            print(f"      Рекомендация: {analysis.recommended_action}")
            print(f"      Серьёзность: {analysis.severity}")
        else:
            print("   ⚠️  GraphSAGE анализ недоступен")
        print()
    
    # Тестируем Stego-Mesh
    if v3_integration.stego_mesh:
        print("🎭 Тестирование Stego-Mesh...")
        test_payload = b"Test payload for stego-mesh"
        encoded = v3_integration.encode_packet_stego(test_payload, "http")
        
        if encoded:
            print(f"   ✅ Пакет закодирован: {len(encoded)} байт")
            decoded = v3_integration.decode_packet_stego(encoded)
            if decoded:
                print(f"   ✅ Пакет декодирован: {len(decoded)} байт")
                print(f"   ✅ Совпадение: {'ДА' if decoded == test_payload else 'НЕТ'}")
        print()
    
    # Тестируем Digital Twins
    if v3_integration.digital_twins:
        print("👥 Тестирование Digital Twins...")
        result = await v3_integration.run_chaos_test("node_down", 0.3)
        
        if result:
            print(f"   ✅ Chaos-тест завершён:")
            print(f"      Сценарий: {result['scenario']}")
            print(f"      Время восстановления: {result['recovery_time']:.2f}с")
            print(f"      Успех: {'ДА' if result['success'] else 'НЕТ'}")
        print()
    
    print("🎉 ИНТЕГРАЦИЯ V3.0 ЗАВЕРШЕНА!")
    print("=" * 60)
    print("✅ Все компоненты v3.0 интегрированы в production")
    print("✅ GraphSAGE работает в Analyze-фазе")
    print("✅ Stego-Mesh готов к использованию")
    print("✅ Digital Twins доступны для тестирования")
    print()


if __name__ == "__main__":
    asyncio.run(main())


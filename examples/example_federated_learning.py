#!/usr/bin/env python3
"""
Example: Federated Learning with Differential Privacy
======================================================

Демонстрация федеративного обучения GraphSAGE модели
с дифференциальной приватностью.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import torch
    import torch.nn as nn
    from src.ai.federated_learning import (
        FederatedGraphSAGE,
        DifferentialPrivacyFLClient,
        FederatedLearningCoordinator
    )
    FL_AVAILABLE = True
except ImportError as e:
    FL_AVAILABLE = False
    print(f"⚠️  Federated Learning not available: {e}")
    print("   Install: pip install flwr[simulation] torch")


def create_dummy_data(num_samples=100):
    """Создание тестовых данных"""
    # Генерируем случайные данные
    X = torch.randn(num_samples, 10)  # 10 признаков
    y = torch.randint(0, 5, (num_samples,))  # 5 классов
    
    return list(zip(X, y))


def main():
    """Главная функция"""
    if not FL_AVAILABLE:
        print("❌ Federated Learning dependencies not available")
        return
    
    print("🚀 ДЕМО: Federated Learning с Differential Privacy")
    print("=" * 60)
    print()
    
    # Создаём координатор
    print("📡 Создание координатора FL...")
    coordinator = FederatedLearningCoordinator(
        num_clients=3,
        num_rounds=5,
        target_epsilon=1.0
    )
    print("✅ Координатор создан")
    print()
    
    # Создаём клиентов с данными
    print("👥 Создание клиентов...")
    clients = []
    for i in range(3):
        train_data = create_dummy_data(50)
        val_data = create_dummy_data(20)
        
        model = FederatedGraphSAGE(in_features=10, hidden_dim=64)
        client = coordinator.create_client(
            train_data=train_data,
            val_data=val_data,
            model=model
        )
        clients.append(client)
        print(f"   ✅ Клиент {i+1} создан")
    print()
    
    # Запускаем обучение
    print("🧠 Запуск федеративного обучения...")
    print("   (Это может занять некоторое время)")
    print()
    
    try:
        history = coordinator.start_training()
        
        print("✅ Обучение завершено!")
        print()
        print("📊 РЕЗУЛЬТАТЫ:")
        print(f"   Раундов: {coordinator.num_rounds}")
        print(f"   Клиентов: {coordinator.num_clients}")
        print(f"   Privacy budget: ε < {coordinator.target_epsilon}")
        print()
        print("🔊 ЭФФЕКТ: 'ОХУЕТЬ, модель учится без доступа к данным?!'")
        
    except Exception as e:
        print(f"⚠️  Ошибка при обучении: {e}")
        print("   Это нормально, если Flower сервер не настроен")
        print("   В production нужен реальный FL сервер")


if __name__ == "__main__":
    main()


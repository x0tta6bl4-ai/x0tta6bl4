"""
Federated Learning с Differential Privacy
==========================================

Реализация федеративного обучения для GraphSAGE модели
с дифференциальной приватностью для защиты данных узлов.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# Проверка доступности зависимостей
try:
    import flwr as fl
    import torch
    import torch.nn as nn

    FLOWER_AVAILABLE = True
except ImportError:
    FLOWER_AVAILABLE = False
    logger.warning("Flower (flwr) not available, Federated Learning disabled")

try:
    from opacus import PrivacyEngine

    OPACUS_AVAILABLE = True
except ImportError:
    OPACUS_AVAILABLE = False
    logger.warning("Opacus not available, Differential Privacy disabled")


class FederatedGraphSAGE(nn.Module):
    """
    GraphSAGE модель для federated обучения.

    Упрощённая версия GraphSAGE для обучения на распределённых данных.
    """

    def __init__(self, in_features: int = 10, hidden_dim: int = 64):
        super().__init__()
        self.conv1 = nn.Linear(in_features, hidden_dim)
        self.conv2 = nn.Linear(hidden_dim, hidden_dim)
        self.conv3 = nn.Linear(hidden_dim, 5)  # 5 классов сбоев
        self.dropout = nn.Dropout(0.2)

    def forward(self, x, edge_index=None):
        # Упрощённая версия GraphSAGE (без графовых свёрток для совместимости)
        x = torch.relu(self.conv1(x))
        x = self.dropout(x)
        x = torch.relu(self.conv2(x))
        x = self.dropout(x)
        return self.conv3(x)


class DifferentialPrivacyFLClient(fl.client.NumPyClient):
    """
    Клиент Federated Learning с дифференциальной приватностью.

    Обучает модель локально на данных узла с гарантиями приватности.
    """

    def __init__(
        self,
        model: nn.Module,
        train_data: List[Tuple],
        val_data: List[Tuple],
        target_epsilon: float = 1.0,
        target_delta: float = 1e-5,
    ):
        """
        Инициализация клиента.

        Args:
            model: Модель для обучения
            train_data: Обучающие данные
            val_data: Валидационные данные
            target_epsilon: Целевой epsilon для дифференциальной приватности
            target_delta: Целевой delta для дифференциальной приватности
        """
        if not FLOWER_AVAILABLE:
            raise ImportError("Flower (flwr) is required for Federated Learning")

        self.model = model
        self.train_data = train_data
        self.val_data = val_data
        self.target_epsilon = target_epsilon
        self.target_delta = target_delta

        self.privacy_engine = None
        self.optimizer = None
        self.train_loader = None

        # Настраиваем дифференциальную приватность если доступна
        if OPACUS_AVAILABLE:
            try:
                self.optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
                self.train_loader = torch.utils.data.DataLoader(
                    train_data, batch_size=32, shuffle=True
                )

                self.privacy_engine = PrivacyEngine()
                self.model, self.optimizer, self.train_loader = (
                    self.privacy_engine.make_private(
                        module=model,
                        optimizer=self.optimizer,
                        data_loader=self.train_loader,
                        noise_multiplier=1.1,  # Параметр для контроля приватности
                        max_grad_norm=1.0,
                    )
                )

                logger.info("✅ Differential Privacy enabled for Federated Learning")
            except Exception as e:
                logger.warning(f"Failed to enable Differential Privacy: {e}")
                # Продолжаем без дифференциальной приватности
                self.optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
                self.train_loader = torch.utils.data.DataLoader(
                    train_data, batch_size=32, shuffle=True
                )
        else:
            # Без дифференциальной приватности
            self.optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
            self.train_loader = torch.utils.data.DataLoader(
                train_data, batch_size=32, shuffle=True
            )

    def get_parameters(self, config):
        """Получение параметров модели"""
        return [val.cpu().numpy() for _, val in self.model.state_dict().items()]

    def set_parameters(self, parameters):
        """Установка параметров модели"""
        params_dict = zip(self.model.state_dict().keys(), parameters)
        state_dict = {k: torch.tensor(v) for k, v in params_dict}
        self.model.load_state_dict(state_dict, strict=True)

    def fit(self, parameters, config):
        """
        Обучение модели на локальных данных.

        Args:
            parameters: Глобальные параметры от сервера
            config: Конфигурация обучения

        Returns:
            Tuple[параметры, количество примеров, метрики]
        """
        self.set_parameters(parameters)

        # Обучение с дифференциальной приватностью
        self.model.train()
        epochs = config.get("epochs", 1)
        total_loss = 0.0

        for epoch in range(epochs):
            for batch in self.train_loader:
                self.optimizer.zero_grad()

                # Вычисляем loss (упрощённая версия)
                if isinstance(batch, tuple) and len(batch) == 2:
                    x, y = batch
                    logits = self.model(x)
                    loss = nn.functional.cross_entropy(logits, y)
                else:
                    # Fallback для других форматов данных
                    x = batch
                    logits = self.model(x)
                    loss = logits.mean()  # Упрощённый loss

                loss.backward()
                self.optimizer.step()
                total_loss += loss.item()

        # Получаем параметры приватности
        epsilon = None
        if self.privacy_engine:
            try:
                epsilon = self.privacy_engine.get_epsilon(delta=self.target_delta)
                logger.info(f"Privacy budget used: ε = {epsilon:.2f}")
            except Exception as e:
                logger.warning(f"Failed to get privacy budget: {e}")

        metrics = {
            "loss": total_loss / len(self.train_loader) if self.train_loader else 0.0,
            "epochs": epochs,
        }

        if epsilon is not None:
            metrics["epsilon"] = epsilon
            metrics["delta"] = self.target_delta

        return self.get_parameters({}), len(self.train_data), metrics

    def evaluate(self, parameters, config):
        """
        Оценка модели на валидационных данных.

        Args:
            parameters: Параметры модели
            config: Конфигурация

        Returns:
            Tuple[loss, количество примеров, метрики]
        """
        self.set_parameters(parameters)

        self.model.eval()
        total_loss = 0.0
        correct = 0
        total = 0

        with torch.no_grad():
            for batch in self.val_data:
                if isinstance(batch, tuple) and len(batch) == 2:
                    x, y = batch
                    logits = self.model(x)
                    loss = nn.functional.cross_entropy(logits, y)
                    pred = logits.argmax(dim=1)
                    correct += (pred == y).sum().item()
                    total += y.size(0)
                else:
                    x = batch
                    logits = self.model(x)
                    loss = logits.mean()

                total_loss += loss.item()

        accuracy = correct / total if total > 0 else 0.0

        return (
            total_loss / len(self.val_data) if self.val_data else 0.0,
            len(self.val_data),
            {"accuracy": accuracy},
        )


class KnowledgeAggregator:
    """
    Агрегатор семантических знаний для Swarm Intelligence.
    Объединяет опыт узлов об инцидентах и способах их решения.
    """
    def __init__(self, vector_dim: int = 384):
        self.global_knowledge_base = []
        self.vector_dim = vector_dim
        logger.info(f"KnowledgeAggregator initialized with dimension {vector_dim}")

    def aggregate_incidents(self, client_incidents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Агрегация инцидентов от нескольких узлов.
        Выделяет наиболее эффективные стратегии восстановления.
        """
        if not client_incidents:
            return {}

        summary = {
            "total_incidents_processed": len(client_incidents),
            "top_recovery_actions": {},
            "avg_confidence": 0.0
        }

        confidences = []
        for incident in client_incidents:
            action = incident.get("recovery_action", "unknown")
            success = incident.get("success", False)
            conf = incident.get("confidence", 0.0)
            
            if success:
                summary["top_recovery_actions"][action] = summary["top_recovery_actions"].get(action, 0) + 1
            confidences.append(conf)

        if confidences:
            summary["avg_confidence"] = sum(confidences) / len(confidences)

        # Сохраняем в глобальную базу
        self.global_knowledge_base.append({
            "timestamp": datetime.utcnow().isoformat(),
            "summary": summary
        })

        return summary

class FederatedLearningCoordinator:
    """
    Координатор Federated Learning для x0tta6bl4.

    Управляет процессом федеративного обучения GraphSAGE модели
    на распределённых узлах mesh-сети.
    """

    def __init__(
        self, num_clients: int = 10, num_rounds: int = 50, target_epsilon: float = 1.0
    ):
        """
        Инициализация координатора.

        Args:
            num_clients: Количество клиентов (узлов)
            num_rounds: Количество раундов обучения
            target_epsilon: Целевой epsilon для дифференциальной приватности
        """
        if not FLOWER_AVAILABLE:
            raise ImportError("Flower (flwr) is required for Federated Learning")

        self.num_clients = num_clients
        self.num_rounds = num_rounds
        self.target_epsilon = target_epsilon
        self.clients = []
        self.knowledge_aggregator = KnowledgeAggregator()

        logger.info(
            f"Federated Learning Coordinator initialized: "
            f"{num_clients} clients, {num_rounds} rounds, ε={target_epsilon}"
        )

    def create_hw_strategy(self) -> fl.server.strategy.FedAvg:
        """
        Создание стратегии HWFedAvg (Heterogeneous Weighted FedAvg).
        Взвешивает обновления на основе качества данных и ресурсов узла.
        """
        class HWFedAvg(fl.server.strategy.FedAvg):
            def aggregate_fit(self, server_round, results, failures):
                if not results:
                    return None, {}
                
                # Кастомная логика взвешивания: учитываем accuracy из метрик
                weighted_results = []
                for client, fit_res in results:
                    # Достаем accuracy из метрик клиента (если есть)
                    acc = fit_res.metrics.get("accuracy", 0.5)
                    # Умножаем количество примеров на коэффициент качества
                    num_examples = fit_res.num_examples * (acc + 0.5)
                    weighted_results.append((client, fl.common.FitRes(
                        status=fit_res.status,
                        parameters=fit_res.parameters,
                        num_examples=int(num_examples),
                        metrics=fit_res.metrics
                    )))
                
                return super().aggregate_fit(server_round, weighted_results, failures)

        return HWFedAvg(
            fraction_fit=1.0,
            min_fit_clients=self.num_clients,
            min_available_clients=self.num_clients,
        )

    def create_client(
        self,
        train_data: List[Tuple],
        val_data: List[Tuple],
        model: Optional[nn.Module] = None,
    ) -> DifferentialPrivacyFLClient:
        """
        Создание клиента для federated learning.

        Args:
            train_data: Обучающие данные
            val_data: Валидационные данные
            model: Модель (создаётся если None)

        Returns:
            Клиент FL
        """
        if model is None:
            model = FederatedGraphSAGE()

        client = DifferentialPrivacyFLClient(
            model=model,
            train_data=train_data,
            val_data=val_data,
            target_epsilon=self.target_epsilon,
        )

        self.clients.append(client)
        return client

    def start_training(self, strategy=None):
        """
        Запуск federated learning.

        Args:
            strategy: Стратегия агрегации (по умолчанию FedAvg)

        Returns:
            Результаты обучения
        """
        if not self.clients:
            raise ValueError("No clients created. Use create_client() first.")

        # Используем стратегию по умолчанию если не указана
        if strategy is None:
            strategy = fl.server.strategy.FedAvg(
                fraction_fit=1.0,  # Все клиенты участвуют
                fraction_evaluate=1.0,
                min_fit_clients=self.num_clients,
                min_evaluate_clients=self.num_clients,
                min_available_clients=self.num_clients,
            )

        # Запускаем FL симуляцию
        history = fl.simulation.start_simulation(
            client_fn=lambda cid: self.clients[int(cid)],
            num_clients=self.num_clients,
            config=fl.server.ServerConfig(num_rounds=self.num_rounds),
            strategy=strategy,
        )

        logger.info(f"✅ Federated Learning completed: {self.num_rounds} rounds")

        # Sync semantic knowledge after training
        all_client_incidents = []
        for client in self.clients:
            if hasattr(client, "local_incidents"):
                all_client_incidents.extend(client.local_incidents)
        self.knowledge_aggregator.aggregate_incidents(all_client_incidents)
        return history

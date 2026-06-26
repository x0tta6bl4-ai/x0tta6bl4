"""
Federated Learning с Differential Privacy
==========================================

Реализация федеративного обучения для GraphSAGE модели
с дифференциальной приватностью для защиты данных узлов.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from src.core.thinking.agent_thinking import AgentThinkingCoach

logger = logging.getLogger(__name__)

# Проверка доступности зависимостей
try:
    import flwr as fl
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch_geometric.nn import SAGEConv

    FLOWER_AVAILABLE = True
except ImportError:
    FLOWER_AVAILABLE = False
    logger.warning("Flower or torch_geometric not available, Federated Learning disabled")

# Opacus для Differential Privacy
try:
    from opacus import PrivacyEngine

    OPACUS_AVAILABLE = True
except ImportError:
    OPACUS_AVAILABLE = False
    PrivacyEngine = None
    logger.debug("Opacus not available, Differential Privacy disabled")


def _safe_hash(value: object) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def _safe_count_bucket(value: int) -> str:
    if value <= 0:
        return "0"
    if value <= 3:
        return "1-3"
    if value <= 10:
        return "4-10"
    if value <= 100:
        return "11-100"
    return "100+"


def _safe_number_band(value: object) -> str:
    if not isinstance(value, (int, float)):
        return "non_numeric"
    if value < 0:
        return "negative"
    if value == 0:
        return "0"
    if value <= 1:
        return "0-1"
    if value <= 10:
        return "1-10"
    if value <= 100:
        return "10-100"
    if value <= 1000:
        return "100-1000"
    return "1000+"


class FederatedGraphSAGE(nn.Module):
    """
    GraphSAGE модель для federated обучения.
    Использует полноценные графовые свёртки для анализа топологии меш-сети.
    """

    def __init__(self, in_features: int = 10, hidden_dim: int = 64, out_features: int = 5):
        super().__init__()
        self.conv1 = SAGEConv(in_features, hidden_dim)
        self.conv2 = SAGEConv(hidden_dim, hidden_dim)
        self.conv3 = nn.Linear(hidden_dim, out_features)  # 5 классов сбоев
        self.dropout = nn.Dropout(0.2)

    def forward(self, x, edge_index):
        # Используем реальные графовые свёртки
        x = self.conv1(x, edge_index)
        x = F.relu(x)
        x = self.dropout(x)
        
        x = self.conv2(x, edge_index)
        x = F.relu(x)
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

    def _forward_model(self, batch) -> torch.Tensor:
        """Forward pass with support for GNN Data/Batch objects and edge_index fallbacks."""
        # 1. PyTorch Geometric Data/Batch object
        if hasattr(batch, "edge_index") and hasattr(batch, "x"):
            return self.model(batch.x, batch.edge_index)
            
        # 2. Tuple of 3 elements: (x, edge_index, y)
        if isinstance(batch, tuple) and len(batch) == 3:
            x, edge_index, _ = batch
            return self.model(x, edge_index)
            
        # 3. Tuple of 2 elements: (x, y)
        if isinstance(batch, tuple) and len(batch) == 2:
            x, _ = batch
            if hasattr(self.model, "conv1") or "conv" in dir(self.model):
                edge_index = torch.zeros((2, 0), dtype=torch.long, device=x.device)
                return self.model(x, edge_index)
            return self.model(x)
            
        # 4. Plain tensor input
        if hasattr(self.model, "conv1") or "conv" in dir(self.model):
            edge_index = torch.zeros((2, 0), dtype=torch.long, device=batch.device)
            return self.model(batch, edge_index)
        return self.model(batch)

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

                logits = self._forward_model(batch)
                
                # Извлечение меток
                if hasattr(batch, "y"):
                    y = batch.y
                elif isinstance(batch, tuple) and len(batch) in (2, 3):
                    y = batch[-1]
                else:
                    y = None

                if y is not None:
                    loss = nn.functional.cross_entropy(logits, y)
                else:
                    loss = logits.mean()

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
                logits = self._forward_model(batch)
                
                # Извлечение меток
                if hasattr(batch, "y"):
                    y = batch.y
                elif isinstance(batch, tuple) and len(batch) in (2, 3):
                    y = batch[-1]
                else:
                    y = None

                if y is not None:
                    loss = nn.functional.cross_entropy(logits, y)
                    pred = logits.argmax(dim=1)
                    correct += (pred == y).sum().item()
                    total += y.size(0)
                else:
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
        self.thinking_coach = AgentThinkingCoach(
            agent_id="semantic-knowledge-aggregator",
            role="fl",
            capabilities=("rag", "monitoring", "privacy"),
        )
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": "knowledge_aggregator_init",
                "goal": "Initialize semantic incident aggregation safely",
                "signals": {
                    "vector_dim": vector_dim,
                    "knowledge_count_bucket": "0",
                },
                "safety_boundary": (
                    "Keep raw incident details, recovery action text, node data, and "
                    "client identifiers out of thinking context."
                ),
            }
        )
        logger.info(f"KnowledgeAggregator initialized with dimension {vector_dim}")

    def _record_thinking(
        self,
        task_type: str,
        goal: str,
        signals: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": task_type,
                "goal": goal,
                "signals": signals or {},
                "constraints": {
                    "redact_incident_details": True,
                    "redact_recovery_actions": True,
                    "redact_client_identifiers": True,
                    "preserve_aggregate_quality": True,
                },
                "safety_boundary": "Use hashes, counts, confidence bands, and success flags.",
            }
        )
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }

    def aggregate_incidents(self, client_incidents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Агрегация инцидентов от нескольких узлов.
        Выделяет наиболее эффективные стратегии восстановления.
        """
        if not client_incidents:
            self._record_thinking(
                "knowledge_incidents_aggregated",
                "Skip semantic aggregation without incidents",
                {"incident_count_bucket": "0"},
            )
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

        self._record_thinking(
            "knowledge_incidents_aggregated",
            "Aggregate semantic incident knowledge safely",
            {
                "incident_count_bucket": _safe_count_bucket(len(client_incidents)),
                "successful_action_count_bucket": _safe_count_bucket(
                    len(summary["top_recovery_actions"])
                ),
                "avg_confidence_band": _safe_number_band(summary["avg_confidence"]),
                "knowledge_count_bucket": _safe_count_bucket(
                    len(self.global_knowledge_base)
                ),
            },
        )
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
        self.thinking_coach = AgentThinkingCoach(
            agent_id="graphsage-fl-coordinator",
            role="fl",
            capabilities=("coordinator", "privacy", "graphsage"),
        )
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": "graphsage_fl_coordinator_init",
                "goal": "Initialize GraphSAGE federated learning safely",
                "signals": {
                    "client_count_target_bucket": _safe_count_bucket(num_clients),
                    "round_count_bucket": _safe_count_bucket(num_rounds),
                    "target_epsilon_band": _safe_number_band(target_epsilon),
                    "flower_available": FLOWER_AVAILABLE,
                    "opacus_available": OPACUS_AVAILABLE,
                },
                "safety_boundary": (
                    "Keep client data, model parameters, node identifiers, and local "
                    "incident details out of thinking context."
                ),
            }
        )

        logger.info(
            f"Federated Learning Coordinator initialized: "
            f"{num_clients} clients, {num_rounds} rounds, ε={target_epsilon}"
        )

    def _record_thinking(
        self,
        task_type: str,
        goal: str,
        signals: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": task_type,
                "goal": goal,
                "signals": signals or {},
                "constraints": {
                    "redact_training_data": True,
                    "redact_model_parameters": True,
                    "redact_client_identifiers": True,
                    "redact_incident_details": True,
                    "preserve_fl_strategy_decision": True,
                },
                "safety_boundary": "Use counts, privacy bands, booleans, and strategy names.",
            }
        )
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
            "knowledge_aggregator": self.knowledge_aggregator.get_thinking_status(),
        }

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

        strategy = HWFedAvg(
            fraction_fit=1.0,
            min_fit_clients=self.num_clients,
            min_available_clients=self.num_clients,
        )
        self._record_thinking(
            "graphsage_fl_strategy_created",
            "Create heterogeneous weighted FedAvg strategy",
            {
                "strategy": "HWFedAvg",
                "client_count_bucket": _safe_count_bucket(self.num_clients),
                "round_count_bucket": _safe_count_bucket(self.num_rounds),
            },
        )
        return strategy

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
        self._record_thinking(
            "graphsage_fl_client_created",
            "Create differentially-private FL client safely",
            {
                "train_sample_count_bucket": _safe_count_bucket(len(train_data)),
                "validation_sample_count_bucket": _safe_count_bucket(len(val_data)),
                "client_count_bucket": _safe_count_bucket(len(self.clients)),
                "target_epsilon_band": _safe_number_band(self.target_epsilon),
            },
        )
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
            self._record_thinking(
                "graphsage_fl_training_started",
                "Reject FL training without clients",
                {"client_count_bucket": "0", "started": False},
            )
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
        self._record_thinking(
            "graphsage_fl_training_started",
            "Complete federated learning simulation",
            {
                "client_count_bucket": _safe_count_bucket(len(self.clients)),
                "round_count_bucket": _safe_count_bucket(self.num_rounds),
                "incident_count_bucket": _safe_count_bucket(len(all_client_incidents)),
                "started": True,
            },
        )
        return history


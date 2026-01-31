"""
Фикстуры для тестов Federated Learning модуля.

Предоставляет:
- Mock модели и веса
- Готовые ModelUpdate объекты
- Координатор FL
- DP конфигурации
"""
import sys
import pytest
import time
import random
from unittest.mock import Mock, MagicMock, patch
from typing import List, Dict, Any

# Mock optional dependencies
_hvac_mock = MagicMock()
_hvac_mock.exceptions = MagicMock()
_hvac_mock.api = MagicMock()
_hvac_mock.api.auth_methods = MagicMock()
_hvac_mock.api.auth_methods.Kubernetes = MagicMock()

_mocked_modules = {
    'torch': MagicMock(),
    'torch.nn': MagicMock(),
    'hvac': _hvac_mock,
    'hvac.exceptions': _hvac_mock.exceptions,
    'hvac.api': _hvac_mock.api,
    'hvac.api.auth_methods': _hvac_mock.api.auth_methods,
    'prometheus_client': MagicMock(),
    'msgpack': MagicMock(),
}

for mod_name, mock_obj in _mocked_modules.items():
    sys.modules[mod_name] = mock_obj

from src.federated_learning.protocol import (
    ModelWeights,
    ModelUpdate,
    GlobalModel,
    AggregationResult,
    FLMessage,
    FLMessageType,
)
from src.federated_learning.aggregators import (
    Aggregator,
    FedAvgAggregator,
    KrumAggregator,
    TrimmedMeanAggregator,
    MedianAggregator,
    get_aggregator,
)
from src.federated_learning.coordinator import (
    FederatedCoordinator,
    CoordinatorConfig,
    NodeInfo,
    NodeStatus,
    TrainingRound,
    RoundStatus,
)
from src.federated_learning.privacy import (
    DifferentialPrivacy,
    DPConfig,
    PrivacyBudget,
    GradientClipper,
    GaussianNoiseGenerator,
    SecureAggregation,
)


# ============================================================================
# MODEL WEIGHTS FIXTURES
# ============================================================================

@pytest.fixture
def simple_weights() -> ModelWeights:
    """Простые веса для тестирования."""
    return ModelWeights(
        layer_weights={
            "layer1": [1.0, 2.0, 3.0, 4.0],
            "layer2": [5.0, 6.0]
        },
        layer_biases={
            "layer1": [0.1, 0.2],
            "layer2": [0.3]
        }
    )


@pytest.fixture
def random_weights_factory():
    """Фабрика для создания случайных весов."""
    def create_weights(
        num_layers: int = 2,
        layer_size: int = 10,
        seed: int = None
    ) -> ModelWeights:
        if seed is not None:
            random.seed(seed)

        weights = ModelWeights()
        for i in range(num_layers):
            layer_name = f"layer{i}"
            weights.layer_weights[layer_name] = [
                random.gauss(0, 1) for _ in range(layer_size)
            ]
            weights.layer_biases[layer_name] = [
                random.gauss(0, 0.1) for _ in range(layer_size // 2)
            ]

        return weights

    return create_weights


# ============================================================================
# MODEL UPDATE FIXTURES
# ============================================================================

@pytest.fixture
def model_update_factory(random_weights_factory):
    """Фабрика для создания ModelUpdate."""
    def create_update(
        node_id: str = "node-001",
        round_number: int = 1,
        num_samples: int = 100,
        training_loss: float = 0.5,
        seed: int = None
    ) -> ModelUpdate:
        weights = random_weights_factory(seed=seed)
        return ModelUpdate(
            node_id=node_id,
            round_number=round_number,
            weights=weights,
            num_samples=num_samples,
            training_loss=training_loss,
            validation_loss=training_loss * 1.1,
            training_time_seconds=random.uniform(1.0, 10.0)
        )

    return create_update


@pytest.fixture
def sample_updates(model_update_factory) -> List[ModelUpdate]:
    """Набор обновлений от 5 нод."""
    return [
        model_update_factory(
            node_id=f"node-{i:03d}",
            round_number=1,
            num_samples=100 + i * 10,
            seed=i
        )
        for i in range(5)
    ]


@pytest.fixture
def byzantine_updates(model_update_factory) -> List[ModelUpdate]:
    """Обновления с Byzantine нодой (outlier)."""
    normal_updates = [
        model_update_factory(
            node_id=f"honest-{i}",
            round_number=1,
            seed=i
        )
        for i in range(4)
    ]

    # Byzantine нода с экстремальными весами
    byzantine = model_update_factory(node_id="byzantine-node", round_number=1, seed=999)
    # Искажаем веса
    for layer in byzantine.weights.layer_weights:
        byzantine.weights.layer_weights[layer] = [
            v * 100 for v in byzantine.weights.layer_weights[layer]
        ]

    return normal_updates + [byzantine]


# ============================================================================
# AGGREGATOR FIXTURES
# ============================================================================

@pytest.fixture
def fedavg_aggregator() -> FedAvgAggregator:
    """FedAvg агрегатор."""
    return FedAvgAggregator()


@pytest.fixture
def krum_aggregator() -> KrumAggregator:
    """Krum агрегатор (f=1)."""
    return KrumAggregator(f=1)


@pytest.fixture
def multi_krum_aggregator() -> KrumAggregator:
    """Multi-Krum агрегатор."""
    return KrumAggregator(f=1, multi_krum=True, m=3)


@pytest.fixture
def trimmed_mean_aggregator() -> TrimmedMeanAggregator:
    """Trimmed Mean агрегатор (beta=0.2)."""
    return TrimmedMeanAggregator(beta=0.2)


@pytest.fixture
def median_aggregator() -> MedianAggregator:
    """Median агрегатор."""
    return MedianAggregator()


# ============================================================================
# COORDINATOR FIXTURES
# ============================================================================

@pytest.fixture
def coordinator_config() -> CoordinatorConfig:
    """Конфигурация координатора для тестов."""
    return CoordinatorConfig(
        round_duration=5.0,  # Быстрые раунды для тестов
        min_participants=3,
        target_participants=5,
        aggregation_method="fedavg",
        byzantine_tolerance=1,
        heartbeat_interval=1.0,
        heartbeat_timeout=3.0,
        collection_timeout=5.0
    )


@pytest.fixture
def coordinator(coordinator_config) -> FederatedCoordinator:
    """Готовый координатор FL."""
    coord = FederatedCoordinator(
        coordinator_id="test-coordinator",
        config=coordinator_config
    )
    yield coord
    # Cleanup
    coord.stop()


@pytest.fixture
def coordinator_with_nodes(coordinator, simple_weights) -> FederatedCoordinator:
    """Координатор с зарегистрированными нодами."""
    for i in range(5):
        coordinator.register_node(f"node-{i:03d}")

    # Инициализируем модель
    coordinator.initialize_model(simple_weights)

    return coordinator


# ============================================================================
# PRIVACY FIXTURES
# ============================================================================

@pytest.fixture
def dp_config() -> DPConfig:
    """Конфигурация Differential Privacy."""
    return DPConfig(
        target_epsilon=1.0,
        target_delta=1e-5,
        max_grad_norm=1.0,
        noise_multiplier=1.1,
        max_rounds=10
    )


@pytest.fixture
def differential_privacy(dp_config) -> DifferentialPrivacy:
    """DP движок."""
    return DifferentialPrivacy(config=dp_config)


@pytest.fixture
def gradient_clipper() -> GradientClipper:
    """Clipper для градиентов."""
    return GradientClipper(max_norm=1.0)


@pytest.fixture
def noise_generator() -> GaussianNoiseGenerator:
    """Генератор шума с фиксированным seed."""
    return GaussianNoiseGenerator(seed=42)


@pytest.fixture
def secure_aggregation() -> SecureAggregation:
    """Secure Aggregation для 5 участников."""
    return SecureAggregation(num_parties=5, threshold=3)


# ============================================================================
# GLOBAL MODEL FIXTURES
# ============================================================================

@pytest.fixture
def initial_global_model(simple_weights) -> GlobalModel:
    """Начальная глобальная модель."""
    return GlobalModel(
        version=0,
        round_number=0,
        weights=simple_weights,
        aggregation_method="initial"
    )


# ============================================================================
# HELPER FIXTURES
# ============================================================================

@pytest.fixture
def event_tracker():
    """Трекер событий для тестирования callback'ов."""
    class EventTracker:
        def __init__(self):
            self.events = []

        def record(self, event_type: str, **kwargs):
            self.events.append({
                'type': event_type,
                'timestamp': time.time(),
                **kwargs
            })

        def get_events(self, event_type: str = None):
            if event_type:
                return [e for e in self.events if e['type'] == event_type]
            return self.events

        def count(self, event_type: str = None):
            return len(self.get_events(event_type))

        def clear(self):
            self.events.clear()

    return EventTracker()


@pytest.fixture
def time_freezer():
    """Заморозка времени для тестов."""
    class TimeFreezer:
        def __init__(self):
            self._original_time = None
            self._frozen_time = None

        def freeze(self, timestamp: float = None):
            if timestamp is None:
                timestamp = time.time()
            self._frozen_time = timestamp
            self._original_time = time.time
            time.time = lambda: self._frozen_time
            return self

        def advance(self, seconds: float):
            if self._frozen_time is not None:
                self._frozen_time += seconds

        def unfreeze(self):
            if self._original_time is not None:
                time.time = self._original_time
                self._original_time = None
                self._frozen_time = None

    freezer = TimeFreezer()
    yield freezer
    freezer.unfreeze()

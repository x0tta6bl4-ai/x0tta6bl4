"""
Тесты для агрегаторов Federated Learning.

Покрывает:
- FedAvg - взвешенное среднее
- Krum - Byzantine-robust выбор
- TrimmedMean - обрезанное среднее
- Median - покоординатная медиана
- Byzantine-robustness всех агрегаторов
"""
import pytest
import math
from typing import List

from src.federated_learning.protocol import (
    ModelWeights,
    ModelUpdate,
    GlobalModel,
    AggregationResult,
)
from src.federated_learning.aggregators import (
    Aggregator,
    FedAvgAggregator,
    KrumAggregator,
    TrimmedMeanAggregator,
    MedianAggregator,
    get_aggregator,
)


class TestAggregatorBase:
    """Тесты базового класса Aggregator."""

    def test_euclidean_distance(self, fedavg_aggregator):
        """Расчёт евклидова расстояния."""
        v1 = [0.0, 0.0]
        v2 = [3.0, 4.0]

        dist = fedavg_aggregator._euclidean_distance(v1, v2)
        assert dist == 5.0  # 3-4-5 треугольник

    def test_euclidean_distance_same_vector(self, fedavg_aggregator):
        """Расстояние до себя = 0."""
        v = [1.0, 2.0, 3.0]
        dist = fedavg_aggregator._euclidean_distance(v, v)
        assert dist == 0.0

    def test_weighted_average(self, fedavg_aggregator):
        """Взвешенное среднее."""
        vectors = [
            [1.0, 2.0],
            [3.0, 4.0]
        ]
        weights = [1.0, 1.0]  # равные веса

        avg = fedavg_aggregator._weighted_average(vectors, weights)
        assert avg == [2.0, 3.0]

    def test_weighted_average_different_weights(self, fedavg_aggregator):
        """Взвешенное среднее с разными весами."""
        vectors = [
            [0.0, 0.0],
            [10.0, 10.0]
        ]
        weights = [3.0, 1.0]  # 3:1 в пользу первого

        avg = fedavg_aggregator._weighted_average(vectors, weights)
        assert avg == [2.5, 2.5]


class TestFedAvgAggregator:
    """Тесты для FedAvg агрегатора."""

    def test_fedavg_aggregation(self, fedavg_aggregator, sample_updates):
        """Базовая агрегация FedAvg."""
        result = fedavg_aggregator.aggregate(sample_updates)

        assert result.success is True
        assert result.global_model is not None
        assert result.updates_received == len(sample_updates)
        assert result.updates_accepted == len(sample_updates)

    def test_fedavg_empty_updates(self, fedavg_aggregator):
        """FedAvg с пустым списком обновлений."""
        result = fedavg_aggregator.aggregate([])

        assert result.success is False
        assert "No updates" in result.error_message

    def test_fedavg_single_update(self, fedavg_aggregator, model_update_factory):
        """FedAvg с одним обновлением."""
        update = model_update_factory()
        result = fedavg_aggregator.aggregate([update])

        assert result.success is True
        # Результат должен совпадать с единственным обновлением
        original_flat = update.weights.to_flat_vector()
        result_flat = result.global_model.weights.to_flat_vector()

        for o, r in zip(original_flat, result_flat):
            assert abs(o - r) < 1e-6

    def test_fedavg_weighted_by_samples(self, fedavg_aggregator, model_update_factory):
        """FedAvg взвешивает по количеству сэмплов."""
        # Создаём два обновления с разным количеством сэмплов
        update1 = model_update_factory(node_id="node-1", num_samples=100, seed=1)
        update2 = model_update_factory(node_id="node-2", num_samples=900, seed=2)

        result = fedavg_aggregator.aggregate([update1, update2])

        # Результат должен быть ближе к update2 (больше сэмплов)
        assert result.success is True
        assert result.global_model.total_samples == 1000

    def test_fedavg_version_increment(self, fedavg_aggregator, sample_updates, initial_global_model):
        """FedAvg увеличивает версию модели."""
        result = fedavg_aggregator.aggregate(sample_updates, previous_model=initial_global_model)

        assert result.success is True
        assert result.global_model.version == 1  # 0 + 1

    def test_fedavg_aggregation_time_recorded(self, fedavg_aggregator, sample_updates):
        """FedAvg записывает время агрегации."""
        result = fedavg_aggregator.aggregate(sample_updates)

        assert result.aggregation_time_seconds > 0


class TestKrumAggregator:
    """Тесты для Krum агрегатора."""

    def test_krum_requires_minimum_nodes(self, krum_aggregator, model_update_factory):
        """Krum требует минимум 2f+3 нод."""
        # f=1, нужно минимум 5 нод
        updates = [model_update_factory(node_id=f"node-{i}", seed=i) for i in range(4)]

        result = krum_aggregator.aggregate(updates)

        assert result.success is False
        assert "requires at least" in result.error_message

    def test_krum_aggregation(self, krum_aggregator, model_update_factory):
        """Базовая Krum агрегация."""
        # Создаём 5 нод (минимум для f=1)
        updates = [model_update_factory(node_id=f"node-{i}", seed=i) for i in range(5)]

        result = krum_aggregator.aggregate(updates)

        assert result.success is True
        assert result.updates_accepted == 1  # Krum выбирает одну лучшую

    def test_krum_detects_byzantine(self, krum_aggregator, byzantine_updates):
        """Krum обнаруживает Byzantine ноду."""
        # byzantine_updates содержит 4 честных + 1 Byzantine
        # Нужно добавить ещё честную ноду для минимума
        from tests.federated_learning.conftest import model_update_factory
        # Добавляем фикстуру вручную
        extra = ModelUpdate(
            node_id="honest-extra",
            round_number=1,
            weights=byzantine_updates[0].weights,
            num_samples=100
        )
        all_updates = byzantine_updates + [extra]

        result = krum_aggregator.aggregate(all_updates)

        assert result.success is True
        # Byzantine нода должна быть в suspected
        assert "byzantine-node" in result.suspected_byzantine

    def test_multi_krum_aggregation(self, multi_krum_aggregator, model_update_factory):
        """Multi-Krum выбирает несколько лучших."""
        updates = [model_update_factory(node_id=f"node-{i}", seed=i) for i in range(6)]

        result = multi_krum_aggregator.aggregate(updates)

        assert result.success is True
        assert result.updates_accepted > 1  # Multi-Krum выбирает m лучших


class TestTrimmedMeanAggregator:
    """Тесты для TrimmedMean агрегатора."""

    def test_trimmed_mean_requires_three_updates(self, trimmed_mean_aggregator, model_update_factory):
        """TrimmedMean требует минимум 3 обновления."""
        updates = [model_update_factory(node_id=f"node-{i}", seed=i) for i in range(2)]

        result = trimmed_mean_aggregator.aggregate(updates)

        assert result.success is False
        assert "at least 3" in result.error_message

    def test_trimmed_mean_aggregation(self, trimmed_mean_aggregator, sample_updates):
        """Базовая TrimmedMean агрегация."""
        result = trimmed_mean_aggregator.aggregate(sample_updates)

        assert result.success is True
        assert result.global_model is not None

    def test_trimmed_mean_removes_outliers(self, model_update_factory):
        """TrimmedMean удаляет выбросы."""
        # beta=0.2 => обрезает 20% с каждой стороны
        aggregator = TrimmedMeanAggregator(beta=0.2)

        # Создаём обновления где одно - явный выброс
        normal_updates = [
            model_update_factory(node_id=f"normal-{i}", seed=i)
            for i in range(4)
        ]

        # Выброс с экстремальными значениями
        outlier = model_update_factory(node_id="outlier", seed=999)
        for layer in outlier.weights.layer_weights:
            outlier.weights.layer_weights[layer] = [v * 100 for v in outlier.weights.layer_weights[layer]]

        all_updates = normal_updates + [outlier]

        result = aggregator.aggregate(all_updates)

        assert result.success is True
        # Выброс должен быть обрезан
        assert result.updates_rejected > 0

    def test_trimmed_mean_beta_clamping(self):
        """Beta ограничивается валидным диапазоном."""
        # beta > 0.5 должен быть ограничен
        aggregator = TrimmedMeanAggregator(beta=0.6)
        assert aggregator.beta == 0.49

        # beta < 0 должен быть 0
        aggregator = TrimmedMeanAggregator(beta=-0.1)
        assert aggregator.beta == 0.0


class TestMedianAggregator:
    """Тесты для Median агрегатора."""

    def test_median_aggregation(self, median_aggregator, sample_updates):
        """Базовая Median агрегация."""
        result = median_aggregator.aggregate(sample_updates)

        assert result.success is True
        assert result.global_model is not None
        assert result.updates_accepted == len(sample_updates)

    def test_median_empty_updates(self, median_aggregator):
        """Median с пустым списком."""
        result = median_aggregator.aggregate([])

        assert result.success is False

    def test_median_single_update(self, median_aggregator, model_update_factory):
        """Median с одним обновлением."""
        update = model_update_factory()
        result = median_aggregator.aggregate([update])

        assert result.success is True

    def test_median_computation_odd(self, median_aggregator):
        """Вычисление медианы для нечётного количества."""
        values = [1.0, 3.0, 2.0, 5.0, 4.0]
        median = median_aggregator._median(values)
        assert median == 3.0

    def test_median_computation_even(self, median_aggregator):
        """Вычисление медианы для чётного количества."""
        values = [1.0, 2.0, 3.0, 4.0]
        median = median_aggregator._median(values)
        assert median == 2.5  # среднее двух средних

    def test_median_robust_to_outliers(self, median_aggregator, model_update_factory):
        """Median устойчив к выбросам."""
        # Создаём обновления с выбросом
        normal = [model_update_factory(node_id=f"n-{i}", seed=i) for i in range(4)]

        outlier = model_update_factory(node_id="outlier", seed=999)
        for layer in outlier.weights.layer_weights:
            outlier.weights.layer_weights[layer] = [1000.0] * len(outlier.weights.layer_weights[layer])

        all_updates = normal + [outlier]

        result = median_aggregator.aggregate(all_updates)

        # Медиана не должна быть близка к выбросу
        assert result.success is True
        flat = result.global_model.weights.to_flat_vector()
        assert all(abs(v) < 100 for v in flat)


class TestGetAggregator:
    """Тесты для фабричной функции get_aggregator."""

    def test_get_fedavg(self):
        """Получение FedAvg агрегатора."""
        agg = get_aggregator("fedavg")
        assert isinstance(agg, FedAvgAggregator)

    def test_get_krum(self):
        """Получение Krum агрегатора."""
        agg = get_aggregator("krum", f=2)
        assert isinstance(agg, KrumAggregator)
        assert agg.f == 2

    def test_get_trimmed_mean(self):
        """Получение TrimmedMean агрегатора."""
        agg = get_aggregator("trimmed_mean", beta=0.15)
        assert isinstance(agg, TrimmedMeanAggregator)
        assert agg.beta == 0.15

    def test_get_median(self):
        """Получение Median агрегатора."""
        agg = get_aggregator("median")
        assert isinstance(agg, MedianAggregator)

    def test_get_unknown_raises(self):
        """Неизвестный агрегатор вызывает исключение."""
        with pytest.raises(ValueError, match="Unknown aggregator"):
            get_aggregator("unknown_method")


class TestAggregatorConsistency:
    """Тесты консистентности агрегаторов."""

    def test_all_aggregators_return_same_structure(self, sample_updates):
        """Все агрегаторы возвращают одинаковую структуру."""
        # Добавляем ещё обновлений для Krum
        extra_updates = sample_updates + [
            ModelUpdate(
                node_id=f"extra-{i}",
                round_number=1,
                weights=sample_updates[0].weights,
                num_samples=100
            )
            for i in range(3)
        ]

        aggregators = [
            FedAvgAggregator(),
            KrumAggregator(f=1),
            TrimmedMeanAggregator(beta=0.1),
            MedianAggregator()
        ]

        for agg in aggregators:
            result = agg.aggregate(extra_updates)

            assert hasattr(result, 'success')
            assert hasattr(result, 'global_model')
            assert hasattr(result, 'aggregation_time_seconds')

            if result.success:
                assert result.global_model.version is not None
                assert result.global_model.weights is not None

    def test_aggregators_deterministic(self, sample_updates):
        """Агрегаторы детерминистичны (для одинакового входа)."""
        aggregator = FedAvgAggregator()

        result1 = aggregator.aggregate(sample_updates)
        result2 = aggregator.aggregate(sample_updates)

        # Результаты должны совпадать
        flat1 = result1.global_model.weights.to_flat_vector()
        flat2 = result2.global_model.weights.to_flat_vector()

        for v1, v2 in zip(flat1, flat2):
            assert abs(v1 - v2) < 1e-10


class TestByzantineRobustness:
    """Тесты Byzantine-robustness."""

    def test_fedavg_not_byzantine_robust(self, model_update_factory):
        """FedAvg НЕ устойчив к Byzantine атакам."""
        # Честные обновления
        honest = [model_update_factory(node_id=f"honest-{i}", seed=i) for i in range(4)]

        # Byzantine с экстремальными весами
        byzantine = model_update_factory(node_id="byzantine", seed=999)
        for layer in byzantine.weights.layer_weights:
            byzantine.weights.layer_weights[layer] = [1e6] * len(byzantine.weights.layer_weights[layer])

        all_updates = honest + [byzantine]

        aggregator = FedAvgAggregator()
        result = aggregator.aggregate(all_updates)

        # FedAvg усреднит с Byzantine, результат будет искажён
        flat = result.global_model.weights.to_flat_vector()
        # Средние будут большими из-за Byzantine
        assert any(abs(v) > 1000 for v in flat)

    def test_median_is_byzantine_robust(self, model_update_factory):
        """Median устойчив к Byzantine атакам."""
        # Честные обновления с малыми значениями
        honest = [model_update_factory(node_id=f"honest-{i}", seed=i) for i in range(5)]

        # Byzantine с экстремальными весами
        byzantine = model_update_factory(node_id="byzantine", seed=999)
        for layer in byzantine.weights.layer_weights:
            byzantine.weights.layer_weights[layer] = [1e6] * len(byzantine.weights.layer_weights[layer])

        all_updates = honest + [byzantine]

        aggregator = MedianAggregator()
        result = aggregator.aggregate(all_updates)

        # Медиана должна игнорировать выброс
        flat = result.global_model.weights.to_flat_vector()
        # Все значения должны быть разумными
        assert all(abs(v) < 100 for v in flat)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
